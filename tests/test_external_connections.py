from datetime import UTC, datetime

import pytest

from agora.external_connections import (
    DiscoveryRecord,
    ExternalConnectionCatalog,
    ExternalConnectionError,
    ExternalResourceDescriptor,
    SceneBinding,
    SceneCard,
    build_external_resource_catalog_snapshot,
    diff_external_resource_catalog_snapshots,
    discover_entry_points,
    evaluate_scene_card,
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
SCENE_CARD = SceneCard(
    scene_id="research-brief",
    journey_id="weekly-decision",
    goal="缩短研究结论形成时间",
    trigger="每周决策会前",
    input_contract="已授权的研究资料引用",
    result_contract="带来源和置信度的决策简报",
    outcome_metric="decision_latency_hours",
    consumer="research-lead",
    approver="human:xiamingxing",
    owner="research-ops",
    failure_cost="错误结论进入决策会",
    data_classification="private",
    data_scope="private:research",
    operator="human:xiamingxing",
    permission_ref="credential://research",
    rollback_plan="disable-resource",
    sample_refs=(
        "vault://redacted/sample-1",
        "vault://redacted/sample-2",
        "vault://redacted/sample-3",
    ),
    demand_evidence_refs=("evidence://research/demand-1",),
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


def test_catalog_snapshot_exposes_safe_health_and_lifecycle_reasons() -> None:
    payload = _descriptor("source:snapshot", lifecycle="active")
    payload["health"] = {
        "status": "healthy",
        "observed_at": "2026-08-02T00:00:00+00:00",
        "latency_ms": 42,
        "source": "probe:test",
        "metrics": {"trust": 0.9, "freshness": 0.8, "secret": "omit"},
    }
    snapshot = build_external_resource_catalog_snapshot(
        [
            DiscoveryRecord(
                descriptor=ExternalResourceDescriptor.from_mapping(payload),
                entry_point="external.resources:test",
            ),
            DiscoveryRecord(
                descriptor=None,
                entry_point="external.resources:broken",
                error="ImportError",
            ),
        ],
        now=NOW,
        health_ttl_seconds=3600,
    )

    resource = snapshot["resources"][0]
    assert snapshot["schema"] == "external-resource-catalog/v1"
    assert snapshot["activation"] == "forbidden"
    assert resource["availability"] == "available"
    assert resource["health"]["status"] == "healthy"
    assert resource["health"]["metrics"] == {"trust": 0.9, "freshness": 0.8}
    assert "metadata" not in resource
    assert snapshot["errors"] == [
        {
            "entry_point": "external.resources:broken",
            "status": "unavailable",
            "error": "ImportError",
        }
    ]


def test_catalog_snapshot_marks_stale_health_and_proposal_only_explicitly() -> None:
    payload = _descriptor("source:stale", lifecycle="active", mode="proposal_only")
    payload["health"] = {
        "status": "healthy",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "latency_ms": 80,
        "source": "probe:test",
    }
    snapshot = build_external_resource_catalog_snapshot(
        [
            DiscoveryRecord(
                descriptor=ExternalResourceDescriptor.from_mapping(payload),
                entry_point="external.resources:stale",
            )
        ],
        now=NOW,
        health_ttl_seconds=60,
    )

    resource = snapshot["resources"][0]
    assert resource["availability"] == "proposal_only"
    assert resource["health"]["status"] == "healthy"
    assert "health_stale" in resource["reason_codes"]
    assert "missing_expiry_or_review" not in resource["reason_codes"]


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


def test_scene_card_gate_requires_demand_evidence_or_opportunity_window() -> None:
    card = SceneCard(**{**SCENE_CARD.__dict__, "demand_evidence_refs": ()})

    decision = evaluate_scene_card(card)

    assert decision.status == "rejected"
    assert "missing_demand_evidence_or_opportunity_window" in decision.reasons


def test_scene_card_rejects_raw_content_and_keeps_only_opaque_refs() -> None:
    payload = SCENE_CARD.to_dict()
    payload["sample_data"] = "private body"

    with pytest.raises(ExternalConnectionError, match="raw content field"):
        SceneCard.from_mapping(payload)

    payload = SCENE_CARD.to_dict()
    payload["sample_refs"] = ["https://example.test/raw-document"] * 3
    with pytest.raises(ExternalConnectionError, match="non-opaque ref"):
        SceneCard.from_mapping(payload)


def test_full_scene_card_is_required_for_strict_activation() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor("source:card"))

    decision = catalog.activate_with_scene_card(
        "source:card", SCENE_CARD, trace_id="trace-card", now=NOW
    )

    assert decision.status == "admitted"
    assert catalog.get("source:card").lifecycle == "active"

    rejected = catalog.activate_with_scene_card(
        "source:card",
        {**SCENE.to_dict()},
        trace_id="trace-card-missing",
        now=NOW,
    )
    assert rejected.status == "rejected"
    assert rejected.reasons[0].startswith("invalid_scene_card:")


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


def test_evaluate_candidates_exposes_explainable_decisions_without_activation() -> None:
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor("source:healthy", lifecycle="active", trust=0.7))
    wrong_permission = _descriptor("source:wrong-permission", lifecycle="active")
    wrong_permission["permission_ref"] = "credential://other"
    catalog.register(wrong_permission)
    no_capability = _descriptor("source:no-capability", lifecycle="active")
    no_capability["capabilities"] = ["read"]
    catalog.register(no_capability)

    evaluation = catalog.evaluate_candidates(
        "search",
        SCENE,
        trace_id="trace-evaluation",
        now=NOW,
    ).to_dict()

    assert evaluation["schema"] == "external-resource-evaluation/v1"
    assert evaluation["mode"] == "read_only_evaluation"
    assert evaluation["activation"] == "forbidden"
    assert evaluation["status"] == "selected"
    assert evaluation["selected_resource_id"] == "source:healthy"
    decisions = {item["resource_id"]: item for item in evaluation["candidates"]}
    assert decisions["source:healthy"]["status"] == "eligible"
    assert decisions["source:healthy"]["decision_factors"]["health"] == "healthy"
    assert decisions["source:healthy"]["rank"]
    assert decisions["source:wrong-permission"]["status"] == "rejected"
    assert (
        "missing_or_mismatched_permission"
        in decisions["source:wrong-permission"]["reasons"]
    )
    assert decisions["source:no-capability"]["status"] == "not_applicable"
    assert catalog.get("source:healthy").lifecycle == "active"


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
    assert evidence["decision_factors"]
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


