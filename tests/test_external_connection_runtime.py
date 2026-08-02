import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "projects/agora/src", ROOT / "projects/omo/src"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))

from agora.external_connections import ExternalConnectionCatalog, SceneBinding  # noqa: E402
from omo.omo_external_receipt import record_external_receipt  # noqa: E402
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event  # noqa: E402


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
        json.dumps(grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return grant


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_external_receipt_can_close_a_workflow_mesh_evidence_chain(tmp_path: Path) -> None:
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
    store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
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
    assert snapshot["evidence"][f"external:source:mesh-test:{receipt.receipt_id}"]["sha256"]
