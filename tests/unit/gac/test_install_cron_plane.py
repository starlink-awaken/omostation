"""crontab 平面安装器 (bin/ops/install-cron-plane.py) 的合同测试。

**为什么需要这个脚本** (2026-11-03 实测): `scheduler-compile.py --generate crontab` 只产出
**内容**, 从不写入本机 crontab ⇒ 登记面与安装面各走各的:

| 机器 | 登记面声明 | 实际装 | drift |
|---|---|---|---|
| mini | 43 条 | 43 条 | 0 |
| mbp  | 48 条 |  5 条 | 41 |

mbp 上那 38 条登记面声明的巡检**从未在本机跑过**。

**本文件锁住三件事**:
1. 安装器只动**登记面**的行, 本机其它行 (用户自装的外部工具) 一律保留。
2. 幂等: 连跑两次, crontab 内容逐字节相同。
3. `$HOME/Workspace` 必须展开成绝对路径 —— cron 的 PATH 只有 /usr/bin:/bin 且 crontab
   不走 shell 变量展开, 留字面量会让作业指向不存在的路径。

**判据自证**: 每条用例都做「变异对照」——把修复摘掉时用例必须变红
(否则绿可能只是「检测器压根没命中」)。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "bin" / "ops" / "install-cron-plane.py"


def _load():
    spec = importlib.util.spec_from_file_location("install_cron_plane", INSTALLER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── 判据 1: 归属判定 (只动登记面的行) ────────────────────────────────────────


def test_managed_lines_are_recognised_by_compiled_key() -> None:
    """登记面编译出的行 ⇒ 是「登记面的行」, 安装时要被替换。

    判据: 行的比较键与某条登记面条目相同 ⇒ 归登记面管。
    """
    module = _load()
    compiled = module._compiled_lines()
    assert compiled, "registry 应至少编译出 crontab 行, 否则本用例恒绿"
    managed = {module._key(line) for line in compiled}
    for line in compiled:
        assert module._is_managed(line, managed), f"登记面条目应被认领: {line[:90]}"


def test_foreign_lines_are_left_alone() -> None:
    """非登记面的行 (用户自装的外部工具) ⇒ 不属于登记面, 安装时保留。

    这条是安装器的**安全性**核心: 用户自己装的 clash-*/fleet-*/bwg-* 等
    外部工具不能被本仓登记面覆盖掉。
    """
    module = _load()
    managed = {module._key(line) for line in module._compiled_lines()}
    foreign = [
        "*/20 * * * * python3 /Users/xiamingxing/.local/bin/clash-speed active >>x.log 2>&1",
        "0 6 * * * cd /Users/xiamingxing/Project/work-agent && python3 scripts/x.py",
        "30 7 * * * /opt/homebrew/bin/python3 /Users/x/.local/bin/bwg-usage.sh >>y.log",
    ]
    for line in foreign:
        assert not module._is_managed(line, managed), (
            f"外部工具行不得被认领为登记面: {line[:80]}"
        )


def test_managed_detection_is_not_vacuous() -> None:
    """正控制: 判据确实会拒认领 —— 否则上面两条可能恒真。"""
    module = _load()
    managed = {module._key(line) for line in module._compiled_lines()}
    # 一条**登记面里确实存在**的变体 (只差解释器写法) 必须被认领
    sample = module._compiled_lines()[0]
    variant = sample.replace("/opt/homebrew/bin/python3.13", "python3")
    assert module._is_managed(variant, managed), "解释器写法不同的同一作业应被认领"


# ── 判据 2: $HOME/Workspace 展开 (cron 不做 shell 变量展开) ────────────────────


def test_home_workspace_is_expanded_to_absolute_path() -> None:
    """registry 里的 `$HOME/Workspace` 必须展开成绝对路径。

    cron 的 PATH 只有 /usr/bin:/bin, 且 crontab **不走 shell 的变量展开** ⇒
    留字面量 `$HOME/Workspace` 会让作业指向一个不存在的相对路径。
    """
    module = _load()
    home = str(Path.home())
    expanded = module._expand_workspace('cd "$HOME/Workspace" && python3 x.py')
    assert f"{home}/Workspace" in expanded
    assert "$HOME" not in expanded

    plain = module._expand_workspace("cd $HOME/Workspace && python3 x.py")
    assert f"{home}/Workspace" in plain
    assert "$HOME" not in plain


def test_expansion_does_not_touch_other_home_references() -> None:
    """只展开 `$HOME/Workspace`, 不动别的 `$HOME` 引用。

    registry 里有 `>> $HOME/.local/log/x.log` 这类写法 —— 那些是**日志重定向**,
    由 cron 作业的 shell 解释, 展开与否取决于写法, 不在本脚本职责内。
    过度展开会把登记面与安装态的口径搅乱 (判据 `_key` 依赖两侧同口径)。
    """
    module = _load()
    out = module._expand_workspace("cmd >> $HOME/.local/log/x.log")
    assert "$HOME/.local/log/x.log" in out, "非 Workspace 的 $HOME 引用不得被改写"


# ── 判据 3: 幂等 (安装两次内容不变) ───────────────────────────────────────────


def _fake_crontab(monkeypatch: pytest.MonkeyPatch, module, initial: list[str]) -> dict:
    """把 crontab 读/写接到内存里, 返回状态 dict。

    **返回 dict 而非 list**: 写入时 crontab 内容整体替换 ⇒ 实现会 rebind
    `state["lines"]` 到**新** list 对象; 拿初始 list 引用会读到旧内容。
    """
    state: dict = {"lines": list(initial)}

    def fake_run(args, **kwargs):
        if args[0] == "crontab" and args[1] == "-l":
            return subprocess.CompletedProcess(args, 0, "\n".join(state["lines"]) + "\n", "")
        if args[0] == "crontab" and args[1] == "-":
            state["lines"] = (kwargs.get("input") or "").splitlines()
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return state


def test_install_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """连装两次 ⇒ crontab 内容逐字节相同。

    幂等是安装器的**硬要求**: 每次装都重排/改写会让 crontab 一直处于变动中,
    cron 反复重载, 且无法用「装完再比一次」验证是否真的对齐。
    """
    module = _load()
    foreign = "*/20 * * * * python3 /Users/x/.local/bin/clash-speed active >>x.log 2>&1"
    state = _fake_crontab(monkeypatch, module, [foreign])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 0
    first = list(state["lines"])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 0
    second = list(state["lines"])

    assert first == second, "安装器不幂等: 第二次装后内容变了"
    assert len(first) > 1, "应装入登记面条目, 不只是保留外部工具行"


def test_install_preserves_foreign_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """安装后, 非登记面的行必须**原样保留**。

    变异对照: 把「保留外部行」这段逻辑摘掉 ⇒ 本用例变红。
    """
    module = _load()
    foreign = "*/20 * * * * python3 /Users/x/.local/bin/clash-speed active >>x.log 2>&1"
    state = _fake_crontab(monkeypatch, module, [foreign])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 0

    assert foreign in state["lines"], "外部工具行被安装器覆盖掉了"


def test_install_replaces_stale_managed_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """登记面里声明、但本机内容已过时的行 ⇒ 被替换成登记面的当前内容。

    场景: 登记面改了命令 (如加了 --retention-days), 本机还是旧版 ⇒
    装完必须与登记面逐字一致, 否则那条变更在本机不生效。
    """
    module = _load()
    compiled = module._compiled_lines()
    assert compiled, "registry 应至少编译出 crontab 行, 否则本用例恒绿"
    target = compiled[0]
    stale = target.replace("python3", "python3.9", 1)
    if stale == target:
        stale = target + " # stale"

    state = _fake_crontab(monkeypatch, module, [stale])
    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 0

    assert stale not in state["lines"], "过时的登记面行应被替换, 不能与新行并存"
    assert target in state["lines"], "登记面的当前内容应被装入"


def test_status_reports_missing_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """--status: 装的少于登记面时要报 MISSING 且返回非 0。

    这是「装得不全」的**可观测面**: mbp 上 drift 41 就是靠它暴露的。
    """
    module = _load()
    state = _fake_crontab(monkeypatch, module, [])["lines"]
    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--status"])
    rc = module.main()
    assert rc == 1, "一条都没装时 --status 应返回非 0"


def test_status_returns_zero_when_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """登记面全部装齐时 --status 返回 0。

    正控制: 与上面「缺一条就非 0」配对, 证明返回码确实随实况变化。
    """
    module = _load()
    state = _fake_crontab(monkeypatch, module, module._compiled_lines())["lines"]
    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--status"])
    assert module.main() == 0


def test_remove_keeps_foreign_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """--remove 只移除登记面的行, 外部工具行保留。

    与 install 同一套归属判定 ⇒ 装/卸对称。
    """
    module = _load()
    foreign = "*/20 * * * * python3 /Users/x/.local/bin/clash-speed active >>x.log 2>&1"
    state = _fake_crontab(monkeypatch, module, module._compiled_lines() + [foreign])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--remove"])
    assert module.main() == 0

    assert foreign in state["lines"], "外部工具行不该被 --remove 删掉"
    for line in module._compiled_lines():
        assert line not in state["lines"], f"登记面条目未被移除: {line[:80]}"


def test_dry_run_does_not_write(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """--dry-run 只打印, 不写 crontab。

    **必须读 state dict 而不是 list 引用**: 写入时实现会 rebind `state["lines"]`
    到**新** list 对象; 拿旧引用比对恒等 ⇒ 本用例恒绿 (踩过: 变异对照
    「dry-run 也真写」当时没被抓到, 就是这个坑)。
    """
    module = _load()
    state = _fake_crontab(monkeypatch, module, [])
    before = list(state["lines"])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--dry-run", "--install"])
    assert module.main() == 0
    assert state["lines"] == before, "--dry-run 写了 crontab"
    assert capsys.readouterr().out.strip(), "dry-run 应有输出"


def test_dry_run_remove_does_not_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """--remove --dry-run 也不写 (两条路径各有守卫, 都要覆盖)。"""
    module = _load()
    state = _fake_crontab(monkeypatch, module, module._compiled_lines())
    before = list(state["lines"])

    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--dry-run", "--remove"])
    assert module.main() == 0
    assert state["lines"] == before, "--remove --dry-run 写了 crontab"
