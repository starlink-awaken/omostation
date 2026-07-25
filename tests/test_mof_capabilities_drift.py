"""STRAT MOF-M4 Phase0 P0-2 — check-mof-capabilities-drift 漂移门测试 (ADR-0238).

验证 CR-X4-MOF-CAPABILITIES-DRIFT: 注入三类漂移 (path/stat/mcptool_count) 均被检出,
干净状态全绿. 守"注册面零漂移"北极星 (plan §3).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# 连字符文件名无法直接 import, 用 importlib 动态加载
_BIN = Path(__file__).resolve().parent.parent / "bin" / "mof"
_spec = importlib.util.spec_from_file_location(
    "mof_drift", _BIN / "check-mof-capabilities-drift.py"
)
assert _spec is not None and _spec.loader is not None, "无法加载 drift 模块"
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


# ─── 端到端: 当前真实注册表 (P0-1/P0-4 已修复) 必须全绿 ───


def test_clean_current_registry_no_drift():
    """端到端: 真实 mof-capabilities.yaml (已修复) → 0 drift."""
    result = drift.detect_drift()
    assert result["total_drifts"] == 0, f"仍有漂移: {result['findings']}"
    assert result["rule_id"] == "CR-X4-MOF-CAPABILITIES-DRIFT"


# ─── model_stats 漂移注入检出 (P0-1 守护) ───


def test_stat_drift_detected():
    """故意注入 m1_nodes=999 (实际 1419) → 检出 1 项."""
    findings = drift.check_model_stats(
        {"m1_nodes": 999, "m2_schemas": 55}, actual_m1=1419, actual_m2=55
    )
    assert len(findings) == 1
    assert findings[0]["stat"] == "m1_nodes"
    assert findings[0]["declared"] == 999
    assert findings[0]["actual"] == 1419


def test_stat_clean_no_drift():
    """正确 stats → 无漂移."""
    findings = drift.check_model_stats(
        {"m1_nodes": 1419, "m2_schemas": 55}, actual_m1=1419, actual_m2=55
    )
    assert findings == []


# ─── tool path 漂移注入检出 (bin/mof/* 迁移最易复发) ───


def test_path_drift_detected(tmp_path):
    """故意注入幽灵 path → 检出 (bin/mof-* 旧路径漂移复现)."""
    findings = drift.check_tool_paths(
        {"ghost-tool": {"path": "nonexistent/ghost"}}, repo=tmp_path
    )
    assert len(findings) == 1
    assert findings[0]["tool"] == "ghost-tool"
    assert findings[0]["declared_path"] == "nonexistent/ghost"
    assert findings[0]["actual"] == "MISSING"


def test_path_exists_no_drift(tmp_path):
    """真实存在 path → 无漂移."""
    real = tmp_path / "bin" / "mof" / "mof-io"
    real.parent.mkdir(parents=True)
    real.write_text("x")
    findings = drift.check_tool_paths(
        {"mof-io": {"path": "bin/mof/mof-io"}}, repo=tmp_path
    )
    assert findings == []


# ─── MCPTOOL tool_count 漂移注入检出 (P0-4 守护) ───


def test_mcptool_count_drift_detected():
    """故意注入 tool_count=41 (代码实际 2) → 检出 (P0-4 漂移复现)."""
    findings = drift.check_mcptool_tool_count(
        declared=41, mcp_code="self._register_tool()\nself._register_tool()"
    )
    assert len(findings) == 1
    assert findings[0]["declared"] == 41
    assert findings[0]["actual"] == 2
    assert findings[0]["node"] == "MCPTOOL-MODEL-DRIVEN"


def test_mcptool_count_clean():
    """正确 tool_count → 无漂移."""
    findings = drift.check_mcptool_tool_count(
        declared=2, mcp_code="self._register_tool()\nself._register_tool()"
    )
    assert findings == []
