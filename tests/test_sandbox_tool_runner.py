from __future__ import annotations

import hashlib
import json

import pytest
from omo.cli import main as cli_main
from omo.sandbox_tool_runner import SandboxToolError, run_sandbox_tool
from omo.worker_lifecycle import (
    acknowledge_worker,
    expire_worker_lease,
    reclaim_worker,
    record_step_dispatch,
)
from omo.workflow_eval import build_operations_snapshot
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _grant(run_id: str, step_run_id: str, *, sandbox: bool = True) -> dict[str, object]:
    capabilities = ["execute"]
    if sandbox:
        capabilities.append("sandbox.tool.invoke")
    grant: dict[str, object] = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "sandbox",
        "step_run_ids": [step_run_id],
        "capabilities": capabilities,
        "policy_digest": "policy-sandbox",
        "issued_at": "2026-08-03T00:00:00Z",
        "expires_at": "2026-08-03T01:00:00Z",
    }
    unsigned = json.dumps(
        grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    grant["proof"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return grant


def _context(
    tmp_path, run_id: str = "run-sandbox", *, sandbox: bool = True
) -> dict[str, str]:
    step_run_id = f"{run_id}:execute"
    grant = _grant(run_id, step_run_id, sandbox=sandbox)
    store = WorkflowMeshStore(tmp_path)
    store.append(
        new_workflow_event(
            "WorkflowRequested",
            run_id,
            trace_id=run_id,
            scene_binding={
                "scene_id": "engineering-delivery",
                "journey_id": "intent-to-evidence",
                "outcome_metric": "verified_delivery_lead_time",
            },
        )
    )
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    record_step_dispatch(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        dispatch_id="dispatch-sandbox",
        worker_id="worker-sandbox",
        step_run_id=step_run_id,
        admission_id=str(grant["admission_id"]),
    )
    acknowledge_worker(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        dispatch_id="dispatch-sandbox",
        worker_id="worker-sandbox",
        step_run_id=step_run_id,
        admission_id=str(grant["admission_id"]),
        lease_seconds=60,
        now="2026-08-03T00:00:00Z",
    )
    return {
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "dispatch_id": "dispatch-sandbox",
        "worker_id": "worker-sandbox",
        "step_run_id": step_run_id,
        "admission_id": str(grant["admission_id"]),
    }


def test_sandbox_tool_records_deterministic_receipt_and_evidence(tmp_path):
    context = _context(tmp_path)
    input_digest = "a" * 64

    result = run_sandbox_tool(
        tmp_path,
        **context,
        input_ref="artifact://knowledge/demo",
        input_digest=input_digest,
        now="2026-08-03T00:00:10Z",
    )

    assert result["status"] == "executed"
    assert result["activation"] == "sandbox"
    assert result["external_side_effects"] == "disabled"
    snapshot = WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])
    assert snapshot["state"] == "succeeded"
    assert snapshot["step_runs"][context["step_run_id"]]["state"] == "succeeded"
    evidence = next(iter(snapshot["evidence"].values()))
    assert evidence["evidence_schema"] == "external-connection-receipt/v1"
    assert evidence["result_state"] == "succeeded"
    invocation = next(
        event
        for event in WorkflowMeshStore(tmp_path).events()
        if event["event_type"] == "ToolInvocationRecorded"
    )
    assert invocation["payload"]["activation"] == "sandbox"
    assert "raw_input" not in json.dumps(invocation)
    projection = build_operations_snapshot(tmp_path)
    assert projection["sandbox_tools"] == {
        "status": "observed",
        "activation": "sandbox",
        "external_side_effects": "disabled",
        "invocation_count": 1,
        "receipt_run_count": 1,
        "outcomes": {"succeeded": 1},
        "next_action": "review_sandbox_receipt_and_promote_only_with_real_scene",
    }


def test_sandbox_tool_retry_is_idempotent(tmp_path):
    context = _context(tmp_path)
    kwargs = {
        **context,
        "input_ref": "sandbox://descriptor/demo",
        "input_digest": "b" * 64,
        "now": "2026-08-03T00:00:10Z",
    }
    first = run_sandbox_tool(tmp_path, **kwargs)
    event_count = len(WorkflowMeshStore(tmp_path).events())
    repeated = run_sandbox_tool(tmp_path, **kwargs)

    assert repeated["status"] == "replayed"
    assert repeated["invocation_id"] == first["invocation_id"]
    assert len(WorkflowMeshStore(tmp_path).events()) == event_count


def test_sandbox_tool_rejects_raw_ref_and_missing_capability(tmp_path):
    context = _context(tmp_path)
    with pytest.raises(SandboxToolError, match="input_ref"):
        run_sandbox_tool(
            tmp_path,
            **context,
            input_ref="raw-content",
            input_digest="c" * 64,
        )

    no_capability = _context(
        tmp_path / "no-capability", "run-no-capability", sandbox=False
    )
    with pytest.raises(SandboxToolError, match="lacks capability"):
        run_sandbox_tool(
            tmp_path / "no-capability",
            **no_capability,
            input_ref="artifact://knowledge/demo",
            input_digest="c" * 64,
            now="2026-08-03T00:00:10Z",
        )


