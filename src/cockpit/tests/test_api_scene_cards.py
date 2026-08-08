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


def test_scene_cards_intake_returns_proposal_only_projection(monkeypatch):
    projection = {
        "schema": "scene-card-intake/v1",
        "mode": "proposal_only_intake",
        "status": "proposal_only",
        "activation": "forbidden",
        "next_action": "run_external_activation_preflight",
        "side_effects": {
            "raw_content_read": False,
            "provider_called": False,
            "omo_written": False,
            "workflow_created": False,
            "activation_attempted": False,
        },
    }
    calls: list[dict] = []

    def fake_intake(scene_card):
        calls.append(scene_card)
        return projection

    monkeypatch.setattr(api_scene_cards, "build_intake", fake_intake)
    response = TestClient(_app()).post(
        "/api/scene-cards/intake",
        json={"scene_card": {"schema": "scene-card/v1", "scene_id": "research-brief"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "proposal_only",
        "projection": projection,
        "activation": "forbidden",
        "activation_attempted": False,
        "persistence": "none",
    }
    assert calls == [{"schema": "scene-card/v1", "scene_id": "research-brief"}]


def test_scene_cards_intake_rejects_invalid_payload(monkeypatch):
    def fail_intake(_scene_card):
        raise ValueError("scene card contains forbidden field: raw_content")

    monkeypatch.setattr(api_scene_cards, "build_intake", fail_intake)
    response = TestClient(_app()).post("/api/scene-cards/intake", json={"scene_card": {"raw_content": "secret"}})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "invalid"
    assert response.json()["activation"] == "forbidden"
    assert response.json()["persistence"] == "none"


def test_scene_cards_preflight_uses_latest_omo_catalog(monkeypatch):
    scene_card = {"schema": "scene-card/v1", "scene_id": "research-brief"}
    intake = {
        "status": "proposal_only",
        "missing_fields": [],
        "scene_card": {
            "scene_id": "research-brief",
            "journey_id": "question-to-brief",
            "outcome_metric": "verified_brief_acceptance",
            "sample_refs": ["sample://1", "sample://2", "sample://3"],
            "demand_evidence_refs": ["evidence://demand"],
            "activation_evidence_refs": ["evidence://approval"],
            "required_capabilities": ["source.research"],
        },
    }
    catalog = {"schema": "external-resource-catalog/v1", "observed_at": "now"}
    calls: list[dict] = []

    def fake_intake(card):
        calls.append({"kind": "intake", "card": card})
        return intake

    def fake_preflight(card, received_catalog):
        calls.append({"kind": "preflight", "card": card, "catalog": received_catalog})
        return {
            "schema": "external-activation-preflight/v1",
            "status": "proposal_only",
            "activation": "forbidden",
            "next_action": "replace_proposal_only_capabilities_before_admission",
        }

    monkeypatch.setattr(api_scene_cards, "build_intake", fake_intake)
    monkeypatch.setattr(api_scene_cards, "build_preflight", fake_preflight)
    monkeypatch.setattr(api_scene_cards, "_latest_catalog", lambda: catalog)

    response = TestClient(_app()).post("/api/scene-cards/preflight", json=scene_card)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "proposal_only"
    assert body["catalog_source"] == "omo.external_resource_observation"
    assert body["activation"] == "forbidden"
    assert body["persistence"] == "none"
    assert calls == [
        {"kind": "intake", "card": scene_card},
        {"kind": "preflight", "card": scene_card, "catalog": catalog},
    ]


def test_scene_cards_preflight_blocks_without_omo_catalog(monkeypatch):
    intake = {
        "status": "proposal_only",
        "missing_fields": [],
        "scene_card": {
            "scene_id": "research-brief",
            "journey_id": "question-to-brief",
            "outcome_metric": "verified_brief_acceptance",
            "sample_refs": [],
            "demand_evidence_refs": [],
            "activation_evidence_refs": [],
            "required_capabilities": [],
        },
    }
    monkeypatch.setattr(api_scene_cards, "build_intake", lambda _card: intake)
    monkeypatch.setattr(api_scene_cards, "_latest_catalog", lambda: None)

    response = TestClient(_app()).post("/api/scene-cards/preflight", json={"scene_card": {"schema": "scene-card/v1"}})

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["projection"]["missing_fields"] == ["catalog_observation"]
    assert body["projection"]["activation"] == "forbidden"


def test_scene_cards_preflight_rejects_forbidden_input(monkeypatch):
    monkeypatch.setattr(
        api_scene_cards,
        "build_intake",
        lambda _card: (_ for _ in ()).throw(ValueError("scene card contains forbidden field: raw_content")),
    )

    response = TestClient(_app()).post("/api/scene-cards/preflight", json={"scene_card": {"raw_content": "secret"}})

    assert response.json()["ok"] is False
    assert response.json()["status"] == "invalid"
    assert response.json()["activation"] == "forbidden"


def test_scene_cards_task_handoff_creates_idempotent_planned_task(monkeypatch, tmp_path):
    scene_card = {
        "schema": "scene-card/v1",
        "scene_id": "research-brief",
        "journey_id": "question-to-brief",
    }
    intake = {
        "status": "proposal_only",
        "intake_id": "scene-intake:research-brief:test",
        "source_digest": "sha256:scene-card",
        "scene_card": {
            "scene_id": "research-brief",
            "journey_id": "question-to-brief",
            "outcome_metric": "verified_brief_acceptance",
        },
    }
    created: list[dict] = []

    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_scene_cards, "build_intake", lambda _card: intake)
    monkeypatch.setattr(
        api_scene_cards,
        "_latest_catalog",
        lambda: {"schema": "external-resource-catalog/v1"},
    )
    monkeypatch.setattr(
        api_scene_cards,
        "build_preflight",
        lambda _card, _catalog: {
            "status": "ready_for_admission_preview",
            "next_action": "submit_omo_admission_preview",
            "scene": {
                "scene_id": "research-brief",
                "journey_id": "question-to-brief",
                "outcome_metric": "verified_brief_acceptance",
            },
        },
    )

    def fake_create(_omo_dir, *, task_data, **_kwargs):
        created.append(task_data)
        return task_data

    monkeypatch.setattr(api_scene_cards, "create_planned_task", fake_create)

    response = TestClient(_app()).post(
        "/api/scene-cards/task",
        json={"scene_card": scene_card, "risk_level": "L1"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "created"
    assert body["projection"]["schema"] == "scene-card-task/v1"
    assert body["projection"]["scene_binding"] == {
        "scene_id": "research-brief",
        "journey_id": "question-to-brief",
        "outcome_metric": "verified_brief_acceptance",
    }
    assert body["projection"]["side_effects"] == {
        "provider_called": False,
        "workflow_created": False,
        "worker_launch": False,
        "activation_attempted": False,
    }
    assert created[0]["metadata"]["scene_binding"]["scene_id"] == "research-brief"
    assert "goal" not in created[0]["metadata"]


def test_scene_cards_task_handoff_blocks_before_omo_write(monkeypatch, tmp_path):
    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_scene_cards,
        "build_intake",
        lambda _card: {
            "status": "proposal_only",
            "intake_id": "scene-intake:test",
            "source_digest": "sha256:test",
            "scene_card": {
                "scene_id": "test-scene",
                "journey_id": "test-journey",
                "outcome_metric": "test_metric",
            },
        },
    )
    monkeypatch.setattr(api_scene_cards, "_latest_catalog", lambda: {"schema": "catalog"})
    monkeypatch.setattr(
        api_scene_cards,
        "build_preflight",
        lambda _card, _catalog: {
            "status": "proposal_only",
            "next_action": "replace_proposal_only_capabilities_before_admission",
            "missing_fields": ["capability_health"],
            "scene": {"scene_id": "test-scene", "journey_id": "test-journey", "outcome_metric": "test_metric"},
        },
    )

    def create(*_args, **_kwargs):
        raise AssertionError("must not write")

    monkeypatch.setattr(api_scene_cards, "create_planned_task", create)

    response = TestClient(_app()).post(
        "/api/scene-cards/task",
        json={"scene_card": {"schema": "scene-card/v1"}},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "blocked"
    assert body["projection"]["blockers"] == ["capability_health"]
    assert body["persistence"] == "none"


def test_scene_cards_degrades_when_candidate_discovery_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(api_scene_cards, "_REPO_ROOT", tmp_path)

    def fail_discovery(*_args, **_kwargs):
        raise RuntimeError("candidate source unavailable")

    monkeypatch.setattr(api_scene_cards, "collect_candidates", fail_discovery)
    response = TestClient(_app()).get("/api/scene-cards")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["projection"]["activation"] == "forbidden"
