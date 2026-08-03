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
        "candidates": [
            {
                "resource_id": "source:test",
                "capability": "search",
                "status": "eligible",
                "reasons": [],
                "decision_factors": {"health": "healthy"},
                "rank": [1, "source:test"],
                "availability": "available",
                "provenance_ref": "evidence://source/test",
            }
        ],
        "reasons": [],
        "summary": {"candidate_count": 1, "eligible_count": 1, "rejected_count": 0, "not_applicable_count": 0},
    }


def _pack() -> dict:
    return {
        "schema": "external-resource-pack/v1",
        "pack_id": "pack:research",
        "pack_version": "1.0.0",
        "activation": "forbidden",
        "extension": {
            "entry_point_group": "external.resources",
            "entry_point": "research",
            "provider_method": "external_descriptor",
            "health_probe": {
                "method": "health_probe",
                "side_effect": "read_only",
                "required": True,
            },
        },
        "descriptor": {
            "id": "source:research",
            "kind": "knowledge_source",
            "provider": "research-provider",
            "protocol": "external-resource/v1",
            "capabilities": ["discover", "search"],
            "data_classification": "public",
            "provenance": {"source_ref": "evidence://research/provider"},
            "lifecycle": "sandbox",
            "health": {
                "status": "healthy",
                "observed_at": "2026-08-03T00:00:00+00:00",
                "latency_ms": 10,
                "source": "probe:research",
            },
            "owner": "owner:research",
            "version": "1.0.0",
            "permission_ref": "permission://research/read",
            "mode": "live_query",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "rollback_plan": "disable provider",
        },
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


def test_external_resource_refresh_persists_governed_observation_receipts(monkeypatch, tmp_path):
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_observe(root, **kwargs):
        calls.append((root, kwargs))
        return {
            "schema": "external-resource-observation-result/v1",
            "status": "recorded",
            "observation_run_status": "recorded",
            "catalog": {"summary": {"resource_count": 2}},
            "observation": {
                "observation_id": "external-resource-observation:test",
                "change_summary": {"review_required": False, "risk_codes": []},
            },
            "observation_run": {"receipt_id": "external-observation-run:test"},
        }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "observe_external_resources", fake_observe)

    response = TestClient(_app()).post(
        "/api/external-resources/refresh",
        json={"actor_ref": "human:test", "run_id": "run:test", "probe": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["persistence"] == "omo_append_only"
    assert payload["activation"] == "forbidden"
    assert payload["provider_invocation"] is False
    assert payload["workflow_run_creation"] is False
    assert calls == [
        (
            tmp_path,
            {
                "actor": "human:test",
                "source_ref": "cockpit:external-resources:refresh",
                "run_id": "run:test",
                "probe": True,
            },
        )
    ]


def test_external_resource_refresh_rejects_unknown_fields_without_observing(monkeypatch, tmp_path):
    called = False

    def fail_observe(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "observe_external_resources", fail_observe)

    response = TestClient(_app()).post(
        "/api/external-resources/refresh",
        json={"activation": "live"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["activation"] == "forbidden"
    assert called is False


def test_external_resource_refresh_status_exposes_stale_recovery_state(monkeypatch, tmp_path):
    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_external_resources,
        "read_latest_external_resource_observation",
        lambda _path: {
            "schema": "external-resource-observation/v1",
            "observation_id": "external-resource-observation:stale",
            "observed_at": "2020-01-01T00:00:00Z",
            "recorded_at": "2020-01-01T00:00:01Z",
            "change_state": "unchanged",
            "change_summary": {"review_required": False, "risk_codes": []},
            "catalog": {
                "schema": "external-resource-catalog/v1",
                "observed_at": "2020-01-01T00:00:00Z",
                "catalog_ttl_seconds": 3600,
            },
        },
    )

    response = TestClient(_app()).get("/api/external-resources/refresh-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["projection"]["freshness"] == "stale"
    assert "受治理刷新" in payload["projection"]["next_action"]
    assert payload["projection"]["provider_invocation"] is False


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


def test_external_resource_directory_prefers_latest_observed_catalog(monkeypatch, tmp_path):
    catalog = _projection()
    directory = {
        "schema": "external-resource-directory/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "summary": {
            "resource_count": 1,
            "available_count": 1,
            "capability_count": 1,
        },
    }
    calls: list[dict] = []

    def fake_builder(received):
        calls.append(received)
        return directory

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_external_resources,
        "read_latest_external_resource_observation",
        lambda _path: {"schema": "external-resource-observation/v1", "catalog": catalog},
    )
    monkeypatch.setattr(api_external_resources, "build_external_resource_directory_snapshot", fake_builder)
    monkeypatch.setattr(
        api_external_resources,
        "collect_external_resources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must use observation")),
    )

    response = TestClient(_app()).get("/api/external-resources/directory")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["source"] == "omo.external_resource_observation"
    assert body["projection"] == directory
    assert body["external_side_effects"] == "disabled"
    assert calls == [catalog]


