"""Observability unified event-plane API tests (T9-02)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_observability


def _write_events(tmp_path, events: list[dict]) -> None:
    path = tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )


def _sample_events() -> list[dict]:
    return [
        {
            "id": "evt_1",
            "ts": "2026-08-08T10:00:00.000Z",
            "domain": "governance",
            "type": "governance:gate_failed",
            "severity": "critical",
            "source": "gac-local-gate",
            "trace_id": "trace-abc",
            "payload": {"check": "x"},
            "schema_version": 1,
        },
        {
            "id": "evt_2",
            "ts": "2026-08-08T10:01:00.000Z",
            "domain": "runtime",
            "type": "runtime:bus_trace",
            "severity": "info",
            "source": "bus-foundation",
            "trace_id": "trace-abc",
            "payload": {"name": "op"},
            "schema_version": 1,
        },
        {
            "id": "evt_3",
            "ts": "2026-08-08T10:02:00.000Z",
            "domain": "governance",
            "type": "governance:gate_passed",
            "severity": "info",
            "source": "gac-local-gate",
            "trace_id": None,
            "payload": {},
            "schema_version": 1,
        },
    ]


class TestObservabilityEventsAPI:
    def test_events_returns_all(self, tmp_path, monkeypatch):
        _write_events(tmp_path, _sample_events())
        monkeypatch.setattr(
            api_observability, "_events_file",
            lambda: tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl",
        )
        resp = TestClient(app).get("/api/observability/events")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 3
        # 新→旧排序
        assert payload["items"][0]["id"] == "evt_3"

    def test_events_alert_only(self, tmp_path, monkeypatch):
        _write_events(tmp_path, _sample_events())
        monkeypatch.setattr(
            api_observability, "_events_file",
            lambda: tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl",
        )
        resp = TestClient(app).get("/api/observability/events", params={"alert_only": "true"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 1
        assert payload["items"][0]["severity"] == "critical"

    def test_events_filter_by_trace_id(self, tmp_path, monkeypatch):
        _write_events(tmp_path, _sample_events())
        monkeypatch.setattr(
            api_observability, "_events_file",
            lambda: tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl",
        )
        resp = TestClient(app).get(
            "/api/observability/events", params={"trace_id": "trace-abc"}
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 2
        assert {e["id"] for e in payload["items"]} == {"evt_1", "evt_2"}

    def test_events_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            api_observability, "_events_file",
            lambda: tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl",
        )
        resp = TestClient(app).get("/api/observability/events")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}


class TestObservabilityStatsAPI:
    def test_stats_aggregates(self, tmp_path, monkeypatch):
        _write_events(tmp_path, _sample_events())
        monkeypatch.setattr(
            api_observability, "_events_file",
            lambda: tmp_path / ".omo" / "_delivery" / "observability" / "events.jsonl",
        )
        resp = TestClient(app).get("/api/observability/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total"] == 3
        assert stats["by_severity"] == {"critical": 1, "info": 2}
        assert stats["by_domain"] == {"governance": 2, "runtime": 1}
        assert stats["alerts"] == 1
