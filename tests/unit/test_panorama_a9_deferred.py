"""A9 accepts a deferred cockpit source as "not failed".

Under sustained host load the collector round is skipped rather than run into a
timeout. Reporting that as a source failure would paint the gate red for reasons
that have nothing to do with the source.
"""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"

REQUIRED_SOURCES = {
    "catalog", "strategy", "strategy-projection", "environment_evidence",
    "portfolio", "workflow", "resident", "scheduler", "references",
    "orca", "multica", "ruflo", "documents", "compute",
}


def _load(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("panorama_a9_deferred", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATA_JSON", tmp_path / "data.json")
    (tmp_path / "data.json").write_text(
        json.dumps({"generated_at": _stamp(0), "asd": {
            "schema": "asd-snapshot/v1", "verdict": "COMPLETE",
            "panels": {"overview": {}, "spine": {}, "agents": {}, "milestones": {}, "degradation": {}},
            "degraded_panels": [],
        }}), encoding="utf-8")
    home = tmp_path / "home"
    (home / ".local/share/zhixing-dashboard").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return module


def _stamp(age_seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()


def _cockpit(statuses: dict[str, str]) -> dict:
    states = {}
    for name in REQUIRED_SOURCES:
        status = statuses.get(name, "OK")
        states[name] = {"status": status, "last_success_at": _stamp(60)}
    return {"generated_at": _stamp(60), "source_states": states}


def _write_cockpit(tmp_path: dict, payload: dict) -> None:
    path = tmp_path["home"] / ".local/share/zhixing-dashboard/current.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("deferred", ["orca", "workflow", "ruflo"])
def test_deferred_source_does_not_fail_the_gate(monkeypatch, tmp_path, deferred):
    module = _load(monkeypatch, tmp_path)
    _write_cockpit({"home": tmp_path / "home"}, _cockpit({deferred: "DEFERRED"}))
    report = module.collect_a9_gate(payload={}, dashboard_live=True)
    assert report["verdict"] == "PASS", report


def test_failed_source_still_fails_the_gate(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    _write_cockpit({"home": tmp_path / "home"}, _cockpit({"orca": "UNAVAILABLE"}))
    report = module.collect_a9_gate(payload={}, dashboard_live=True)
    assert report["verdict"] == "PARTIAL"
    assert "cockpit_sources" in report["detail"]