def test_external_resource_directory_falls_back_to_safe_discovery(monkeypatch, tmp_path):
    catalog = _projection()
    directory = {
        "schema": "external-resource-directory/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "summary": {
            "resource_count": 0,
            "available_count": 0,
            "capability_count": 0,
        },
    }
    calls: list[object] = []

    def fake_discovery(root, *, probe):
        calls.append((root, probe))
        return catalog

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)
    monkeypatch.setattr(api_external_resources, "collect_external_resources", fake_discovery)
    monkeypatch.setattr(api_external_resources, "build_external_resource_directory_snapshot", lambda value: directory)

    response = TestClient(_app()).get("/api/external-resources/directory")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "attention"
    assert body["source"] == "agora.external_resource_discovery"
    assert body["projection"]["schema"] == "external-resource-directory/v1"
    assert calls == [(tmp_path, True)]


def test_external_resource_connection_plan_prefers_latest_observed_catalog(monkeypatch, tmp_path):
    catalog = _projection()
    directory = {"schema": "external-resource-directory/v1", "resources": []}
    plan = {
        "schema": "external-resource-connection-plan/v1",
        "summary": {"resource_count": 1, "blocked_count": 1},
        "items": [{"resource_id": "tool:ocr", "status": "blocked"}],
    }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_external_resources,
        "read_latest_external_resource_observation",
        lambda _path: {"schema": "external-resource-observation/v1", "catalog": catalog},
    )
    monkeypatch.setattr(
        api_external_resources,
        "collect_external_resources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("discovery should not run")),
    )
    monkeypatch.setattr(
        api_external_resources,
        "build_external_resource_directory_snapshot",
        lambda _value: directory,
    )
    monkeypatch.setattr(
        api_external_resources,
        "build_external_resource_connection_plan",
        lambda _value: plan,
    )

    response = TestClient(_app()).get("/api/external-resources/connection-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "attention"
    assert body["source"] == "omo.external_resource_observation"
    assert body["projection"] == plan
    assert body["external_side_effects"] == "disabled"
    assert body["worker_launch"] is False


def test_external_resource_connection_plan_uses_safe_discovery_fallback(monkeypatch, tmp_path):
    catalog = _projection()
    directory = {"schema": "external-resource-directory/v1", "resources": []}
    plan = {
        "schema": "external-resource-connection-plan/v1",
        "summary": {"resource_count": 0, "blocked_count": 0},
        "items": [],
    }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_external_resources,
        "read_latest_external_resource_observation",
        lambda _path: None,
    )
    monkeypatch.setattr(
        api_external_resources,
        "collect_external_resources",
        lambda *_args, **_kwargs: catalog,
    )
    monkeypatch.setattr(
        api_external_resources,
        "build_external_resource_directory_snapshot",
        lambda _value: directory,
    )
    monkeypatch.setattr(
        api_external_resources,
        "build_external_resource_connection_plan",
        lambda _value: plan,
    )

    response = TestClient(_app()).get("/api/external-resources/connection-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "empty"
    assert body["source"] == "agora.external_resource_discovery"


def test_external_resource_pack_preflight_is_read_only(monkeypatch, tmp_path):
    calls: list[tuple[object, dict]] = []
    projection = {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": "ready_for_catalog_preview",
        "reason_codes": [],
    }

    def fake_check(root, pack):
        calls.append((root, pack))
        return projection

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "check_external_resource_pack", fake_check)

    response = TestClient(_app()).post("/api/external-resources/packs/preflight", json={"pack": _pack()})
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "ready_for_catalog_preview"
    assert body["projection"] == projection
    assert body["activation"] == "forbidden"
    assert body["persistence"] == "none"
    assert body["provider_invocation"] is False
    assert body["external_side_effects"] == "disabled"
    assert calls == [(tmp_path, _pack())]


