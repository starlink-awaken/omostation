"""Integration tests for the ontoderive CLI/derivation surface.

The original CLI entry point (`python -m ontoderive.cli`) was removed
when the `engine/` directory was retired (P30); the only remaining
`__main__` is the POC stdio MCP server. These tests therefore
exercise the underlying public surface directly: building an
OntoDerive instance and running the commands that the CLI used to
dispatch. This locks the integration boundary so future refactors
that drop a method surface a failure here, not in production.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ontoderive.core.derive import OntoDerive
from ontoderive.toolforge import ToolForge

PYTHON = sys.executable


def _seed_project(project_dir: Path) -> Path:
    """Seed a project root with the minimum directory layout that
    OntoDerive expects to see on disk."""
    for sub in ("facts", "entities", "inferences", "scheme", "protocols", "_logs"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    (project_dir / "facts" / "D-F1.md").write_text(
        "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n| D-F1 | 测试 | 1 | t |\n",
        encoding="utf-8",
    )
    return project_dir


# ── Derive surface ──────────────────────────────────────────


def test_derive_engine_runs_against_seed_project(tmp_path: Path):
    project = _seed_project(tmp_path / "demo")
    od = OntoDerive(str(project))
    summary = od.derive()
    assert summary["facts"] >= 1
    assert summary["inferences"] >= 0
    assert "derived_at" in summary


def test_derive_engine_alignment_report_smoke(tmp_path: Path):
    project = _seed_project(tmp_path / "demo")
    od = OntoDerive(str(project))
    report = od.build_alignment_report()
    assert "alignment_rate" in report
    assert 0.0 <= report["alignment_rate"] <= 1.0
    assert "issues" in report


def test_derive_engine_validation_pipeline_smoke(tmp_path: Path):
    project = _seed_project(tmp_path / "demo")
    od = OntoDerive(str(project))
    result = od.run_validation_pipeline()
    assert "alignment_report" in result
    assert len(result["steps"]) == 4
    assert {"step", "status"} <= set(result["steps"][0].keys())


# ── ToolForge surface ───────────────────────────────────────


def test_toolforge_match_returns_grouped_results():
    tf = ToolForge()
    matched = tf.match("分析新能源汽车市场", limit=3)
    assert isinstance(matched, dict)
    # At least one category should return matches for a content-rich
    # Chinese query.
    assert any(matched.values())


def test_toolforge_select_returns_top_n():
    tf = ToolForge()
    results = tf.select("市场进入策略", top_n=3)
    assert len(results) <= 3
    for tool in results:
        assert "id" in tool
        assert "score" in tool


# ── MCP surface (must remain subprocess-importable) ─────────


def test_ontoderive_mcp_help_advertises_transport_options():
    """The published MCP server entry point should always advertise a
    transport action so downstream MCP routers can discover it."""
    result = subprocess.run(
        [PYTHON, "-m", "ontoderive", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    # The stdio POC server prints its usage; lock that it surfaces
    # the transport-related action keyword.
    assert "--action" in combined
    assert "ACTION" in combined
    assert "{serve}" in combined
