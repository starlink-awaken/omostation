from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_scene_cards


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_scene_cards.router)
    return app


def _candidate_projection() -> dict:
    return {
        "schema": "scene-card-candidate/v1",
        "mode": "candidate_only",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "candidates": [
            {
                "candidate_id": "scene-candidate:test",
                "title": "测试场景",
                "proposed_scene_id": "test-scene",
                "proposed_journey_id": "test-journey",
                "outcome_metric_hint": "verified_outcome",
                "discovery_refs": ["docs/test.md#scene"],
                "capability_refs": ["external:test"],
                "safe_observations": ["需要业务确认"],
                "activation_evidence_refs": [],
                "sample_refs": [],
                "demand_evidence_refs": [],
                "opportunity_window": "",
                "missing_activation_fields": ["owner"],
            }
        ],
        "summary": {
            "candidate_count": 1,
            "activation_eligible_count": 0,
            "requires_business_confirmation_count": 1,
        },
    }


def test_scene_cards_returns_candidate_only_projection(monkeypatch, tmp_path):
    projection = _candidate_projection()
    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_scene_cards, "collect_candidates", lambda root: projection)

    response = TestClient(_app()).get("/api/scene-cards")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "live", "projection": projection}


def test_scene_cards_review_approve_is_blocked_and_does_not_activate(monkeypatch, tmp_path):
    projection = _candidate_projection()
    calls: list[dict] = []

    def fake_review(payload, **kwargs):
        calls.append({"payload": payload, **kwargs})
        return {
            "schema": "scene-card-review/v1",
            "review_id": "review:test",
            "candidate_id": kwargs["candidate_id"],
            "decision": kwargs["decision"],
            "status": "blocked",
            "reason": "scene_card_incomplete",
            "next_action": "complete_scene_card_and_submit_evidence",
            "activation": "forbidden",
            "activation_attempted": False,
            "note_digest": "sha256:test",
        }

    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_scene_cards, "collect_candidates", lambda root: projection)
    monkeypatch.setattr(api_scene_cards, "create_review_receipt", fake_review)

    response = TestClient(_app()).post(
        "/api/scene-cards/review",
        json={
            "candidate_id": "scene-candidate:test",
            "decision": "approve",
            "reviewer_ref": "business://owner",
            "note": "材料待补",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["receipt"]["status"] == "blocked"
    assert body["activation"] == "forbidden"
    assert body["activation_attempted"] is False
    assert body["persistence"] == "none"
    assert calls[0]["note"] == "材料待补"


def test_scene_cards_review_rejects_missing_candidate_id(monkeypatch):
    response = TestClient(_app()).post("/api/scene-cards/review", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "invalid"
    assert response.json()["activation"] == "forbidden"


def test_scene_cards_degrades_when_candidate_discovery_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)

    def fail_discovery(*_args, **_kwargs):
        raise RuntimeError("candidate source unavailable")

    monkeypatch.setattr(api_scene_cards, "collect_candidates", fail_discovery)
    response = TestClient(_app()).get("/api/scene-cards")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["projection"]["activation"] == "forbidden"