def test_external_resource_pack_preflight_exposes_unobserved_catalog_preview(monkeypatch, tmp_path):
    projection = {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": "ready_for_catalog_preview",
        "reason_codes": [],
        "catalog_preview": {
            "schema": "external-resource-pack-catalog-preview/v1",
            "mode": "read_only_pack_preview",
            "activation": "forbidden",
            "status": "ready_for_catalog_preview",
            "resource": {
                "id": "source:research",
                "availability": "unobserved",
                "health": {"status": "unobserved"},
            },
        },
    }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_external_resources,
        "check_external_resource_pack",
        lambda root, pack: projection,
    )

    response = TestClient(_app()).post("/api/external-resources/packs/preflight", json={"pack": _pack()})

    assert response.status_code == 200
    body = response.json()
    assert body["projection"]["catalog_preview"]["resource"]["availability"] == "unobserved"
    assert body["projection"]["catalog_preview"]["resource"]["health"]["status"] == "unobserved"
    assert body["activation"] == "forbidden"
    assert body["persistence"] == "none"
    assert body["provider_invocation"] is False


def test_external_resource_pack_preflight_returns_invalid_without_activation(monkeypatch):
    def reject(_root, _pack):
        raise api_external_resources.ExternalResourcePackError(
            "secret field is forbidden: pack.descriptor.metadata.token"
        )

    monkeypatch.setattr(api_external_resources, "check_external_resource_pack", reject)

    response = TestClient(_app()).post("/api/external-resources/packs/preflight", json={"pack": _pack()})
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["status"] == "invalid"
    assert body["error"] == "external_resource_pack_invalid"
    assert body["activation"] == "forbidden"
    assert body["persistence"] == "none"
    assert body["provider_invocation"] is False