def test_sandbox_tool_requires_live_worker_lease(tmp_path):
    context = _context(tmp_path, "run-expired")
    with pytest.raises(SandboxToolError, match="context mismatch"):
        run_sandbox_tool(
            tmp_path,
            **{**context, "worker_id": "worker-other"},
            input_ref="artifact://knowledge/demo",
            input_digest="d" * 64,
            now="2026-08-03T00:00:10Z",
        )
    with pytest.raises(SandboxToolError, match="lease has expired"):
        run_sandbox_tool(
            tmp_path,
            **context,
            input_ref="artifact://knowledge/demo",
            input_digest="d" * 64,
            now="2026-08-03T00:01:00Z",
        )


@pytest.mark.parametrize(
    ("outcome", "error_code", "run_state"),
    [
        ("failed", "SANDBOX_TOOL_FAILED", "failed"),
        ("unavailable", "SANDBOX_BACKEND_UNAVAILABLE", "unavailable"),
    ],
)
def test_sandbox_tool_failure_never_creates_success_or_evidence(
    tmp_path, outcome, error_code, run_state
):
    context = _context(tmp_path, f"run-{outcome}")
    kwargs = {
        **context,
        "input_ref": "sandbox://descriptor/failure",
        "input_digest": "f" * 64,
        "outcome": outcome,
        "now": "2026-08-03T00:00:10Z",
    }

    first = run_sandbox_tool(tmp_path, **kwargs)
    repeated = run_sandbox_tool(tmp_path, **kwargs)
    events = WorkflowMeshStore(tmp_path).events()
    event_types = [event["event_type"] for event in events]

    assert first["status"] == "executed"
    assert repeated["status"] == "replayed"
    assert first["outcome"] == outcome
    assert first["error_code"] == error_code
    assert first["receipt_event_id"] is None
    assert event_types.count("ToolInvocationRecorded") == 1
    assert "WorkflowSucceeded" not in event_types
    assert "EvidenceRecorded" not in event_types
    snapshot = WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])
    assert snapshot["state"] == run_state
    assert snapshot["step_runs"][context["step_run_id"]]["state"] == run_state
    assert build_operations_snapshot(tmp_path)["sandbox_tools"]["outcomes"] == {
        outcome: 1
    }


def test_sandbox_tool_replays_after_worker_reclaim_with_new_attempt(tmp_path):
    context = _context(tmp_path, "run-reclaimed")
    expire_worker_lease(
        tmp_path,
        **context,
        now="2026-08-03T00:01:00Z",
    )
    reclaim_worker(
        tmp_path,
        **context,
        successor_worker_id="worker-successor",
        successor_dispatch_id="dispatch-successor",
        now="2026-08-03T00:01:01Z",
    )
    successor_step = f"{context['workflow_run_id']}:execute:attempt-2"
    record_step_dispatch(
        tmp_path,
        workflow_run_id=context["workflow_run_id"],
        trace_id=context["trace_id"],
        dispatch_id="dispatch-successor",
        worker_id="worker-successor",
        step_run_id=successor_step,
        admission_id=context["admission_id"],
    )
    acknowledge_worker(
        tmp_path,
        workflow_run_id=context["workflow_run_id"],
        trace_id=context["trace_id"],
        dispatch_id="dispatch-successor",
        worker_id="worker-successor",
        step_run_id=successor_step,
        admission_id=context["admission_id"],
        lease_seconds=60,
        now="2026-08-03T00:01:01Z",
    )

    result = run_sandbox_tool(
        tmp_path,
        **{
            **context,
            "dispatch_id": "dispatch-successor",
            "worker_id": "worker-successor",
            "step_run_id": successor_step,
            "input_ref": "artifact://knowledge/recovered",
            "input_digest": "9" * 64,
            "now": "2026-08-03T00:01:10Z",
        },
    )

    assert result["status"] == "executed"
    assert result["outcome"] == "succeeded"
    snapshot = WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])
    assert snapshot["state"] == "succeeded"
    assert snapshot["worker"]["worker_id"] == "worker-successor"
    assert snapshot["step_runs"][successor_step]["state"] == "succeeded"


def test_sandbox_tool_cli_is_explicit_and_json(capsys, tmp_path):
    context = _context(tmp_path, "run-cli")
    assert (
        cli_main(
            [
                "worker",
                "sandbox-tool",
                context["workflow_run_id"],
                "--trace-id",
                context["trace_id"],
                "--dispatch-id",
                context["dispatch_id"],
                "--worker",
                context["worker_id"],
                "--step-run-id",
                context["step_run_id"],
                "--admission-id",
                context["admission_id"],
                "--input-ref",
                "artifact://cli/demo",
                "--input-digest",
                "e" * 64,
                "--omo-dir",
                str(tmp_path),
                "--now",
                "2026-08-03T00:00:10Z",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "sandbox-tool-invocation/v1"
    assert payload["status"] == "executed"
