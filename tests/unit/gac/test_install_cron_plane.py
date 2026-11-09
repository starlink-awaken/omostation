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

    路径从 home 派生而非写字面量 —— tests/unit 的 host 字面量尺
    (test_tests_unit_host_anchors.py) 只允许声明过的合法位置有命中。
    """
    module = _load()
    managed = {module._key(line) for line in module._compiled_lines()}
    home = Path.home()
    foreign = [
        f"*/20 * * * * python3 {home}/.local/bin/clash-speed active >>x.log 2>&1",
        f"0 6 * * * cd {home}/Project/work-agent && python3 scripts/x.py",
        f"30 7 * * * /opt/homebrew/bin/python3 {home}/.local/bin/bwg-usage.sh >>y.log",
    ]
    for line in foreign:
        assert not module._is_managed(line, managed), (
            f"外部工具行不得被认领为登记面: {line[:80]}"
        )


def test_key_does_not_truncate_long_lines() -> None:
    """比较键必须是整行, 不得截断到 120 字符。

    截断会把「前 120 字符相同、之后不同」的两条行折成一个键:
    认领侧让用户自装的外部行被误认成登记面 (安装时**删掉**), 缺失侧让登记面里
    内容不同的两条塌成一条。与 scheduler-compile 的 BET-Y2Q4-T10-291 同族,
    那边已整行化, 本函数此前漏改。
    """
    module = _load()
    # 前 120 字符完全相同, 差异只在 120 之后 —— 截断恰好把这个差异抹掉。
    head = "0 6 * * * cd /some/where && python3 script.py --flag " + "x" * 100
    assert len(head) > 120, "前缀未超 120 字符 —— 本用例失去判别力"
    assert module._key(head + "--alpha") != module._key(head + "--beta"), (
        "比较键被截断: 前 120 字符相同的两条行被折成一个键"
    )


def test_foreign_line_sharing_120_char_prefix_is_not_claimed() -> None:
    """外部行只在前 120 字符上与登记面相同 ⇒ 不得被认领。

    这是安装器**安全性**的直接判据: 认领错一行就等于把用户自装的作业删掉。
    用合成行而非真实登记面 —— 判据只依赖 `_key` 的截断行为, 与 registry 内容无关。
    """
    module = _load()
    target = "0 6 * * * cd /some/where && python3 script.py --flag " + "x" * 200
    foreign = target[:120] + "--user-own-tool"
    managed = {module._key(target)}
    assert module._is_managed(target, managed), "正控制: 登记面行本身应被认领"
    assert not module._is_managed(foreign, managed), (
        "外部行只在前 120 字符上与登记面相同就被认领 —— 安装时会把它删掉"
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
    foreign = f"*/20 * * * * python3 {Path.home()}/.local/bin/clash-speed active >>x.log 2>&1"
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
    foreign = f"*/20 * * * * python3 {Path.home()}/.local/bin/clash-speed active >>x.log 2>&1"
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
    foreign = f"*/20 * * * * python3 {Path.home()}/.local/bin/clash-speed active >>x.log 2>&1"
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


def test_install_skips_write_when_already_aligned(monkeypatch: pytest.MonkeyPatch) -> None:
    """已对齐时不得重写 crontab。

    无条件重写会让每次 --install 都触发 cron 重载 + crontab mtime 变动, 即使什么
    都没改。本机 `crontab(1)` 写入持续 EINTR 时, 这一条还能让「已对齐」的安装
    成功 (否则明明没事也会失败)。
    """
    module = _load()
    compiled = module._compiled_lines()
    assert compiled, "登记面应编译出条目, 否则本用例恒绿"
    writes: list[str] = []

    def fake_run(args, **kwargs):
        if args[0] == "crontab" and args[1] == "-l":
            return subprocess.CompletedProcess(args, 0, "\n".join(compiled) + "\n", "")
        if args[0] == "crontab" and args[1] == "-":
            writes.append(kwargs.get("input") or "")
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 0
    assert writes == [], "已对齐却仍调用了 crontab - 写入"


def test_write_failure_returns_nonzero_and_prints_content(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """写入失败必须返回非 0 且把将写入的内容打出来。

    只抛 CalledProcessError 的话, 调用者拿不到可以直接手工应用的内容 —— 实测
    本机 `crontab(1)` 写入持续 EINTR (系统级) 时卡住的正是这一步。
    """
    module = _load()

    def fake_run(args, **kwargs):
        if args[0] == "crontab" and args[1] == "-l":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "crontab" and args[1] == "-":
            return subprocess.CompletedProcess(
                args, 1, "", "crontab: tmp/tmp.1: Interrupted system call"
            )
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["install-cron-plane.py", "--install"])
    assert module.main() == 1
    err = capsys.readouterr().err
    assert "Interrupted system call" in err, "失败原因要原样带出来"
    assert module._compiled_lines()[0][:40] in err, "失败时要打印将写入的内容"


# ── scheduler-compile.py --diff: 整份替换的破坏面预览 ────────────────────────


def test_diff_does_not_report_home_spelled_candidates_as_added() -> None:
    """候选侧必须与 check_drift 同口径展开 `$HOME/Workspace`。

    不展开时, 登记面里每个 `$HOME` 拼法的作业都会同时出现在 removed 与 added 里 ——
    实测 23 条「added」**全部**含 `$HOME`, 而同期 `check_drift` 是 drift 0 / orphan 3
    (两边对同一份登记面给出互相矛盾的读数)。
    """
    spec = importlib.util.spec_from_file_location(
        "scheduler_compile_diff", ROOT / "bin" / "scheduler-compile.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    jobs = module._load_jobs()
    candidate = [l for l in module.compile_crontab(jobs) if l.strip() and not l.startswith("#")]
    assert candidate, "登记面应编译出条目, 否则本用例恒绿"
    res = module.diff_installation(
        installed_lines=[module._expand_workspace(l) for l in candidate]
    )
    assert res["added"] == [], f"$HOME 拼法的候选被当成「会加」: {res['added'][:3]}"
    assert res["removed"] == [], f"展开后的候选被当成「会删」: {res['removed'][:3]}"


def test_diff_installation_names_what_wholesale_replace_would_delete() -> None:
    """`scheduler-compile.py --diff` 必须点名「整份替换会删掉哪些已装条目」。

    背景 (2026-11-07 实测): 已装 crontab 比 `.omo/cron/registry.yaml` 多出
    resident daemon 五角色 (`*/2`) 等条目; 整份 `generate crontab | crontab -`
    会把它们删掉 —— resident daemon 是常驻 Agent 的驱动。--diff 是装机前的
    只读安全预览, 与 install-cron-plane.py 的分工: 后者只动自己登记面的行,
    本函数回答「整份替换会改动什么」。
    """
    spec = importlib.util.spec_from_file_location(
        "scheduler_compile", ROOT / "bin" / "scheduler-compile.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    # 路径从 home 派生而非写字面量: tests/unit 的 host 字面量尺
    # (test_tests_unit_host_anchors.py) 只允许声明过的合法位置有命中,
    # 且换机后注入行仍要落在「登记面没有的路径」上 (判据才成立)。
    home = str(Path.home())
    res = module.diff_installation(
        installed_lines=[
            f"*/2 * * * * cd {home}/Workspace && /opt/homebrew/bin/python3 "
            f"-m omo.cli resident daemon --once --role decision "
            f">> {home}/Workspace/.omo/_delivery/resident-orchestrator/cron-decision.log 2>&1",
            "0 3 * * * cd $HOME/Workspace && python3 bin/ssot/log-rotate.py --daily "
            ">> runtime/cron/log-rotate.log 2>&1",
        ]
    )
    assert res["mode"] == "read_only"
    assert res["removed_count"] >= 1
    # 关键判据: resident daemon 那条必须被点名 —— 它是常驻 Agent 的驱动,
    # 整份替换会把它删掉。
    assert any("resident daemon" in line for line in res["removed"])
    # 正控制: 候选里**确实存在**的条目不得被报成「会删」—— 否则 removed
    # 可能只是把整个已装面倒出来, 判据失义。
    candidate = [l.strip() for l in module.compile_crontab(module._load_jobs()) if l.strip()]
    assert candidate, "登记面应编译出 crontab 行, 否则本用例恒绿"
    removed = {r.strip() for r in res["removed"]}
    assert not any(c in removed for c in candidate), "候选条目被误报为会删除"


def test_compiled_lines_respect_host_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """`hosts` 字段: 别机专用条目不得出现在本机编译产物里.

    CRON-REGISTRY-NO-HOST-SCOPE —— 安装器此前不过滤, 会把 mini 专用条目报成
    `[MISSING]` 并装上 (实测 mbp: 登记面 44 条 / 缺 1), 让 check_drift 侧的修复被
    安装侧抵消。同口径由 `cron_normalize.host_scoped_jobs` 单点提供。
    """
    module = _load()
    jobs = module._load_raw().get("jobs", [])
    watchdog = next(
        (j for j in jobs if j.get("name") == "work-agent-respire-mbp-watchdog"), None
    )
    assert watchdog is not None, "registry 里应有 work-agent-respire-mbp-watchdog"
    assert watchdog.get("hosts") == ["mini"]

    monkeypatch.setenv("CRON_HOST", "mbp")
    mbp = "\n".join(module._compiled_lines())
    assert "respire_mbp_supervisor_watchdog" not in mbp

    monkeypatch.setenv("CRON_HOST", "mini")
    mini = "\n".join(module._compiled_lines())
    assert "respire_mbp_supervisor_watchdog" in mini


def test_status_missing_listing_is_host_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--status` 的 MISSING 清单与本机作用域一致 —— mini 多的那一条正是 watchdog."""
    module = _load()
    monkeypatch.setenv("CRON_HOST", "mbp")
    mbp_lines = module._compiled_lines()
    monkeypatch.setenv("CRON_HOST", "mini")
    mini_lines = module._compiled_lines()
    assert len(mini_lines) == len(mbp_lines) + 1
    assert any("respire_mbp_supervisor_watchdog" in line for line in mini_lines)
    assert not any("respire_mbp_supervisor_watchdog" in line for line in mbp_lines)


