from __future__ import annotations

import hashlib
import json

import pytest
from omo.cli import main as cli_main
from omo.omo_external_receipt import ExternalReceiptError, record_external_receipt
from omo.workflow_mesh import (
    WorkflowMeshEventError,
    WorkflowMeshStore,
    new_workflow_event,
)

NOW = "2026-08-02T09:00:00Z"


def _grant(run_id: str, step_run_id: str) -> dict[str, object]:
    grant: dict[str, object] = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "external-receipt-test",
        "step_run_ids": [step_run_id],
        "capabilities": ["search"],
        "policy_digest": "external-connection-fabric/v1",
        "issued_at": NOW,
        "expires_at": "2026-08-02T10:00:00Z",
    }
    unsigned = json.dumps(
        grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    grant["proof"] = hashlib.sha256(unsigned).hexdigest()
    return grant


def _seed_succeeded_run(
    tmp_path, run_id: str = "run-receipt"
) -> tuple[WorkflowMeshStore, str]:
    step_run_id = f"{run_id}:step-1"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    context = {"step_run_id": step_run_id, "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, payload=context))
    store.append(new_workflow_event("StepStarted", run_id, payload=context))
    store.append(new_workflow_event("WorkflowSucceeded", run_id))
    return store, step_run_id


def _receipt(result_state: str = "succeeded") -> dict[str, object]:
    return {
        "receipt_id": "receipt-1",
        "trace_id": "trace-1",
        "resource_id": "source:test",
        "operation": "search",
        "result_state": result_state,
        "observed_at": NOW,
        "provenance_ref": "test://source",
        "policy_digest": "external-connection-fabric/v1",
        "decision_factors": {"health": "healthy", "freshness": 1},
        "output_digest": "a" * 64,
    }


def test_receipt_broker_records_safe_evidence_and_is_idempotent(tmp_path):
    store, step_run_id = _seed_succeeded_run(tmp_path)

    first = record_external_receipt(
        tmp_path,
        _receipt(),
        workflow_run_id="run-receipt",
        step_run_id=step_run_id,
    )
    repeated = record_external_receipt(
        tmp_path,
        _receipt(),
        workflow_run_id="run-receipt",
        step_run_id=step_run_id,
    )

    assert repeated == first
    assert len(store.events()) == 6
    evidence = store.evidence_snapshot("run-receipt", "external:source:test:receipt-1")
    assert evidence is not None
    assert evidence["sha256"] == "a" * 64
    assert evidence["decision_factors"] == {"health": "healthy", "freshness": 1}
    assert "output" not in evidence


def test_receipt_broker_rejects_failed_and_raw_receipts(tmp_path):
    _seed_succeeded_run(tmp_path)

    with pytest.raises(ExternalReceiptError, match="only succeeded/degraded"):
        record_external_receipt(
            tmp_path, _receipt("failed"), workflow_run_id="run-receipt"
        )

    raw = _receipt()
    raw["raw_output"] = "must never enter the event"
    with pytest.raises(ExternalReceiptError, match="forbidden"):
        record_external_receipt(tmp_path, raw, workflow_run_id="run-receipt")


def test_receipt_retry_conflict_is_fail_closed(tmp_path):
    _seed_succeeded_run(tmp_path)
    record_external_receipt(tmp_path, _receipt(), workflow_run_id="run-receipt")
    changed = _receipt()
    changed["output_digest"] = "b" * 64

    with pytest.raises(WorkflowMeshEventError, match="Conflicting duplicate"):
        record_external_receipt(tmp_path, changed, workflow_run_id="run-receipt")


def test_receipt_broker_keeps_mesh_fail_closed_without_success(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-incomplete"))

    with pytest.raises(WorkflowMeshEventError):
        record_external_receipt(tmp_path, _receipt(), workflow_run_id="run-incomplete")
    assert len(store.events()) == 1


def test_external_receipt_cli_records_json_event(tmp_path, capsys):
    store, step_run_id = _seed_succeeded_run(tmp_path, "run-cli")
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(_receipt()), encoding="utf-8")

    assert (
        cli_main(
            [
                "worker",
                "external-receipt",
                "run-cli",
                "--receipt-file",
                str(receipt_file),
                "--step-run-id",
                step_run_id,
                "--omo-dir",
                str(tmp_path),
                "--json",
            ]
        )
        == 0
    )
    event = json.loads(capsys.readouterr().out)
    assert event["event_type"] == "EvidenceRecorded"
    assert len(store.events()) == 6
