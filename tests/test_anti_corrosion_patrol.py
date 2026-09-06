"""Tests for anti-corrosion-patrol (BET-Y2Q1-T6-03): red line, scoring, enforce."""

from __future__ import annotations

import importlib.util  # noqa: E402
import json
import subprocess
import sys
from pathlib import Path

_PATROL_PATH = Path(__file__).resolve().parents[1] / "bin" / "gac" / "anti-corrosion-patrol.py"
_spec = importlib.util.spec_from_file_location("anti_corrosion_patrol", _PATROL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

dead_code_and_dupes = _mod.dead_code_and_dupes
patrol = _mod.patrol
rule_health_score = _mod.rule_health_score
weekly_net_lines = _mod.weekly_net_lines

PATROL = str(Path(__file__).resolve().parents[1] / "bin" / "gac" / "anti-corrosion-patrol.py")


def test_weekly_net_lines_shape():
    net = weekly_net_lines(7)
    assert net["ok"] is True
    assert net["red_line"] == "<=0"
    assert net["breach"] == (net["net_lines"] > 0)


def test_rule_health_score_shape():
    health = rule_health_score()
    assert health["ok"] is True
    assert 0 <= health["health_score"] <= 100
    assert health["total_rules"] >= health["healthy"]


def test_dead_code_detector_integration():
    dead = dead_code_and_dupes()
    assert "ok" in dead  # detector 存在时 ok=True，缺失败时 ok=False + error


def test_patrol_snapshot_and_enforce_exit():
    snap = patrol(enforce=False)
    assert snap["verdict"] in ("PASS", "WARN", "BLOCK")
    assert snap["cockpit_alert"]["level"] in ("red", "yellow", "green")
    # enforce 模式: breach 时 exit 1, 无 breach 时 exit 0
    out = subprocess.run([sys.executable, PATROL, "--enforce", "--json"], capture_output=True, text=True, check=False)
    rc = out.returncode
    data = json.loads(out.stdout)
    if data["breaches"]:
        assert rc == 1 and data["verdict"] == "BLOCK"
    else:
        assert rc == 0


def test_patrol_json_has_alert_field():
    out = subprocess.run([sys.executable, PATROL, "--json"], capture_output=True, text=True, check=False)
    data = json.loads(out.stdout)
    assert data["schema"] == "gac.anti_corrosion_patrol.v1"
    assert data["cockpit_alert"]["level"] in ("red", "yellow", "green")