class _ProbingEntryPoint:
    group = "external.resources"
    name = "probing"

    def load(self):
        class Provider:
            def external_descriptor(self):
                return _descriptor("entry:probing", lifecycle="active")

            def health_probe(self):
                return {
                    "status": "healthy",
                    "observed_at": "2026-08-02T00:00:00+00:00",
                    "latency_ms": 0,
                    "source": "probe:test",
                }

        return Provider


def test_explicit_health_probe_overrides_descriptor_health() -> None:
    records = discover_entry_points([_ProbingEntryPoint()], probe=True)

    assert records[0].error is None
    assert records[0].health_override["source"] == "probe:test"
    snapshot = build_external_resource_catalog_snapshot(records, now=NOW)
    assert snapshot["resources"][0]["health"]["latency_ms"] == 0


class _FailingProbeEntryPoint:
    group = "external.resources"
    name = "failing-probe"

    def load(self):
        class Provider:
            def external_descriptor(self):
                return _descriptor("entry:failing-probe", lifecycle="active")

            def health_probe(self):
                raise RuntimeError("probe failure")

        return Provider


def test_failed_health_probe_keeps_candidate_but_quarantines_availability() -> None:
    records = discover_entry_points([_FailingProbeEntryPoint()], probe=True)

    assert records[0].error == "RuntimeError"
    snapshot = build_external_resource_catalog_snapshot(records, now=NOW)
    resource = snapshot["resources"][0]
    assert resource["availability"] == "unavailable"
    assert "provider_probe_failed" in resource["reason_codes"]
    assert snapshot["errors"][0]["error"] == "RuntimeError"


def test_catalog_diff_detects_health_change_and_error_resolution() -> None:
    previous = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "availability": "available",
                "health": {"status": "healthy"},
            }
        ],
        "errors": [
            {
                "entry_point": "external.resources:broken",
                "status": "unavailable",
                "error": "ImportError",
            }
        ],
    }
    current = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-02T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "availability": "unavailable",
                "health": {"status": "unhealthy"},
            }
        ],
        "errors": [],
    }

    diff = diff_external_resource_catalog_snapshots(previous, current)

    assert diff["summary"] == {
        "change_count": 1,
        "added_count": 0,
        "removed_count": 0,
        "changed_count": 1,
        "error_change_count": 1,
        "review_required": False,
        "review_required_count": 0,
        "operational_observation_count": 1,
        "risk_codes": ["availability_changed", "health_changed"],
    }
    assert diff["changes"][0]["changed_fields"] == ["availability", "health"]
    assert diff["changes"][0]["risk_class"] == "operational_observation"
    assert diff["changes"][0]["review_required"] is False
    assert diff["error_changes"][0]["change"] == "resolved"


def test_catalog_diff_marks_descriptor_changes_for_manual_review() -> None:
    previous = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "provider": "provider-a",
                "capabilities": ["search"],
            }
        ],
        "errors": [],
    }
    current = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-02T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "provider": "provider-b",
                "capabilities": ["search", "summarize"],
            },
            {"id": "source:new", "provider": "provider-c", "capabilities": ["search"]},
        ],
        "errors": [],
    }

    diff = diff_external_resource_catalog_snapshots(previous, current)

    assert diff["summary"]["review_required"] is True
    assert diff["summary"]["review_required_count"] == 2
    assert diff["summary"]["operational_observation_count"] == 0
    assert diff["changes"][0]["risk_class"] == "manual_review"
    assert diff["changes"][0]["risk_codes"] == ["resource_added"]
    assert "descriptor_provider_changed" in diff["changes"][1]["risk_codes"]


# ── B2: 能力准入分级 (capability 注册 + 使用度量驱动生命周期) ──────────


def test_register_capability_admitted_with_usage():
    """有调用记录的能力注册为 admitted。"""
    cat = ExternalConnectionCatalog()
    r = cat.register_capability("bos://capability/foo/invoke", use_metrics={"calls": 5})
    assert r.lifecycle == "admitted"
    assert r.kind == "tool_capability"
    assert r.protocol == "bos"


def test_register_capability_zero_usage_sandboxed():
    """零调用能力自动降级为 sandbox (防僵尸能力直接 active)。"""
    cat = ExternalConnectionCatalog()
    r = cat.register_capability("bos://capability/bar/invoke", use_metrics={"calls": 0})
    assert r.lifecycle == "sandbox"


def test_register_capability_explicit_lifecycle():
    """显式指定 lifecycle 不被使用度量覆盖。"""
    cat = ExternalConnectionCatalog()
    r = cat.register_capability(
        "bos://capability/baz/invoke",
        lifecycle="discovered",
        use_metrics={"calls": 10},
    )
    assert r.lifecycle == "discovered"


def test_register_capability_rejects_bad_kind():
    """非法 kind 被拒绝。"""
    cat = ExternalConnectionCatalog()
    try:
        cat.register_capability("bos://capability/x/invoke", kind="not-a-kind")
        raised = False
    except ExternalConnectionError:
        raised = True
    assert raised
