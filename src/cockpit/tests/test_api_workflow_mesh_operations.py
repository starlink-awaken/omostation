from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_workflow_mesh_operations


def test_capability_health_api_projects_server_owned_agora_evidence(monkeypatch):
    async def fake_health(required_capabilities):
        assert required_capabilities == ["runtime", "ocr"]
        return {
            "status": "healthy",
            "source": "agora.workflow_health",
            "observed_at": "2026-08-03T00:00:00Z",
            "required_capabilities": required_capabilities,
            "capabilities": {},
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_read_capability_health", fake_health)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).get(
        "/api/workflow-mesh/capability-health?required_capabilities=runtime&required_capabilities=ocr"
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "healthy",
        "source": "agora.workflow_health",
        "observed_at": "2026-08-03T00:00:00Z",
        "required_capabilities": ["runtime", "ocr"],
        "capability_health": {
            "status": "healthy",
            "source": "agora.workflow_health",
            "observed_at": "2026-08-03T00:00:00Z",
            "required_capabilities": ["runtime", "ocr"],
            "capabilities": {},
        },
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


def test_capability_health_api_fails_closed_when_agora_is_unavailable(monkeypatch):
    async def fail_health(_required_capabilities):
        raise RuntimeError("offline")

    monkeypatch.setattr(api_workflow_mesh_operations, "_read_capability_health", fail_health)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).get("/api/workflow-mesh/capability-health?required_capabilities=runtime")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["external_side_effects"] == "disabled"
    assert response.json()["worker_launch"] is False


def test_capability_health_api_rejects_empty_capabilities():
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).get("/api/workflow-mesh/capability-health")

    assert response.status_code == 200
    assert response.json()["error"] == "required_capabilities_required"


def test_workflow_mesh_operations_api_is_read_only_projection(monkeypatch, tmp_path):
    projection = {
        "schema_version": "workflow-mesh-operations/v1",
        "status": "live",
        "summary": {"run_count": 2, "active_runs": 1},
        "review_queue": [],
        "consumption": {"status": "not_observed", "consumed_runs": 0},
    }
    calls: list[tuple[object, str | None]] = []

    def fake_build(omo_dir, *, scene_id=None):
        calls.append((omo_dir, scene_id))
        return projection

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_operations_snapshot", fake_build)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    response = TestClient(app).get("/api/workflow-mesh/operations?scene_id=engineering-delivery")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "live", "operations": projection}
    assert calls == [(tmp_path / ".omo", "engineering-delivery")]


def test_workflow_mesh_operations_excludes_dedicated_review_scene_from_generic_feedback(monkeypatch, tmp_path):
    projection = {
        "schema_version": "workflow-mesh-operations/v1",
        "status": "live",
        "consumption": {
            "eligible_outcomes": [
                {
                    "workflow_run_id": "run-engineering",
                    "outcome_id": "outcome:run-engineering",
                    "scene_binding": {"scene_id": "engineering-delivery"},
                },
                {
                    "workflow_run_id": "run-generic",
                    "outcome_id": "outcome:run-generic",
                    "scene_binding": {"scene_id": "documentation"},
                },
            ]
        },
    }
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "build_operations_snapshot",
        lambda *_args, **_kwargs: projection,
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).get("/api/workflow-mesh/operations")

    assert response.status_code == 200
    assert response.json()["operations"]["consumption"]["eligible_outcomes"] == [
        {
            "workflow_run_id": "run-generic",
            "outcome_id": "outcome:run-generic",
            "scene_binding": {"scene_id": "documentation"},
        }
    ]
    assert response.json()["operations"]["consumption"]["dedicated_review_scenes"] == ["engineering-delivery"]


def test_workflow_mesh_operations_api_degrades_without_omo(monkeypatch):
    monkeypatch.setattr(api_workflow_mesh_operations, "build_operations_snapshot", None)
    monkeypatch.setattr(api_workflow_mesh_operations, "_OMO_IMPORT_ERROR", ImportError("missing omo"))

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    response = TestClient(app).get("/api/workflow-mesh/operations")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["operations"]["status"] == "unavailable"


