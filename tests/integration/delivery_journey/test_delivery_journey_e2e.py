"""
Safe Fixture E2E Verification for Cockpit Engineering Delivery Golden Journey.
Validates PENDING, RUNNING, VERIFIED, MERGED states and UNAVAILABLE degradation
without generating real production mutations.
"""

import os
import sys
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure cockpit package is accessible
root_dir = Path(__file__).resolve().parent.parent.parent.parent
cockpit_src = root_dir / "projects" / "cockpit" / "src"
if str(cockpit_src) not in sys.path:
    sys.path.insert(0, str(cockpit_src))

from cockpit.delivery_journey import build_delivery_journey_projection, DeliveryStage
from cockpit.web.api_delivery_journey import router


def test_e2e_fixture_four_states_transitions():
    """Verify state transitions across PENDING -> RUNNING -> VERIFIED -> MERGED."""
    fixtures_order = ["PENDING", "RUNNING", "VERIFIED", "MERGED"]
    
    for fixture_name in fixtures_order:
        data = build_delivery_journey_projection(fixture_state=fixture_name)
        assert data.id == f"fixture-{fixture_name.lower()}-101" or "fixture-" in data.id
        assert data.status == "live"
        assert len(data.source) > 0
        assert len(data.stages) == 7
        assert data.scene_binding["scene_id"] == "engineering-delivery"
        assert data.scene_binding["journey_id"] == "intent-to-evidence"

        # Ensure all 7 stages exist
        for k in ["intent", "task", "run", "worktree", "verification", "pr", "evidence"]:
            assert k in data.stages
            stage = data.stages[k]
            assert stage["name"] == k
            assert stage["status"] in ["verified", "running", "pending", "failed", "merged", "open"]


def test_e2e_fixture_pending_properties():
    """Check specific semantics of PENDING fixture state."""
    data = build_delivery_journey_projection(fixture_state="PENDING")
    assert data.stages["run"]["status"] == "pending"
    assert data.stages["verification"]["status"] == "pending"
    assert data.stages["pr"]["status"] == "pending"


def test_e2e_fixture_merged_properties():
    """Check specific semantics of MERGED fixture state."""
    data = build_delivery_journey_projection(fixture_state="MERGED")
    assert data.stages["intent"]["status"] == "verified"
    assert data.stages["run"]["status"] == "verified"
    assert data.stages["worktree"]["status"] == "verified"
    assert data.stages["pr"]["status"] in ["open", "merged"]
    assert data.stages["evidence"]["status"] == "verified"


def test_e2e_fixture_unavailable_degradation():
    """Verify explicit degradation without fake greens when data is unavailable."""
    data = build_delivery_journey_projection(fixture_state="UNAVAILABLE")
    assert data.status == "unavailable"
    assert "Unavailable" in data.title
    
    for k, stage in data.stages.items():
        assert stage["status"] == "unavailable"
        assert "Unavailable" in stage["title"] or "降级" in stage["title"]


def test_e2e_fixture_exposes_next_action_and_mode():
    """Product consumers get an explicit mode and next action, not only technical stages."""
    pending = build_delivery_journey_projection(fixture_state="PENDING")
    merged = build_delivery_journey_projection(fixture_state="MERGED")

    assert pending.mode == "active"
    assert pending.next_action
    assert merged.mode == "completed"
    assert "复盘" in merged.next_action


def test_e2e_api_endpoint_four_states_integration():
    """Simulate E2E endpoint calls for four states plus unavailable degradation."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    for fixture in ["PENDING", "RUNNING", "VERIFIED", "MERGED", "UNAVAILABLE"]:
        response = client.get(f"/api/delivery-journey?fixture={fixture}")
        assert response.status_code == 200
        data = response.json()
        assert "journey" in data
        journey = data["journey"]
        if fixture == "UNAVAILABLE":
            assert data["ok"] is False
            assert journey["status"] == "unavailable"
        else:
            assert data["ok"] is True
            assert journey["status"] == "live"
            assert len(journey["stages"]) == 7
