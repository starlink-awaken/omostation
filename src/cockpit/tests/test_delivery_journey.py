"""Tests for Cockpit Engineering Delivery Golden Journey projection and API."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.delivery_journey import build_delivery_journey_projection
from cockpit.web.api_delivery_journey import router


def test_projection_fixtures_four_states():
    """Verify that PENDING -> RUNNING -> VERIFIED -> MERGED states project correctly without fake green."""
    pending = build_delivery_journey_projection(fixture_state="PENDING")
    assert pending.status == "live"
    assert pending.stages["intent"]["status"] == "pending"
    assert pending.stages["run"]["status"] == "pending"
    assert pending.stages["pr"]["status"] == "pending"
    assert pending.freshness >= 0

    running = build_delivery_journey_projection(fixture_state="RUNNING")
    assert running.status == "live"
    assert running.stages["intent"]["status"] == "verified"
    assert running.stages["run"]["status"] == "running"
    assert running.stages["pr"]["status"] == "pending"

    verified = build_delivery_journey_projection(fixture_state="VERIFIED")
    assert verified.status == "live"
    assert verified.stages["run"]["status"] == "verified"
    assert verified.stages["verification"]["status"] == "verified"
    assert verified.stages["pr"]["status"] == "open"

    merged = build_delivery_journey_projection(fixture_state="MERGED")
    assert merged.status == "live"
    assert merged.stages["verification"]["status"] == "verified"
    assert merged.stages["pr"]["status"] == "merged"
    assert merged.stages["evidence"]["status"] == "verified"


def test_projection_unavailable_state():
    """Verify that UNAVAILABLE state is reported accurately without default green/fake data."""
    unavail = build_delivery_journey_projection(fixture_state="UNAVAILABLE")
    assert unavail.status == "unavailable"
    for st in unavail.stages.values():
        assert st["status"] == "unavailable"


def test_projection_without_workflow_run_is_waiting_and_stale(monkeypatch, tmp_path):
    """A readable worktree is not evidence of an active delivery journey."""
    import cockpit.delivery_journey as delivery_journey

    monkeypatch.setattr(
        delivery_journey,
        "_try_get_git_info",
        lambda _root: {"branch": "work/example", "sha": "abc123", "is_clean": True, "ok": True},
    )
    snapshot = build_delivery_journey_projection(root_dir=tmp_path)

    assert snapshot.status == "stale"
    assert snapshot.mode == "waiting_for_run"
    assert snapshot.id == "waiting-for-run"
    assert snapshot.scene_binding is None
    assert snapshot.stages["intent"]["status"] == "pending"
    assert snapshot.stages["run"]["status"] == "pending"
    assert snapshot.stages["worktree"]["status"] == "verified"
    assert "受治理任务" in snapshot.next_action


def test_projection_reads_scene_binding_from_real_run(monkeypatch, tmp_path):
    """A real run carries the business binding; the projection does not invent it."""
    import cockpit.delivery_journey as delivery_journey

    runs_dir = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "run.yaml").write_text(
        """run_id: run-001
objective: verify delivery truth
status: running
start_time: '2026-08-02T13:00:00Z'
scene_binding:
  scene_id: engineering-delivery
  journey_id: intent-to-evidence
  outcome_metric: verified_delivery_lead_time
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        delivery_journey,
        "_try_get_git_info",
        lambda _root: {"branch": "work/example", "sha": "abc123", "is_clean": False, "ok": True},
    )

    snapshot = build_delivery_journey_projection(root_dir=tmp_path)

    assert snapshot.status == "live"
    assert snapshot.mode == "active"
    assert snapshot.scene_binding == {
        "scene_id": "engineering-delivery",
        "journey_id": "intent-to-evidence",
        "outcome_metric": "verified_delivery_lead_time",
    }
    assert snapshot.stages["run"]["status"] == "running"


def test_delivery_journey_api_endpoints():
    """Test FastAPI endpoints for delivery journey."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    res = client.get("/api/delivery-journey?fixture=VERIFIED")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "live"
    assert data["journey"]["id"] == "fixture-verified-103"
    assert data["journey"]["stages"]["pr"]["status"] == "open"

    res_unavail = client.get("/api/delivery-journey?fixture=UNAVAILABLE")
    assert res_unavail.status_code == 200
    data_unavail = res_unavail.json()
    assert data_unavail["ok"] is False
    assert data_unavail["status"] == "unavailable"
