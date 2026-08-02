from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_external_resources


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_external_resources.router)
    return app


def _projection() -> dict:
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": "2026-08-03T00:00:00Z",
        "health_ttl_seconds": 900,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [],
        "errors": [],
        "summary": {
            "resource_count": 0,
            "unavailable_count": 0,
            "error_count": 0,
            "by_kind": {},
            "by_availability": {},
        },
    }


def _evaluation() -> dict:
    return {
        "schema": "external-resource-evaluation/v1",
        "mode": "read_only_evaluation",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "capability": "search",
        "trace_id": "trace:test",
        "policy_digest": "external-connection-fabric/v1",
        "scene_binding": {
            "scene_id": "research-brief",
            "journey_id": "weekly-decision",
            "outcome_metric": "decision_latency_hours",
            "data_scope": "public:research",
            "operator": "human:test",
            "permission_ref": "permission://test",
        },
        "status": "selected",
        "selected_resource_id": "source:test",
        "candidates": [{
            "resource_id": "source:test",
            "capability": "search",
            "status": "eligible",
            "reasons": [],
            "decision_factors": {"health": "healthy"},
            "rank": [1, "source:test"],
            "availability": "available",
            "provenance_ref": "evidence://source/test",
        }],
        "reasons": [],
        "summary": {"candidate_count": 1, "eligible_count": 1, "rejected_count": 0, "not_applicable_count": 0},
    }


def test_external_resources_prefers_latest_omo_observation(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[object] = []

    def fake_latest(omo_dir):
        calls.append(omo_dir)
        return {"schema": "external-resource-observation/v1", "catalog": projection}

    def fail_discovery(*_args, **_kwargs):
        raise AssertionError("latest governed observation should win")

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", fake_latest)
    monkeypatch.setattr(api_external_resources, "collect_external_resources", fail_discovery)

    response = TestClient(_app()).get("/api/external-resources")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["source"] == "omo.external_resource_observation"
    assert response.json()["projection"] == projection
    assert response.json()["external_side_effects"] == "disabled"
    assert calls == [tmp_path / ".omo"]


def test_external_resources_falls_back_to_safe_discovery(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[tuple[object, bool]] = []

    def fake_discovery(root, *, probe):
        calls.append((root, probe))
        return projection

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)
    monkeypatch.setattr(api_external_resources, "collect_external_resources", fake_discovery)

    response = TestClient(_app()).get("/api/external-resources")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["source"] == "agora.external_resource_discovery"
    assert calls == [(tmp_path, True)]


def test_external_resources_fails_closed_when_discovery_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)

    def fail_discovery(*_args, **_kwargs):
        raise RuntimeError("provider boundary unavailable")

    monkeypatch.setattr(api_external_resources, "collect_external_resources", fail_discovery)

    response = TestClient(_app()).get("/api/external-resources")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["status"] == "unavailable"
    assert body["projection"]["activation"] == "forbidden"
    assert body["external_side_effects"] == "disabled"
    assert body["worker_launch"] is False


def test_external_resource_evaluation_returns_explainable_read_only_decision(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[dict] = []

    def fake_evaluate(root, snapshot, *, capability, scene_binding, trace_id, now=None):
        calls.append({
            "root": root,
            "snapshot": snapshot,
            "capability": capability,
            "scene_binding": scene_binding,
            "trace_id": trace_id,
        })
        return {
            "schema": "external-resource-evaluation/v1",
            "mode": "read_only_evaluation",
            "activation": "forbidden",
            "status": "unavailable",
            "selected_resource_id": None,
            "candidates": [],
            "reasons": ["no_eligible_candidate"],
            "summary": {"candidate_count": 0, "eligible_count": 0, "rejected_count": 0, "not_applicable_count": 0},
        }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: {"catalog": projection})
    monkeypatch.setattr(api_external_resources, "evaluate_external_resources", fake_evaluate)

    response = TestClient(_app()).post(
        "/api/external-resources/evaluate",
        json={
            "capability": "search",
            "scene_binding": {
                "scene_id": "research-brief",
                "journey_id": "weekly-decision",
                "outcome_metric": "decision_latency_hours",
                "data_scope": "public:research",
                "operator": "human:test",
                "permission_ref": "permission://test",
            },
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "unavailable"
    assert body["evaluation"]["activation"] == "forbidden"
    assert body["external_side_effects"] == "disabled"
    assert body["worker_launch"] is False
    assert calls[0]["capability"] == "search"
    assert calls[0]["scene_binding"]["scene_id"] == "research-brief"
    assert calls[0]["trace_id"].startswith("cockpit:external-evaluation:")


def test_external_resource_evaluation_rejects_missing_scene_binding(monkeypatch):
    response = TestClient(_app()).post(
        "/api/external-resources/evaluate",
        json={"capability": "search"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "invalid"
    assert response.json()["activation"] == "forbidden"


def test_external_resource_evaluation_persists_only_when_explicitly_requested(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_evaluate(*_args, **_kwargs):
        return _evaluation()

    def fake_record(omo_dir, evaluation, **kwargs):
        calls.append({"omo_dir": omo_dir, "evaluation": evaluation, **kwargs})
        return {"status": "recorded", "observation": {"observation_id": "observation-1"}}

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: {"catalog": _projection()})
    monkeypatch.setattr(api_external_resources, "evaluate_external_resources", fake_evaluate)
    monkeypatch.setattr(api_external_resources, "record_external_resource_evaluation", fake_record)

    response = TestClient(_app()).post(
        "/api/external-resources/evaluate",
        json={
            "capability": "search",
            "scene_binding": _evaluation()["scene_binding"],
            "persist_observation": True,
            "workflow_run_id": "run-test",
            "actor_ref": "operator:test",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["observation_status"] == "recorded"
    assert body["observation_persisted"] is True
    assert calls[0]["omo_dir"] == tmp_path / ".omo"
    assert calls[0]["workflow_run_id"] == "run-test"
    assert calls[0]["actor"] == "operator:test"


def test_selection_evaluation_projection_is_read_only(monkeypatch, tmp_path):
    dataset = {"dataset_version": "external-resource-selection-eval/v1", "rows": [], "summary": {"row_count": 0}}
    calls: list[object] = []

    def fake_dataset(omo_dir, *, scene_id=None):
        calls.append((omo_dir, scene_id))
        return dataset

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "build_external_resource_selection_dataset", fake_dataset)

    response = TestClient(_app()).get(
        "/api/external-resources/evaluations/selection?scene_id=research-brief"
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "live"
    assert body["dataset"] == dataset
    assert body["activation"] == "forbidden"
    assert calls == [(tmp_path / ".omo", "research-brief")]


def test_selection_policy_proposal_never_applies_policy(monkeypatch, tmp_path):
    dataset = {"dataset_version": "external-resource-selection-eval/v1", "rows": [], "summary": {"row_count": 0}}
    proposal = {"proposal_id": "proposal-1", "status": "proposal_only", "not_applied": True}

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "build_external_resource_selection_dataset", lambda *_args, **_kwargs: dataset)
    monkeypatch.setattr(api_external_resources, "propose_selection_policy_feedback", lambda *_args, **_kwargs: proposal)

    response = TestClient(_app()).post(
        "/api/external-resources/evaluations/proposal",
        json={"proposal_id": "proposal-1", "candidate": {"max_unaligned_rate": 0.2}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "proposal_only"
    assert body["proposal"]["not_applied"] is True
    assert body["external_side_effects"] == "disabled"
