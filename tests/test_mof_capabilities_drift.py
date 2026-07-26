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


# ─── metaos registry 漂移注入检出 (§J1 扩展, workorder 2026-07-25) ───


def test_projects_capabilities_entrypoint_drift_detected(tmp_path):
    """注入死 entrypoint → 检出 (metaos 拆迁遗留: kairon.metaos 死路径复现)."""
    findings = drift.check_projects_capabilities_entrypoints(
        [{"id": "kairon.metaos", "entrypoint": "projects/kairon/packages/metaos"}],
        repo=tmp_path,
    )
    assert len(findings) == 1
    assert findings[0]["capability"] == "kairon.metaos"
    assert findings[0]["actual"] == "MISSING"


def test_projects_capabilities_entrypoint_clean(tmp_path):
    """真实存在 entrypoint → 无漂移."""
    (tmp_path / "projects" / "metaos").mkdir(parents=True)
    findings = drift.check_projects_capabilities_entrypoints(
        [{"id": "project.metaos", "entrypoint": "projects/metaos"}],
        repo=tmp_path,
    )
    assert findings == []


def test_metaos_cli_entrypoint_clean():
    """真实 INTERFACE.yaml (metaos.cli:main) → 无漂移 (入口可达)."""
    findings = drift.check_metaos_cli_entrypoint(drift.METAOS_INTERFACE)
    assert findings == []


def test_metaos_cli_entrypoint_drift_injected(tmp_path):
    """注入 ghost module → 检出 (声明/执行鸿沟)."""
    iface = tmp_path / "INTERFACE.yaml"
    iface.write_text("cli:\n  - module: ghost.pkg:main\n")
    findings = drift.check_metaos_cli_entrypoint(iface, repo=tmp_path)
    assert len(findings) == 1
    assert findings[0]["declared_module"] == "ghost.pkg:main"


def test_metaos_submodule_present_clean():
    """真实 metaos submodule 目录存在 → 无漂移."""
    findings = drift.check_metaos_submodule_present(drift.METAOS_SUBMODULE_DIR)
    assert findings == []


def test_metaos_submodule_missing_injected(tmp_path):
    """注入不存在目录 → 检出."""
    findings = drift.check_metaos_submodule_present(tmp_path / "nope")
    assert len(findings) == 1
    assert findings[0]["check"] == "metaos_submodule_missing"


def test_detect_metaos_registry_structure():
    """detect_metaos_registry_drift 结构正确 (§J1 验收: 一扇门覆盖 metaos 面)."""
    result = drift.detect_metaos_registry_drift()
    assert result["rule_id"] == drift.METAOS_RULE_ID
    assert "total_drifts" in result
    assert "findings" in result
    assert isinstance(result["registries"], list) and len(result["registries"]) >= 2


def test_detect_metaos_known_kairon_drift():
    """端到端活体验收: detect_metaos_registry_drift 检出 kairon.metaos 死路径.

    metaos 2026-06-06 从 kairon/packages/metaos 拆到 projects/metaos, 但
    projects-capabilities.yaml 的 kairon.metaos 条目 entrypoint 仍指向旧路径.
    维护契约: 若 kairon.metaos 已修(projects-capabilities 重生/退役), 删此测试.
    """
    result = drift.detect_metaos_registry_drift()
    cap_ids = {
        f["capability"]
        for f in result["findings"]
        if f.get("check") == "capability_entrypoint_missing"
    }
    assert "kairon.metaos" in cap_ids, (
        f"应检出 kairon.metaos 死路径, 实际 findings: {result['findings'][:3]}"
    )


def test_detect_all_drift_aggregates_two_scopes():
    """detect_all_drift 聚合 MOF + metaos 两面 (§J1: 同一扇门覆盖)."""
    result = drift.detect_all_drift()
    assert result["rule_id"] == "CR-X4-REGISTRY-DRIFT-AGGREGATE"
    assert result["scopes"] == ["mof", "metaos"]
    assert result["total_drifts"] >= 0
