"""BET-Y1Q4-T2-05 pipeline supervisor: degrade semantics, state, inbound chain."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "pipeline_supervisor", ROOT / "projects/omo/src/omo/pipeline_supervisor.py"
)
assert spec and spec.loader
SUP = importlib.util.module_from_spec(spec)
sys.modules["pipeline_supervisor"] = SUP
spec.loader.exec_module(SUP)


def test_station_degrade_captures_reason():
    states: dict = {}
    result = SUP._station("boom", states, lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert result is None
    assert states["boom"]["status"] == "degraded"
    assert "RuntimeError" in states["boom"]["reason"]


def test_station_ok_records_latency():
    states: dict = {}
    out = SUP._station("fine", states, lambda: 42)
    assert out == 42 and states["fine"]["status"] == "ok" and "ms" in states["fine"]


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(SUP, "_ws", lambda: tmp_path)
    SUP._save_state({"schema": SUP.SCHEMA, "morning_runs": [{"ts": "t"}], "inbound_runs": [], "alerts": []})
    loaded = SUP._load_state()
    assert loaded["morning_runs"][0]["ts"] == "t"


def test_status_panel_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(SUP, "_ws", lambda: tmp_path)
    panel = SUP.status()
    assert panel["schema"] == SUP.SCHEMA
    assert panel["today_morning_brief"] is False and panel["morning_runs_total"] == 0


def test_inbound_degrade_on_missing_file(tmp_path, monkeypatch):
    """Bad input → degraded stations, run recorded, no crash (circuit_breaker)."""
    monkeypatch.setattr(SUP, "_ws", lambda: tmp_path)
    result = SUP.process_inbound(Path("/tmp/nonexistent-degrade-test.png"))
    assert result["degraded"], "missing file must degrade, not crash"
    state = json.loads((tmp_path / ".omo/state/pipeline-supervisor-state.json").read_text(encoding="utf-8"))
    assert state["inbound_runs"] and state["alerts"]  # recorded + alerted


def test_routes_registered():
    routes = (ROOT / "projects/omo/src/omo/resident/resident-routes.yaml").read_text(encoding="utf-8")
    assert "PipelineTick" in routes and "pipeline_supervisor" in routes