def test_engineering_delivery_review_queue_is_read_only_projection(monkeypatch, tmp_path):
    calls: list[tuple[object, str | None]] = []
    projection = {
        "schema": "engineering-delivery-review-queue/v1",
        "summary": {"row_count": 1, "pending_review_count": 1},
        "rows": [{"delivery_id": "delivery-1", "review_status": "pending"}],
        "controls": {"read_only": True},
    }

    def fake_queue(omo_dir, *, workflow_run_id=None):
        calls.append((omo_dir, workflow_run_id))
        return projection

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "build_engineering_delivery_review_queue",
        fake_queue,
    )
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/test"),
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).get("/api/workflow-mesh/engineering-delivery/review-queue?workflow_run_id=run-1")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["projection"]["schema"] == "engineering-delivery-review-queue/v1"
    assert response.json()["projection"]["rows"] == [
        {
            "delivery_id": "delivery-1",
            "review_status": "pending",
            "scene_binding": {},
        }
    ]
    assert response.json()["projection"]["controls"]["value_indicator_policy"] is False
    assert calls == [(tmp_path / ".omo", "run-1")]


def test_engineering_delivery_review_api_forwards_only_review_fields(monkeypatch, tmp_path):
    captured: list[tuple[object, dict, str, str]] = []

    def fake_review(omo_dir, review, *, workflow_run_id, principal_assertion):
        captured.append((omo_dir, review, workflow_run_id, principal_assertion["principal_ref"]))
        return {
            "schema": "engineering-delivery-review/v1",
            "status": "recorded",
            "delivery_id": "delivery-1",
            "decision": "adopted",
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "record_engineering_delivery_review",
        fake_review,
    )
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/verified"),
    )
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "issue_engineering_review_assertion",
        lambda principal, _review: {
            "schema": "cockpit-human-principal-assertion/v2",
            "principal_ref": principal.principal_ref,
            "source_class": "real_human",
            "issued_at": "2026-08-03T10:00:00Z",
            "binding_digest": "a" * 64,
            "signature": "b" * 64,
        },
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={
            "workflow_run_id": "run-1",
            "delivery_id": "delivery-1",
            "decision": "adopted",
            "evidence_refs": ["evidence://review/1"],
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["review"]["decision"] == "adopted"
    assert response.json()["workflow_state_mutation"] is False
    assert captured == [
        (
            tmp_path / ".omo",
            {
                "delivery_id": "delivery-1",
                "decision": "adopted",
                "evidence_refs": ["evidence://review/1"],
            },
            "run-1",
            "operator://cockpit-api/verified",
        )
    ]


def test_engineering_delivery_review_signs_the_normalized_broker_payload(monkeypatch, tmp_path):
    captured_bindings: list[dict] = []
    captured_reviews: list[dict] = []

    def fake_assertion(principal, binding):
        captured_bindings.append(binding)
        return {
            "schema": "cockpit-human-principal-assertion/v2",
            "principal_ref": principal.principal_ref,
            "source_class": "real_human",
            "issued_at": "2026-08-03T10:00:00Z",
            "binding_digest": "a" * 64,
            "signature": "b" * 64,
        }

    def fake_review(_omo_dir, review, *, workflow_run_id, principal_assertion):
        captured_reviews.append(review)
        return {
            "schema": "engineering-delivery-review/v1",
            "status": "recorded",
            "delivery_id": review["delivery_id"],
            "decision": review["decision"],
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_engineering_delivery_review", fake_review)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/verified"),
    )
    monkeypatch.setattr(api_workflow_mesh_operations, "issue_engineering_review_assertion", fake_assertion)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={
            "workflow_run_id": " run-1 ",
            "delivery_id": " delivery-1 ",
            "decision": " ADOPTED ",
            "evidence_refs": [" evidence://human-review/1842 "],
        },
    )

    expected_review = {
        "delivery_id": "delivery-1",
        "decision": "adopted",
        "evidence_refs": ["evidence://human-review/1842"],
    }
    assert response.status_code == 200
    assert captured_reviews == [expected_review]
    assert captured_bindings == [
        {
            "workflow_run_id": "run-1",
            "candidate_receipt_id": "delivery-1",
            "review": expected_review,
        }
    ]