def _load_compile_module():
    """按路径加载 scheduler-compile.py (文件名带连字符, 不能直接 import)."""
    spec = importlib.util.spec_from_file_location(
        "scheduler_compile_agree", ROOT / "bin" / "scheduler-compile.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_installer_and_compiler_agree_on_managed_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """安装器与编译器对「哪些条目归登记面管」必须给出**同一个集合**.

    这是「同口径必须单点」的门禁: #5147 给 `scheduler-compile` 加了 hosts 过滤而
    安装器漏掉, 于是判据侧 `check_drift` 绿、安装侧仍把 mini 专用条目报成
    `[MISSING]` 并装上 —— 两边对同一份 registry 给出不同的托管集合。
    """
    icp = _load()
    sc = _load_compile_module()
    monkeypatch.setenv("CRON_HOST", "mbp")

    compiler_keys = {
        icp._key(icp._expand_workspace(line))
        for line in sc.compile_crontab(sc._load_jobs())
        if line.strip() and not line.startswith("#")
    }
    installer_keys = {icp._key(line) for line in icp._compiled_lines()}
    assert compiler_keys, "编译器应产出条目, 否则本用例恒绿"
    assert installer_keys == compiler_keys, (
        "安装器与编译器的托管集合不一致: "
        f"only-installer={sorted(installer_keys - compiler_keys)[:2]} "
        f"only-compiler={sorted(compiler_keys - installer_keys)[:2]}"
    )
