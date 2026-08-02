from datetime import UTC, datetime

import pytest

from agora.external_connections import (
    ExternalConnectionCatalog,
    ExternalConnectionError,
    ExternalResourceDescriptor,
    SceneBinding,
    discover_entry_points,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)
SCENE = SceneBinding(
    scene_id="research-brief",
    journey_id="weekly-decision",
    outcome_metric="decision_latency_hours",
    data_scope="private:research",
    operator="human:xiamingxing",
    permission_ref="credential://research",
)


def _descriptor(
    resource_id: str = "source:primary",
    *,
    lifecycle: str = "sandbox",
    status: str = "healthy",
    trust: float = 0.8,
    mode: str = "live_query",
) -> dict:
    return {
        "id": resource_id,
        "kind": "knowledge_source",
        "provider": resource_id.split(":", 1)[-1],
        "protocol": "external-resource/v1",
        "capabilities": ["discover", "search", "read"],
        "data_classification": "private",
        "provenance": {"source_ref": f"https://example.test/{resource_id}"},
        "lifecycle": lifecycle,
        "health": {
            "status": status,
            "metrics": {"trust": trust, "freshness": 0.8, "cost": 0.2, "latency": 0.3},
        },
        "owner": "test-owner",
        "version": "1.0.0",
        "permission_ref": "credential://research",
        "mode": mode,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "rollback_plan": "disable-resource",
    }


def test_descriptor_rejects_secret_fields_recursively() -> None:
    payload = _descriptor()
    payload["metadata"] = {"nested": {"access_token": "must-not-land"}}
    with pytest.raises(ExternalConnectionError, match="secret field"):
        ExternalResourceDescriptor.from_mapping(payload)


def test_scene_bound_activation_requires_permission_and_expiry() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor())

    decision = catalog.activate("source:primary", SCENE, trace_id="trace-1", now=NOW)

    assert decision.status == "admitted"
    assert catalog.get("source:primary").lifecycle == "active"

    rejected = catalog.admit(
        "source:primary",
        {**SCENE.to_dict(), "permission_ref": "credential://other"},
        trace_id="trace-2",
        now=NOW,
    )
    assert rejected.status == "rejected"
    assert "missing_or_mismatched_permission" in rejected.reasons


def test_router_prefers_healthy_trusted_resource_and_records_factors() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(
        _descriptor(
            "source:degraded", lifecycle="degraded", status="degraded", trust=0.99
        )
    )
    catalog.register(
        _descriptor("source:healthy", lifecycle="active", status="healthy", trust=0.7)
    )

    decision = catalog.route("search", SCENE, trace_id="trace-route", now=NOW)

    assert decision.status == "selected"
    assert decision.selected_resource_id == "source:healthy"
    assert decision.decision_factors["health"] == "healthy"
    assert decision.decision_factors["permission"] == 1


def test_missing_capability_is_explicitly_unavailable() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor("source:only-read", lifecycle="active"))

    decision = catalog.route("invoke", SCENE, trace_id="trace-unavailable", now=NOW)

    assert decision.status == "unavailable"
    assert decision.selected_resource_id is None
    assert "no_admitted_capability" in decision.reasons


def test_invocation_receipt_is_safe_and_mesh_compatible() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor("source:live", lifecycle="active"))

    receipt = catalog.invoke(
        "search",
        SCENE,
        trace_id="trace-receipt",
        operation="search",
        handler=lambda resource: {"resource": resource.id, "count": 2},
        now=NOW,
    )
    evidence = receipt.evidence_payload("workflow-1", "step-1")

    assert receipt.result_state == "succeeded"
    assert receipt.output_digest
    assert evidence["kind"] == "external_connection"
    assert evidence["resource_id"] == "source:live"
    assert evidence["workflow_run_id"] == "workflow-1"
    assert "count" not in receipt.to_dict()
    assert "password" not in receipt.to_dict()


def test_proposal_only_does_not_invoke_handler() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(
        _descriptor("tool:proposal", lifecycle="active", mode="proposal_only")
    )
    called = False

    def handler(_resource):
        nonlocal called
        called = True
        return {"side_effect": "forbidden"}

    receipt = catalog.invoke(
        "search",
        SCENE,
        trace_id="trace-proposal",
        operation="suggest",
        handler=handler,
        now=NOW,
    )

    assert receipt.result_state == "proposed"
    assert called is False


class _EntryPoint:
    group = "external.resources"
    name = "test"

    def load(self):
        class Provider:
            def external_descriptor(self):
                return _descriptor("entry:test", lifecycle="active")

        return Provider


def test_external_entry_points_are_isolated_and_discoverable() -> None:
    records = discover_entry_points([_EntryPoint()])

    assert len(records) == 1
    assert records[0].descriptor.id == "entry:test"
    assert records[0].error is None
