"""CR-CI-RUNNER-COST — GitHub-hosted runner 成本守门回归。

钉住三件事（对应 AGENTS.md §7「扫源码的门禁必须自证」）：

1. **检测器自证** —— `--self-test` 必须通过，否则「绿」可能只是检测器没命中；
2. **允许清单双向对拍** —— 实测付费 OS 用法集合 == ALLOWED：漏一名红、留死名也红；
3. **理由指向真实文件** —— 每条 ALLOWED 的 workflow 路径必须真实存在。

背景：这道门守的是**覆盖增量**，不是账单 —— 一条 macOS/Windows 腿必须覆盖默认 OS 腿
拿不到的东西（launchd 仅 darwin、darwin-arm64 二进制只能 macOS 编译），零增量覆盖的腿
是纯浪费。成本是次要理由且只在 private 仓成立；本仓组全是 public 仓（Actions 分钟免费，
含 macOS），故「public 免费」不构成删这道门的理由。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-runner-cost.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_runner_cost", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_detector_self_test_passes() -> None:
    """检测器必须拿合成违规样本自证 —— 空绿的代价是判据在写者没改完时就变绿。"""
    mod = _load()
    assert mod.self_test() == 0


def test_measured_paid_os_equals_allowlist() -> None:
    """实测集合与 ALLOWED 双向相等：漏一名红、留死名也红。"""
    mod = _load()
    report = mod.scan(mod.REPO)
    measured = {(f["workflow"], f["job"]) for f in report["findings"]}
    # 只对已检出的 workflow 断言 —— 子模块未 init 的检出里那些文件不存在
    alive = {k for k in mod.ALLOWED if (mod.REPO / k[0]).is_file()}
    assert measured == alive, (
        f"实测 {len(measured)} 条 / 清单 {len(alive)} 条\n"
        f"  未登记(实测有而清单无): {sorted(measured - alive)}\n"
        f"  死条目(清单有而实测无): {sorted(alive - measured)}"
    )


def test_allowlist_reasons_are_non_empty() -> None:
    """每条豁免必须写理由 —— 无理由的豁免等于关掉这道闸。"""
    mod = _load()
    assert mod.ALLOWED, "ALLOWED 不能为空（空清单会让所有付费 OS 用法直接阻塞）"
    for key, reason in mod.ALLOWED.items():
        assert reason and reason.strip(), f"{key} 缺理由"
        assert len(reason) >= 10, f"{key} 理由过短 ({reason!r})"


def _declared_submodule_prefixes() -> set[str]:
    """从 .gitmodules 取已声明的子模块路径 —— 与「子模块是否检出」无关。"""
    import re

    text = (REPO_ROOT / ".gitmodules").read_text(encoding="utf-8")
    return {m.group(1).rstrip("/") for m in re.finditer(r"^\s*path\s*=\s*(\S+)", text, re.M)}


def test_allowlist_paths_are_declared_surfaces() -> None:
    """清单里每条路径必须落在根仓 .github 或某个已声明子模块下 —— 防拼写错误的死条目。

    刻意**不**断言文件存在：子模块是否检出是 host/worktree 状态（worktree claim 默认浅 init
    且可能超时），用它当判据会让用例在干净检出里假红。
    匹配用**最长前缀**而不是首段 —— `projects/knowledge/gbrain/...` 的首段是 `projects`，
    而声明的子模块路径是 `projects/knowledge/gbrain`。
    """
    mod = _load()
    prefixes = _declared_submodule_prefixes()
    for (rel, _job) in mod.ALLOWED:
        ok = rel.startswith(".github/") or any(
            rel == p or rel.startswith(p + "/") for p in prefixes
        )
        assert ok, (
            f"ALLOWED 路径 {rel} 既不在根仓 .github 下，"
            f"也不属于任何 .gitmodules 声明的子模块（声明: {sorted(prefixes)}）"
        )
        assert rel.endswith((".yml", ".yaml")), f"ALLOWED 路径不是 workflow 文件: {rel}"


def test_allowlist_entries_are_measured_when_checked_out() -> None:
    """已检出的子模块 workflow 必须被扫到 —— 否则清单会静默失效。"""
    mod = _load()
    report = mod.scan(mod.REPO)
    measured = {(f["workflow"], f["job"]) for f in report["findings"]}
    for key in mod.ALLOWED:
        if (mod.REPO / key[0]).is_file():
            assert key in measured, f"ALLOWED 条目 {key} 的 workflow 已检出但未被扫到"


def test_self_hosted_is_not_flagged() -> None:
    """self-hosted runner 免费 —— scan 层面不得产出任何 finding。

    `_paid_os` 是纯 OS 分类器（不认识 self-hosted），过滤发生在 `scan` 里；
    所以这里断言的是 scan 的行为，不是分类器的返回值。
    """
    import tempfile

    import yaml  # noqa: F401  (scan 内部需要)

    mod = _load()
    assert mod._is_self_hosted({"self-hosted", "macos"}) is True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "self.yml").write_text(
            "jobs:\n  a:\n    runs-on: [self-hosted, macos]\n    steps: []\n", encoding="utf-8"
        )
        assert mod.scan(root)["findings"] == []
