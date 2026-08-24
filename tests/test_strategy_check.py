"""Tests for bin/gac/strategy-check.py (project-strategy-v1 §10 落地).

Validates 9-dim strategy matrix validator:
- Pure status logic (no I/O)
- Color mapping per dimension
- JSON output structure
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "gac" / "strategy-check.py"
_MODULE = "_strategy_check_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    return _load()


# ---------------------------------------------------------------------------
# Status logic (pure)
# ---------------------------------------------------------------------------


def test_scene_status_green_when_3_assisted(tool):
    counts = {"shadow": 5, "assisted": 3, "routine": 0}
    assert tool._status_for_scene(counts, target_3m_assisted=3) == "GREEN"


def test_scene_status_yellow_with_mix(tool):
    counts = {"shadow": 7, "assisted": 1}
    assert tool._status_for_scene(counts, target_3m_assisted=3) == "YELLOW"


def test_scene_status_red_when_only_shadow(tool):
    counts = {"shadow": 9}
    assert tool._status_for_scene(counts, target_3m_assisted=3) == "RED"


def test_scene_status_grey_when_empty(tool):
    assert tool._status_for_scene({}, target_3m_assisted=3) == "GREY"


def test_maturity_status_green_at_target(tool):
    assert tool._status_for_maturity(8.0, target_3m=8.0) == "GREEN"


def test_maturity_status_yellow_near_target(tool):
    assert tool._status_for_maturity(7.7, target_3m=8.0) == "YELLOW"


def test_maturity_status_red_far_from_target(tool):
    assert tool._status_for_maturity(6.0, target_3m=8.0) == "RED"


def test_maturity_status_grey_when_none(tool):
    assert tool._status_for_maturity(None) == "GREY"


def test_bcos_status_provable_is_green(tool):
    assert tool._status_for_bcos("provable") == "GREEN"


def test_bcos_status_partial_is_yellow(tool):
    assert tool._status_for_bcos("partial") == "YELLOW"


def test_bcos_status_unprovable_is_red(tool):
    assert tool._status_for_bcos("unprovable") == "RED"


def test_health_status_thresholds(tool):
    assert tool._status_for_health(85) == "GREEN"
    assert tool._status_for_health(70) == "YELLOW"
    assert tool._status_for_health(50) == "RED"
    assert tool._status_for_health(None) == "GREY"


def test_bet_status_thresholds(tool):
    assert tool._status_for_bets({"available": True, "completion_pct": 95.0}) == "GREEN"
    assert tool._status_for_bets({"available": True, "completion_pct": 90.0}) == "YELLOW"
    assert tool._status_for_bets({"available": True, "completion_pct": 70.0}) == "RED"
    assert tool._status_for_bets({"available": False}) == "GREY"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_render_text_shows_all_9_dimensions(tool):
    dims = [
        {"id": i, "name": f"d{i}", "status": "GREEN", "target_3m": "x", "current": {}}
        for i in range(1, 10)
    ]
    text = tool.render_text(dims)
    for i in range(1, 10):
        assert f"d{i}" in text
    assert "GREEN=9" in text


def test_render_text_summary_counts(tool):
    dims = [
        {"id": 1, "name": "a", "status": "GREEN", "target_3m": "x", "current": {}},
        {"id": 2, "name": "b", "status": "YELLOW", "target_3m": "x", "current": {}},
        {"id": 3, "name": "c", "status": "RED", "target_3m": "x", "current": {}},
    ]
    text = tool.render_text(dims)
    assert "GREEN=1" in text
    assert "YELLOW=1" in text
    assert "RED=1" in text


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_runs_and_emits_matrix():
    """Smoke test: --json works, returns valid JSON with 9 dimensions."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "dimensions" in data
    assert len(data["dimensions"]) == 9
    for d in data["dimensions"]:
        assert "id" in d
        assert "name" in d
        assert "status" in d
        assert "current" in d
        assert d["status"] in {"GREEN", "YELLOW", "RED", "GREY"}