def test_external_resource_pack_proposal_rechecks_and_persists_only_safe_projection(monkeypatch, tmp_path):
    calls: list[dict] = []
    projection = {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": "ready_for_catalog_preview",
        "reason_codes": [],
        "catalog_preview": {
            "schema": "external-resource-pack-catalog-preview/v1",
            "mode": "read_only_pack_preview",
            "activation": "forbidden",
            "status": "ready_for_catalog_preview",
            "resource": {
                "id": "source:research",
                "availability": "unobserved",
                "health": {"status": "unobserved"},
            },
        },
    }

    def fake_check(root, pack):
        calls.append({"kind": "check", "root": root, "pack": pack})
        return projection

    def fake_record(omo_dir, checked, **kwargs):
        calls.append({"kind": "record", "omo_dir": omo_dir, "projection": checked, **kwargs})
        return {"status": "recorded", "proposal": {"proposal_receipt_id": "receipt:pack-1"}}

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "check_external_resource_pack", fake_check)
    monkeypatch.setattr(api_external_resources, "record_external_resource_pack_proposal", fake_record)

    response = TestClient(_app()).post(
        "/api/external-resources/packs/proposals",
        json={
            "pack": _pack(),
            "proposal_id": "proposal:research:1",
            "actor_ref": "operator:test",
            "review_action": "submit",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["proposal_status"] == "ready_for_catalog_preview"
    assert body["proposal"]["proposal_receipt_id"] == "receipt:pack-1"
    assert body["activation"] == "forbidden"
    assert body["persistence"] == "omo_append_only"
    assert body["provider_invocation"] is False
    assert calls[0]["kind"] == "check"
    assert calls[1]["kind"] == "record"
    assert calls[1]["omo_dir"] == tmp_path / ".omo"
    assert calls[1]["proposal_id"] == "proposal:research:1"


def test_external_resource_pack_proposal_does_not_persist_blocked_pack(monkeypatch, tmp_path):
    calls: list[object] = []
    projection = {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": "blocked",
        "reason_codes": ["missing_permission_ref"],
    }

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "check_external_resource_pack", lambda *_args: projection)
    monkeypatch.setattr(
        api_external_resources,
        "record_external_resource_pack_proposal",
        lambda *_args, **_kwargs: calls.append(True),
    )

    response = TestClient(_app()).post(
        "/api/external-resources/packs/proposals",
        json={"pack": _pack(), "proposal_id": "proposal:blocked:1"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["status"] == "blocked"
    assert body["persistence"] == "none"
    assert body["provider_invocation"] is False
    assert calls == []


def test_external_resource_review_queue_projects_manual_review_delta_without_discovery(monkeypatch, tmp_path):
    calls: list[object] = []
    observation = {
        "schema": "external-resource-observation/v1",
        "observation_id": "observation:test",
        "observed_at": "2026-08-03T00:00:00Z",
        "recorded_at": "2026-08-03T00:01:00Z",
        "change_state": "changed",
        "catalog": {
            "schema": "external-resource-catalog/v1",
            "changes": {
                "schema": "external-resource-catalog-diff/v1",
                "changes": [
                    {
                        "id": "source:test",
                        "change": "changed",
                        "review_required": True,
                        "risk_class": "manual_review",
                        "risk_codes": ["descriptor_provider_changed"],
                        "changed_fields": ["provider"],
                        "previous": {
                            "provider": "old-provider",
                            "content": "must not leak",
                        },
                        "current": {
                            "provider": "new-provider",
                            "version": "2.0.0",
                        },
                    },
                    {
                        "id": "source:health",
                        "change": "changed",
                        "review_required": False,
                        "risk_class": "operational_observation",
                        "risk_codes": ["health_changed"],
                        "changed_fields": ["health"],
                    },
                ],
            },
        },
    }

    def fake_latest(omo_dir):
        calls.append(omo_dir)
        return observation

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", fake_latest)
    monkeypatch.setattr(
        api_external_resources,
        "collect_external_resources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("discovery must not run")),
    )

    response = TestClient(_app()).get("/api/external-resources/review-queue")
    body = response.json()
    projection = body["projection"]

    assert response.status_code == 200
    assert body["ok"] is True
    assert projection["schema"] == "external-resource-review-queue/v1"
    assert projection["status"] == "attention"
    assert projection["summary"] == {
        "review_required_count": 1,
        "operational_observation_count": 1,
        "risk_codes": ["descriptor_provider_changed", "health_changed"],
    }
    assert projection["items"][0]["resource_id"] == "source:test"
    assert projection["items"][0]["current"] == {
        "provider": "new-provider",
        "version": "2.0.0",
    }
    assert "content" not in projection["items"][0]["previous"]
    assert projection["activation"] == "forbidden"
    assert body["external_side_effects"] == "disabled"
    assert body["worker_launch"] is False
    assert calls == [tmp_path / ".omo"]


def test_external_resource_review_queue_is_empty_before_first_observation(monkeypatch):
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)

    response = TestClient(_app()).get("/api/external-resources/review-queue")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["projection"]["status"] == "empty"
    assert body["projection"]["items"] == []
    assert body["projection"]["activation"] == "forbidden"


def test_external_resource_review_queue_fails_closed_on_invalid_observation(monkeypatch):
    monkeypatch.setattr(
        api_external_resources,
        "read_latest_external_resource_observation",
        lambda _path: {"schema": "unexpected"},
    )

    response = TestClient(_app()).get("/api/external-resources/review-queue")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["projection"]["status"] == "unavailable"
    assert body["projection"]["activation"] == "forbidden"
    assert body["external_side_effects"] == "disabled"


def _scene_trial(trial_id: str = "scene-trial:test") -> dict:
    return {
        "schema": "external-scene-trial/v1",
        "trial_id": trial_id,
        "scene_binding": {
            "scene_id": "research-brief",
            "journey_id": "weekly-decision",
            "outcome_metric": "decision_latency_hours",
        },
        "consumer_ref": "ref://consumer/test",
        "owner_ref": "ref://owner/test",
        "approver_ref": "ref://approver/test",
        "permission_ref": "ref://permission/test",
        "evidence_refs": ["evidence://demand/test", "evidence://activation/test"],
        "preflight_ref": "ref://preflight/test",
        "catalog_observation_id": "observation:test",
        "trial_stage": "observation_only",
        "status": "proposal_only",
        "metric": {"metric_id": "decision_latency_hours", "direction": "decrease"},
        "sample_plan": {"minimum_samples": 3, "window_seconds": 3600},
        "rollback_ref": "ref://rollback/test",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "feedback_contract": {"schema": "outcome-feedback/v1"},
        "observed_at": "2026-08-03T00:00:00Z",
        "trial_receipt_id": "receipt:test",
    }


def test_external_scene_trial_review_projection_is_read_only(monkeypatch):
    monkeypatch.setattr(api_external_resources, "read_external_scene_trials", lambda _path: [_scene_trial()])
    monkeypatch.setattr(api_external_resources, "read_external_scene_trial_feedback", lambda _path: [])

    response = TestClient(_app()).get("/api/external-resources/scene-trials?scene_id=research-brief")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["projection"]["status"] == "attention"
    assert body["projection"]["summary"]["unreviewed_count"] == 1
    assert body["projection"]["items"][0]["trial_id"] == "scene-trial:test"
    assert body["projection"]["activation"] == "forbidden"
    assert body["projection"]["workflow_run_creation"] == "forbidden"


def test_external_scene_trial_review_records_proposal_only_receipt(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_record(root, payload):
        calls.append({"root": root, "payload": payload})
        return {"status": "recorded", "feedback": {"feedback_id": payload["feedback_id"]}}

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "record_external_scene_trial_feedback", fake_record)
    response = TestClient(_app()).post(
        "/api/external-resources/scene-trials/review",
        json={
            "feedback_id": "review:test",
            "trial_id": "scene-trial:test",
            "review_action": "continue",
            "evidence_refs": ["evidence://review/test"],
            "reviewer_ref": "ref://reviewer/test",
            "review_ref": "ref://review/test",
            "actor_ref": "cockpit:test",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["activation"] == "forbidden"
    assert body["provider_invocation"] is False
    assert body["workflow_run_creation"] == "forbidden"
    assert calls[0]["root"] == tmp_path / ".omo"
    assert calls[0]["payload"]["schema"] == "external-scene-trial-feedback/v1"
    assert calls[0]["payload"]["workflow_run_id"] is None


def test_external_scene_trial_readiness_is_read_only_and_preserves_blockers(monkeypatch, tmp_path):
    projection = {
        "schema": "external-scene-trial-promotion-readiness/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": "forbidden",
        "admission_mutation": "forbidden",
        "external_side_effects": "disabled",
        "status": "blocked",
        "items": [{"trial_id": "scene-trial:test", "blockers": ["workflow_run_missing"]}],
        "summary": {"trial_count": 1, "ready_count": 0, "blocked_count": 1},
        "next_action": "补齐阻断项后重新评估",
    }
    monkeypatch.setattr(
        api_external_resources,
        "build_external_scene_trial_promotion_readiness",
        lambda root, scene_id=None: projection,
    )
    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)

    response = TestClient(_app()).get("/api/external-resources/scene-trials/readiness?scene_id=research-brief")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["projection"]["status"] == "blocked"
    assert body["projection"]["items"][0]["blockers"] == ["workflow_run_missing"]
    assert body["activation"] == "forbidden"
    assert body["provider_invocation"] is False
    assert body["workflow_run_creation"] == "forbidden"
    assert body["admission_mutation"] == "forbidden"
    assert body["worker_launch"] is False


def test_external_resource_evaluation_returns_explainable_read_only_decision(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[dict] = []

    def fake_evaluate(root, snapshot, *, capability, scene_binding, trace_id, now=None):
        calls.append(
            {
                "root": root,
                "snapshot": snapshot,
                "capability": capability,
                "scene_binding": scene_binding,
                "trace_id": trace_id,
            }
        )
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
    monkeypatch.setattr(
        api_external_resources, "read_latest_external_resource_observation", lambda _path: {"catalog": projection}
    )
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
    monkeypatch.setattr(
        api_external_resources, "read_latest_external_resource_observation", lambda _path: {"catalog": _projection()}
    )
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

    response = TestClient(_app()).get("/api/external-resources/evaluations/selection?scene_id=research-brief")
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
    monkeypatch.setattr(
        api_external_resources, "build_external_resource_selection_dataset", lambda *_args, **_kwargs: dataset
    )
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
