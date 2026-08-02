import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (
    ROOT / "projects/agora/src",
    ROOT / "projects/omo/src",
    ROOT / "projects/runtime/src",
):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))

from agora.external_connections import (
    ExternalConnectionCatalog,
    SceneBinding,
)
from omo.omo_external_receipt import record_external_receipt
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _descriptor() -> dict:
    return {
        "id": "source:mesh-test",
        "kind": "knowledge_source",
        "provider": "mesh-test",
        "protocol": "external-resource/v1",
        "capabilities": ["search"],
        "data_classification": "private",
        "provenance": {"source_ref": "test://mesh-source"},
        "lifecycle": "active",
        "health": {"status": "healthy", "metrics": {"trust": 1, "freshness": 1}},
        "owner": "test-owner",
        "version": "1",
        "permission_ref": "credential://mesh-test",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "rollback_plan": "disable-resource",
    }


def _scene() -> SceneBinding:
    return SceneBinding(
        scene_id="mesh-scene",
        journey_id="mesh-journey",
        outcome_metric="evidence_quality",
        data_scope="private:test",
        operator="test-operator",
        permission_ref="credential://mesh-test",
    )


def _grant(run_id: str, step_run_id: str) -> dict:
    grant = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "external-fabric-test",
        "step_run_ids": [step_run_id],
        "capabilities": ["search"],
        "policy_digest": "external-connection-fabric/v1",
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
    }
    grant["proof"] = hashlib.sha256(
        json.dumps(
            grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return grant


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_external_receipt_can_close_a_workflow_mesh_evidence_chain(
    tmp_path: Path,
) -> None:
    pytest.importorskip("omo.workflow_mesh")
    catalog = ExternalConnectionCatalog()
    catalog.register(_descriptor())
    receipt = catalog.invoke(
        "search",
        _scene(),
        trace_id="trace-mesh",
        operation="search",
        handler=lambda _resource: {"result_digest_input": "redacted"},
        now=NOW,
    )
    assert receipt.result_state == "succeeded"

    run_id = "workflow-external-receipt"
    step_run_id = f"{run_id}:step-1"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    store.append(
        new_workflow_event(
            "StepDispatched",
            run_id,
            payload={"step_run_id": step_run_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            run_id,
            payload={"step_run_id": step_run_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(new_workflow_event("WorkflowSucceeded", run_id))
    recorded = record_external_receipt(
        tmp_path,
        receipt,
        workflow_run_id=run_id,
        step_run_id=step_run_id,
    )
    assert recorded["payload"]["decision_factors"]
    store.append(new_workflow_event("WorkflowVerified", run_id))

    snapshot = store.snapshot(run_id)
    assert snapshot["state"] == "verified"
    assert snapshot["evidence"][f"external:source:mesh-test:{receipt.receipt_id}"][
        "sha256"
    ]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_runtime_effect_receipt_can_close_the_same_mesh_run(tmp_path: Path) -> None:
    from runtime.executor.engine import AgentRuntime
    from runtime.workflow_admission import admission_proof

    run_id = "workflow-runtime-effect"
    step_run_id = f"{run_id}:runtime"
    grant = _grant(run_id, step_run_id)
    grant["step_run_ids"] = [step_run_id]
    grant["capabilities"] = ["execute", "search"]
    grant["issued_at"] = datetime.now(UTC).isoformat()
    grant["expires_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    grant["proof"] = admission_proof(grant)
    store = WorkflowMeshStore(tmp_path)

    runtime = AgentRuntime()
    runtime._tool_registry = {
        "lookup": {"fn": lambda query="": {"remote_id": query, "content": "private"}}
    }
    responses = iter(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-runtime-1",
                        "function": {
                            "name": "lookup",
                            "arguments": '{"query":"object-1"}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
                "usage": {"total_tokens": 1},
            },
            {
                "content": "runtime complete",
                "tool_calls": [],
                "finish_reason": "stop",
                "usage": {"total_tokens": 2},
            },
        ]
    )
    runtime._call_llm = lambda *args, **kwargs: next(responses)  # type: ignore[method-assign]
    result = runtime.run_task(
        "private runtime prompt",
        workflow_run_id=run_id,
        event_sink=store.sink(),
        admission=grant,
        context={
            "effect_store_path": str(tmp_path / "effects.jsonl"),
            "resource_id": "source:runtime-test",
            "operation": "lookup",
            "provenance_ref": "runtime-test://lookup",
        },
    )

    assert result["result"] == "runtime complete"
    receipt = result["effect_receipts"][0]
    recorded = record_external_receipt(
        tmp_path,
        receipt,
        workflow_run_id=run_id,
        step_run_id=f"{step_run_id}:1",
        producer="runtime",
    )
    assert recorded["payload"]["evidence_schema"] == "external-connection-receipt/v1"
    store.append(new_workflow_event("WorkflowVerified", run_id))

    snapshot = store.snapshot(run_id)
    assert snapshot["state"] == "verified"
    assert snapshot["evidence"]
    assert all("content" not in str(event) for event in store.events())


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_runtime_compensation_returns_to_running_without_raw_payload(tmp_path: Path) -> None:
    from runtime.executor.engine import AgentRuntime
    from runtime.workflow_admission import admission_proof
    from runtime.workflow_effects import WorkflowEffectStore

    run_id = "workflow-runtime-compensation"
    step_run_id = f"{run_id}:runtime:1"
    grant = _grant(run_id, f"{run_id}:runtime")
    grant["step_run_ids"] = [f"{run_id}:runtime"]
    grant["capabilities"] = ["execute"]
    grant["proof"] = admission_proof(grant)
    store = WorkflowMeshStore(tmp_path / "omo")
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    store.append(
        new_workflow_event(
            "StepDispatched",
            run_id,
            payload={"step_run_id": step_run_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            run_id,
            payload={"step_run_id": step_run_id, "admission_id": grant["admission_id"]},
        )
    )

    effects = WorkflowEffectStore(tmp_path / "effects.jsonl")
    effect_key = f"{run_id}:effect:send"
    effects.execute_once_with_outcome(effect_key, lambda: {"remote_id": "obj-1"})
    payload = AgentRuntime().compensate_effect(
        effects,
        effect_key,
        lambda: {"remote_id": "obj-1", "content": "private"},
        workflow_run_id=run_id,
        step_run_id=step_run_id,
        admission=grant,
        event_sink=store.sink(),
    )

    assert payload["status"] == "compensated"
    snapshot = store.snapshot(run_id)
    assert snapshot["state"] == "running"
    assert [event["event_type"] for event in store.events()][-2:] == [
        "CompensationStarted",
        "WorkflowRecovered",
    ]
    assert all("private" not in str(event) for event in store.events())