def test_engineering_delivery_review_api_rejects_raw_or_unknown_fields(monkeypatch):
    called = False

    def fail_review(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("broker must not receive an invalid envelope")

    monkeypatch.setattr(api_workflow_mesh_operations, "record_engineering_delivery_review", fail_review)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/verified"),
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={"workflow_run_id": "run-1", "document_body": "must-not-cross-boundary"},
    )

    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert response.json()["error"] == "engineering_delivery_review_invalid"
    assert called is False


def test_engineering_delivery_review_rejects_client_supplied_review_time(monkeypatch):
    called = False

    def fail_review(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("client review time must not reach OMO")

    monkeypatch.setattr(api_workflow_mesh_operations, "record_engineering_delivery_review", fail_review)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/verified"),
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={
            "workflow_run_id": "run-1",
            "delivery_id": "delivery-1",
            "decision": "adopted",
            "reviewed_at": "2026-08-03T10:00:00Z",
            "evidence_refs": ["evidence://review/1"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "engineering_delivery_review_invalid"
    assert called is False


def test_engineering_delivery_review_rejects_caller_supplied_actor(monkeypatch):
    called = False

    def fail_review(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("spoofed actor must not reach OMO")

    monkeypatch.setattr(api_workflow_mesh_operations, "record_engineering_delivery_review", fail_review)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "authenticate_api_principal",
        lambda *_args, **_kwargs: SimpleNamespace(principal_ref="operator://cockpit-api/verified"),
    )
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={
            "workflow_run_id": "run-1",
            "actor_ref": "operator://spoofed",
            "delivery_id": "delivery-1",
            "decision": "adopted",
            "evidence_refs": ["evidence://review/1"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "engineering_delivery_review_invalid"
    assert called is False


def test_engineering_delivery_review_requires_strict_auth_before_broker(monkeypatch):
    called = False

    def fail_review(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unauthenticated request must not reach OMO")

    def deny(_headers, *, any_scope, allow_admin):
        assert any_scope == frozenset({"engineering-review"})
        assert allow_admin is False
        raise api_workflow_mesh_operations.ApiAuthenticationError("missing_api_key")

    monkeypatch.setattr(api_workflow_mesh_operations, "record_engineering_delivery_review", fail_review)
    monkeypatch.setattr(api_workflow_mesh_operations, "authenticate_api_principal", deny)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/engineering-delivery/review",
        json={
            "workflow_run_id": "run-1",
            "delivery_id": "delivery-1",
            "decision": "adopted",
            "evidence_refs": ["evidence://review/1"],
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == "engineering_delivery_auth_required"
    assert called is False


def test_outcome_feedback_api_forwards_safe_payload_and_actor(monkeypatch, tmp_path):
    captured: list[tuple[object, dict, str]] = []

    def fake_record(omo_dir, payload, *, actor):
        captured.append((omo_dir, payload, actor))
        return {
            "status": "recorded",
            "feedback": {
                "schema": "outcome-feedback/v1",
                "feedback_id": "outcome-feedback:test",
            },
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fake_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={
            "workflow_run_id": "run-1",
            "outcome_id": "outcome-1",
            "scene_binding": {
                "scene_id": "knowledge-delivery",
                "journey_id": "intent-to-evidence",
                "outcome_metric": "verified_delivery_lead_time",
            },
            "consumption_state": "reviewed",
            "consumer_ref": "operator://redacted/reviewer-1",
            "actor_ref": "operator://redacted/reviewer-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured[0][0] == tmp_path / ".omo"
    assert captured[0][1]["outcome_id"] == "outcome-1"
    assert "actor_ref" not in captured[0][1]
    assert captured[0][2] == "operator://redacted/reviewer-1"


def test_generic_feedback_api_rejects_engineering_delivery_human_state(monkeypatch, tmp_path):
    called = False

    def fake_record(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("dedicated scene must not reach generic feedback broker")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fake_record)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={
            "workflow_run_id": "run-1",
            "outcome_id": "outcome:engineering-delivery:delivery-1",
            "scene_binding": {
                "scene_id": "engineering-delivery",
                "journey_id": "intent-to-evidence",
                "outcome_metric": "verified_delivery_lead_time",
            },
            "consumption_state": "adopted",
            "consumer_ref": "operator://spoofed-reviewer",
            "actor_ref": "operator://spoofed-reviewer",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "engineering_delivery_feedback_requires_authenticated_review"
    assert called is False


def test_outcome_feedback_api_returns_explicit_invalid_status(monkeypatch, tmp_path):
    def fail_record(_omo_dir, _payload, *, actor):
        raise ValueError("feedback scene_binding does not match WorkflowRun")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fail_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={"workflow_run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "outcome_feedback_invalid"


def test_outcome_feedback_api_returns_unavailable_on_persistence_error(monkeypatch, tmp_path):
    def fail_record(_omo_dir, _payload, *, actor):
        raise OSError("disk unavailable")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_outcome_feedback", fail_record)

    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    response = TestClient(app).post(
        "/api/workflow-mesh/outcome-feedback",
        json={"workflow_run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "outcome_feedback_unavailable"


def test_external_receipt_api_forwards_safe_envelope(monkeypatch, tmp_path):
    captured: list[tuple[object, dict, str, str | None, str]] = []

    def fake_record(omo_dir, receipt, *, workflow_run_id, step_run_id, producer):
        captured.append((omo_dir, receipt, workflow_run_id, step_run_id, producer))
        return {
            "event_id": "external-evidence:event-1",
            "workflow_run_id": workflow_run_id,
            "payload": {
                "evidence_id": "external:source:test-receipt-1",
                "receipt_id": receipt["receipt_id"],
                "resource_id": receipt["resource_id"],
                "result_state": receipt["result_state"],
                "observed_at": receipt["observed_at"],
                "provenance_ref": receipt["provenance_ref"],
            },
        }

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "record_external_receipt", fake_record)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/external-receipt",
        json={
            "workflow_run_id": "run-1",
            "step_run_id": "run-1:execute",
            "producer": "operator://receipt-entry",
            "receipt": {
                "receipt_id": "receipt-1",
                "trace_id": "trace-1",
                "resource_id": "source:test",
                "operation": "search",
                "result_state": "succeeded",
                "observed_at": "2026-08-03T10:00:00Z",
                "provenance_ref": "evidence://source/test",
                "policy_digest": "policy-1",
                "output_digest": "a" * 64,
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "recorded",
        "receipt": {
            "event_id": "external-evidence:event-1",
            "evidence_id": "external:source:test-receipt-1",
            "receipt_id": "receipt-1",
            "workflow_run_id": "run-1",
            "resource_id": "source:test",
            "result_state": "succeeded",
            "observed_at": "2026-08-03T10:00:00Z",
            "provenance_ref": "evidence://source/test",
        },
    }
    assert captured[0][0] == tmp_path / ".omo"
    assert captured[0][1]["receipt_id"] == "receipt-1"
    assert captured[0][2:] == (
        "run-1",
        "run-1:execute",
        "operator://receipt-entry",
    )


def test_external_receipt_api_rejects_unknown_envelope_field(monkeypatch):
    monkeypatch.setattr(api_workflow_mesh_operations, "record_external_receipt", lambda *args, **kwargs: None)
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/workflow-mesh/external-receipt",
        json={"workflow_run_id": "run-1", "content": "must-not-cross-boundary"},
    )

    assert response.status_code == 200
    assert response.json()["error"] == "external_receipt_invalid"
