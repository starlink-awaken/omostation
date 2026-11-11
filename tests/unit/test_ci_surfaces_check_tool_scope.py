"""`_is_check_tool` 必须认得根级 check 工具，不能只认前缀。

缺陷（2026-11-11 自证）：`check-ci-surfaces.py` 的 `_is_check_tool` 只用
`CHECK_PREFIX` 前缀列表（`bin/gac/`、`bin/ssot/` …）判「是不是 CI 检查工具」。
根级 `bin/*.py` 不在列表里，于是两个**真被 CI 执行**的 check 工具
既进不了 `ci-surfaces` 登记，也不会被 `gate-parity` / `unregistered-check` 点名：

- `bin/change-lane-check.py` —— sgf-policy gate `change-lane-check`（带 `--staged`）
- `bin/layer-dependency-check.py` —— `gac-gate.yml` 的 `check-layers` 步

两者在 `bin/_registry/scripts/governance/` 都有登记（说明是有主的治理工具），
但在 `ci-surfaces.yaml` 里**一条都没有** —— CI 平面可观测性对它们整块失明。

判据：前缀列表之外，根级 `bin/<name>.py` 的名字含
check/guard/audit/lint/verify 也算检查工具。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-ci-surfaces.py"


def _load():
    spec = importlib.util.spec_from_file_location("ci_surfaces_scope_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def test_root_level_check_tools_are_check_tools() -> None:
    """根级 check 工具必须被认出来（否则登记与告警双失明）。"""
    for tool in ("bin/change-lane-check.py", "bin/layer-dependency-check.py"):
        assert MODULE._is_check_tool(tool), f"{tool} 未被认作检查工具"


def test_prefixed_check_tools_still_recognized() -> None:
    """反例保护: 前缀列表内的工具不受影响。"""
    assert MODULE._is_check_tool("bin/gac/check-ci-surfaces.py")
    assert MODULE._is_check_tool("bin/ssot/doc-link-check.py")
    assert MODULE._is_check_tool("scripts/check-foo.py")


def test_root_level_non_check_tools_are_not_check_tools() -> None:
    """反例保护: 根级非 check 工具不得被误认（否则 gate-parity 会滥报）。"""
    for tool in (
        "bin/compass_radar.py",
        "bin/agent-workflow.py",
        "bin/ops/cli.py",
        "bin/layer-dependency.py",  # 名字里没有 check/guard/audit/lint/verify
    ):
        assert not MODULE._is_check_tool(tool), f"{tool} 被误认作检查工具"


def test_nested_non_check_tools_are_not_check_tools() -> None:
    """反例保护: 非根级目录里的同名形态仍按前缀判（避免全域误认）。"""
    assert not MODULE._is_check_tool("bin/ops/cost_tracker.py")
    assert not MODULE._is_check_tool("projects/omo/src/omo/x.py")
