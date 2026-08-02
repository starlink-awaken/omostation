"""Event-derived Workflow Mesh evaluation dataset and policy proposals."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .knowledge_action import build_knowledge_action_snapshot
from .omo_external_evaluation import read_external_resource_evaluations
from .outcome_feedback import ELIGIBLE_WORKFLOW_STATES, read_outcome_feedback
from .workflow_mesh import WorkflowMeshStore

OPERATIONS_SCHEMA_VERSION = "workflow-mesh-operations/v1"
REQUEST_EVAL_SCHEMA_VERSION = "workflow-request-eval/v1"
SELECTION_EVAL_SCHEMA_VERSION = "external-resource-selection-eval/v1"


def _duration_seconds(events: list[dict[str, Any]]) -> float | None:
    timestamps = []
    for event in events:
        try:
            timestamps.append(datetime.fromisoformat(str(event["occurred_at"])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(timestamps) < 2:
        return None
    return round((max(timestamps) - min(timestamps)).total_seconds(), 3)


def _row(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    types = [str(event["event_type"]) for event in events]
    event_ids = [str(event["event_id"]) for event in events]
    success = "WorkflowSucceeded" in types
    failed = "WorkflowFailed" in types or "StepFailed" in types
    outcome = "success" if success else ("failed" if failed else "incomplete")
    retries = sum(event_type == "StepRetryScheduled" for event_type in types)
    admitted = snapshot.get("admission") is not None
    evidence_count = len(snapshot.get("evidence", {}))
    terminal = outcome in {"success", "failed"}
    return {
        "workflow_run_id": snapshot["workflow_run_id"],
        "trace_id": snapshot.get("trace_id"),
        "features": {
            "event_count": len(events),
            "step_count": len(snapshot.get("step_runs", {})),
            "retry_count": retries,
            "backend_unavailable": "BackendUnavailable" in types,
            "compensation_used": "CompensationStarted" in types,
            "recovered": "WorkflowRecovered" in types,
            "approval_requested": "ApprovalRequested" in types,
            "evidence_count": evidence_count,
            "duration_seconds": _duration_seconds(events),
        },
        "labels": {
            "outcome": outcome,
            "admitted": admitted,
            "verified": "WorkflowVerified" in types,
            "evidence_complete": evidence_count > 0,
            "terminal": terminal,
        },
        "label_source": {
            "event_log": "_knowledge/workflow-mesh/events.jsonl",
            "event_ids": event_ids,
            "labeling_rule": "workflow-mesh-eval/v1:event-derived",
        },
    }


def build_eval_dataset(
    omo_dir: Path | str,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build only terminal runs with admission as high-quality eval rows."""
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    by_run: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_run.setdefault(str(event["workflow_run_id"]), []).append(event)

    rows: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    for snapshot in store.snapshots():
        run_events = by_run.get(snapshot["workflow_run_id"], [])
        candidate = _row(snapshot, run_events)
        labels = candidate["labels"]
        if not labels["admitted"]:
            excluded["missing_admission"] += 1
            continue
        if not labels["terminal"]:
            excluded["incomplete"] += 1
            continue
        rows.append(candidate)

    dataset = {
        "dataset_version": "workflow-mesh-eval/v1",
        "source": {
            "kind": "omo_append_only_event_log",
            "path": "_knowledge/workflow-mesh/events.jsonl",
            "labels_are_event_derived": True,
        },
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "outcomes": dict(Counter(row["labels"]["outcome"] for row in rows)),
            "excluded": dict(excluded),
        },
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return dataset


def build_request_eval_dataset(
    omo_dir: Path | str,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build an event-derived dataset for the request-to-admission funnel.

    This dataset deliberately includes planned requests. They are useful
    labels for approval, capability, budget, and product-friction analysis,
    even though they are not safe execution-outcome rows yet.
    """
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    by_run: dict[str, list[dict[str, Any]]] = {}
    requests: dict[str, dict[str, Any]] = {}
    for event in events:
        run_id = str(event["workflow_run_id"])
        by_run.setdefault(run_id, []).append(event)
        if event.get("event_type") == "WorkflowRequested":
            requests.setdefault(run_id, event)

    snapshots = {
        snapshot["workflow_run_id"]: snapshot for snapshot in store.snapshots()
    }
    rows: list[dict[str, Any]] = []
    for run_id, event in requests.items():
        payload = event.get("payload") or {}
        snapshot = snapshots.get(run_id, {})
        run_events = by_run.get(run_id, [])
        state = str(snapshot.get("state", "unknown"))
        rows.append(
            {
                "workflow_run_id": run_id,
                "trace_id": event.get("trace_id", run_id),
                "task_id": payload.get("task_id"),
                "workflow": payload.get("workflow"),
                "operation_level": payload.get("operation_level"),
                "approval_required": bool(payload.get("approval_required")),
                "evidence_plan_count": len(payload.get("evidence_plan") or []),
                "knowledge_ref_digest": payload.get("knowledge_ref_digest"),
                "scene_binding": payload.get("scene_binding"),
                "request_event_id": event.get("event_id"),
                "requested_at": payload.get("requested_at") or event.get("occurred_at"),
                "duration_seconds": _duration_seconds(run_events),
                "labels": {
                    "current_state": state,
                    "admitted": snapshot.get("admission") is not None,
                    "gate_outcome": (
                        "admitted"
                        if snapshot.get("admission") is not None
                        else "pending_admission"
                        if state == "planned"
                        else state
                    ),
                },
                "label_source": {
                    "event_log": "_knowledge/workflow-mesh/events.jsonl",
                    "event_ids": [str(item["event_id"]) for item in run_events],
                    "labeling_rule": f"{REQUEST_EVAL_SCHEMA_VERSION}:event-derived",
                },
            }
        )

    dataset = {
        "dataset_version": REQUEST_EVAL_SCHEMA_VERSION,
        "source": {
            "kind": "omo_append_only_event_log",
            "path": "_knowledge/workflow-mesh/events.jsonl",
            "labels_are_event_derived": True,
        },
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "states": dict(
                Counter(row["labels"]["current_state"] for row in rows)
            ),
            "approval_required_count": sum(
                row["approval_required"] for row in rows
            ),
            "admitted_count": sum(row["labels"]["admitted"] for row in rows),
        },
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return dataset


def evaluate_policy(
    dataset: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate a candidate gate policy against labeled rows, without applying it."""
    rows = list(dataset.get("rows", []))
    require_admission = bool(candidate.get("require_admission", True))
    require_evidence_for_verify = bool(
        candidate.get("require_evidence_for_verify", True)
    )
    admitted_rows = [
        row
        for row in rows
        if not require_admission or row["labels"].get("admitted", False)
    ]
    unsafe = [
        row
        for row in admitted_rows
        if (not require_admission and not row["labels"].get("admitted", False))
        or (
            require_evidence_for_verify
            and row["labels"].get("verified", False)
            and not row["labels"].get("evidence_complete", False)
        )
    ]
    successes = sum(row["labels"].get("outcome") == "success" for row in admitted_rows)
    baseline_successes = sum(
        row["labels"].get("outcome") == "success" for row in rows
    )
    result = {
        "candidate": candidate,
        "rows_considered": len(rows),
        "rows_admitted_by_candidate": len(admitted_rows),
        "unsafe_rows": len(unsafe),
        "success_rate": round(successes / len(admitted_rows), 4)
        if admitted_rows
        else 0.0,
        "baseline_success_rate": round(baseline_successes / len(rows), 4)
        if rows
        else 0.0,
        "offline_gate_passed": bool(admitted_rows) and not unsafe,
        "not_applied": True,
    }
    return result


def propose_policy_feedback(
    dataset: dict[str, Any], candidate: dict[str, Any], *, proposal_id: str
) -> dict[str, Any]:
    """Return an auditable proposal; production policy mutation is out of scope."""
    evaluation = evaluate_policy(dataset, candidate)
    return {
        "proposal_id": proposal_id,
        "status": "proposal_only",
        "source_dataset_version": dataset.get("dataset_version"),
        "evaluation": evaluation,
        "requires_human_approval": True,
        "apply_ref": None,
        "decision": "eligible_for_review"
        if evaluation["offline_gate_passed"]
        else "rejected_offline",
    }


def _selection_run_outcome(
    run_events: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> str:
    event_types = {str(event.get("event_type")) for event in run_events}
    if not run_events:
        return "not_executed"
    if "WorkflowFailed" in event_types or "StepFailed" in event_types:
        return "failed"
    if "BackendUnavailable" in event_types or "WorkerLeaseExpired" in event_types:
        return "unavailable"
    if any(item.get("result_state") == "degraded" for item in evidence):
        return "degraded"
    if "WorkflowSucceeded" in event_types:
        return "success"
    return "incomplete"


def build_external_resource_selection_dataset(
    omo_dir: Path | str,
    *,
    scene_id: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Join safe selection observations with Mesh receipts and human feedback.

    The join is intentionally read-only. A selection without a matching run is
    retained as ``not_executed`` so the dataset distinguishes lack of evidence
    from failure; it is never promoted to a success label.
    """
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    snapshots = {snapshot["workflow_run_id"]: snapshot for snapshot in store.snapshots()}
    events_by_run: dict[str, list[dict[str, Any]]] = {}
    runs_by_trace: dict[str, set[str]] = {}
    for event in events:
        run_id = str(event["workflow_run_id"])
        events_by_run.setdefault(run_id, []).append(event)
        runs_by_trace.setdefault(str(event.get("trace_id", run_id)), set()).add(run_id)

    feedback_by_run: dict[str, list[dict[str, Any]]] = {}
    for feedback in read_outcome_feedback(omo_dir):
        feedback_by_run.setdefault(str(feedback["workflow_run_id"]), []).append(feedback)

    rows: list[dict[str, Any]] = []
    for observation in read_external_resource_evaluations(omo_dir):
        binding = observation.get("scene_binding") or {}
        if scene_id is not None and binding.get("scene_id") != scene_id:
            continue
        requested_run_id = str(observation.get("workflow_run_id") or "").strip() or None
        trace_id = str(observation.get("trace_id") or "")
        trace_runs = runs_by_trace.get(trace_id, set())
        run_id = requested_run_id
        join_status = "explicit" if requested_run_id else "unbound"
        if run_id is None and len(trace_runs) == 1:
            run_id = next(iter(trace_runs))
            join_status = "trace_match"
        elif run_id is None and len(trace_runs) > 1:
            join_status = "ambiguous_trace"

        run_events = events_by_run.get(run_id or "", [])
        snapshot = snapshots.get(run_id or "", {})
        evidence = [
            item
            for item in (snapshot.get("evidence") or {}).values()
            if isinstance(item, dict) and item.get("resource_id")
        ]
        receipts = [
            item
            for item in evidence
            if item.get("evidence_schema") == "external-connection-receipt/v1"
        ]
        selected_resource_id = observation.get("selected_resource_id")
        used_resource_ids = {str(item["resource_id"]) for item in receipts}
        if not run_id:
            alignment = "not_executed"
        elif not selected_resource_id:
            alignment = "no_selection"
        elif not receipts:
            alignment = "missing_receipt"
        elif selected_resource_id in used_resource_ids:
            alignment = "aligned"
        else:
            alignment = "different_resource"

        feedback = [
            item
            for item in feedback_by_run.get(run_id or "", [])
            if item.get("consumption_state") != "rejected"
        ]
        outcome = _selection_run_outcome(run_events, evidence)
        labels = {
            "execution_outcome": outcome,
            "selection_alignment": alignment,
            "consumption_state": feedback[0]["consumption_state"] if feedback else "unobserved",
            "terminal": "WorkflowClosed" in {str(event.get("event_type")) for event in run_events},
            "verified": "WorkflowVerified" in {str(event.get("event_type")) for event in run_events},
            "evidence_complete": bool(evidence),
            "label_quality": (
                "execution_and_consumption"
                if feedback and outcome not in {"not_executed", "incomplete"}
                else "execution"
                if run_events
                else "unbound"
            ),
        }
        rows.append(
            {
                "evaluation_id": observation["evaluation_id"],
                "workflow_run_id": run_id,
                "trace_id": trace_id,
                "scene_binding": binding,
                "features": {
                    "capability": observation["capability"],
                    "selected_resource_id": selected_resource_id,
                    "candidate_count": observation["summary"]["candidate_count"],
                    "eligible_count": observation["summary"]["eligible_count"],
                    "rejected_count": observation["summary"]["rejected_count"],
                    "selected_decision_factors": next(
                        (
                            item["decision_factors"]
                            for item in observation["candidates"]
                            if item["resource_id"] == selected_resource_id
                        ),
                        {},
                    ),
                },
                "labels": labels,
                "join": {"status": join_status, "receipt_count": len(receipts)},
                "label_source": {
                    "evaluation_observation_id": observation["observation_id"],
                    "event_ids": [str(event["event_id"]) for event in run_events],
                    "receipt_ids": [str(item["receipt_id"]) for item in receipts if item.get("receipt_id")],
                    "feedback_ids": [str(item["feedback_id"]) for item in feedback],
                    "labeling_rule": f"{SELECTION_EVAL_SCHEMA_VERSION}:event-receipt-feedback-join",
                },
            }
        )

    dataset = {
        "dataset_version": SELECTION_EVAL_SCHEMA_VERSION,
        "source": {
            "kind": "omo_external_evaluation_log_joined_with_mesh",
            "evaluation_log": "_knowledge/workflow-mesh/external-resource-evaluations.jsonl",
            "event_log": "_knowledge/workflow-mesh/events.jsonl",
            "outcome_feedback_log": "_knowledge/workflow-mesh/outcome-feedback.jsonl",
            "raw_content_policy": "never_read_or_export",
        },
        "filter": {"scene_id": scene_id},
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "linked_run_count": sum(bool(row["workflow_run_id"]) for row in rows),
            "executed_count": sum(
                row["labels"]["execution_outcome"] not in {"not_executed", "incomplete"}
                for row in rows
            ),
            "aligned_count": sum(row["labels"]["selection_alignment"] == "aligned" for row in rows),
            "outcomes": dict(Counter(row["labels"]["execution_outcome"] for row in rows)),
            "label_quality": dict(Counter(row["labels"]["label_quality"] for row in rows)),
        },
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dataset


def evaluate_selection_policy(
    dataset: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Compare a selection policy offline; never apply it to routing or admission."""
    max_unaligned_rate = float(candidate.get("max_unaligned_rate", 0.2))
    if not 0 <= max_unaligned_rate <= 1:
        raise ValueError("max_unaligned_rate must be between 0 and 1")
    rows = [
        row
        for row in dataset.get("rows", [])
        if row.get("labels", {}).get("execution_outcome")
        not in {"not_executed", "incomplete"}
    ]
    unaligned = sum(
        row.get("labels", {}).get("selection_alignment") == "different_resource"
        for row in rows
    )
    successful = sum(row.get("labels", {}).get("execution_outcome") == "success" for row in rows)
    aligned_successful = sum(
        row.get("labels", {}).get("execution_outcome") == "success"
        and row.get("labels", {}).get("selection_alignment") == "aligned"
        for row in rows
    )
    return {
        "candidate": candidate,
        "dataset_version": dataset.get("dataset_version"),
        "rows_considered": len(rows),
        "unaligned_count": unaligned,
        "unaligned_rate": round(unaligned / len(rows), 4) if rows else None,
        "success_rate": round(successful / len(rows), 4) if rows else None,
        "aligned_success_rate": round(aligned_successful / len(rows), 4) if rows else None,
        "offline_gate_passed": bool(rows) and (unaligned / len(rows)) <= max_unaligned_rate,
        "not_applied": True,
    }


def propose_selection_policy_feedback(
    dataset: dict[str, Any], candidate: dict[str, Any], *, proposal_id: str
) -> dict[str, Any]:
    """Create a reviewable selection proposal without changing production policy."""
    evaluation = evaluate_selection_policy(dataset, candidate)
    return {
        "proposal_id": proposal_id,
        "status": "proposal_only",
        "source_dataset_version": dataset.get("dataset_version"),
        "evaluation": evaluation,
        "requires_human_approval": True,
        "apply_ref": None,
        "decision": "eligible_for_review"
        if evaluation["offline_gate_passed"]
        else "rejected_offline",
    }


def _operations_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _scene_key(binding: dict[str, str] | None) -> str:
    if not binding:
        return "_unbound"
    return " / ".join(
        binding[field]
        for field in ("scene_id", "journey_id", "outcome_metric")
    )


def _review_item(
    snapshot: dict[str, Any], event_types: set[str]
) -> dict[str, Any] | None:
    state = str(snapshot.get("state", "unknown"))
    action_by_state = {
        "waiting_approval": ("approval", "review_pending_approval", "审批待处理"),
        "failed": ("recovery", "recover_failed_run", "失败运行待恢复"),
        "unavailable": ("recovery", "restore_backend_or_reclaim", "后端不可用待恢复"),
        "succeeded": ("verification", "verify_with_evidence", "成功运行待验证"),
        "verified": ("delivery", "merge_or_close", "已验证运行待交付收口"),
        "merged": ("closeout", "close_run", "已合并运行待关闭"),
    }
    if state in action_by_state:
        category, action, title = action_by_state[state]
    elif state == "closed" and not snapshot.get("scene_binding"):
        category, action, title = "attribution", "bind_scene_for_review", "已关闭运行缺少场景归因"
    elif state == "closed" and not snapshot.get("evidence"):
        category, action, title = "evidence", "review_missing_evidence", "已关闭运行缺少证据"
    else:
        return None

    return {
        "workflow_run_id": snapshot["workflow_run_id"],
        "state": state,
        "category": category,
        "recommended_action": action,
        "title": title,
        "scene_binding": snapshot.get("scene_binding"),
        "last_event_type": snapshot.get("last_event_type"),
        "event_count": snapshot.get("event_count", 0),
        "recovered": "WorkflowRecovered" in event_types,
    }


def build_operations_snapshot(
    omo_dir: Path | str,
    *,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Build the read-only operational projection from OMO's event truth.

    This projection is derived from OMO's event and outcome-feedback logs. It
    reports consumption only when an explicit feedback record exists; closure,
    verification, or evidence presence must not be treated as consumption.
    """
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    by_run: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_run.setdefault(str(event["workflow_run_id"]), []).append(event)

    snapshots = store.snapshots()
    if scene_id is not None:
        snapshots = [
            snapshot
            for snapshot in snapshots
            if (snapshot.get("scene_binding") or {}).get("scene_id") == scene_id
        ]
    feedback_records = read_outcome_feedback(omo_dir)
    selected_run_ids = {snapshot["workflow_run_id"] for snapshot in snapshots}
    feedback_by_run: dict[str, list[dict[str, Any]]] = {}
    for feedback in feedback_records:
        run_id = str(feedback["workflow_run_id"])
        if run_id in selected_run_ids:
            feedback_by_run.setdefault(run_id, []).append(feedback)

    state_counts: Counter[str] = Counter()
    scene_rows: dict[str, dict[str, Any]] = {}
    review_queue: list[dict[str, Any]] = []
    durations: list[float] = []
    admitted_runs = 0
    success_runs = 0
    verified_runs = 0
    merged_runs = 0
    closed_runs = 0
    evidence_complete_runs = 0
    recovered_runs = 0
    approval_runs = 0
    retry_runs = 0
    failed_runs = 0
    unavailable_runs = 0
    sandbox_tool_invocations = 0
    sandbox_tool_receipt_runs = 0

    for snapshot in snapshots:
        run_events = by_run.get(snapshot["workflow_run_id"], [])
        event_types = {str(event["event_type"]) for event in run_events}
        state = str(snapshot.get("state", "unknown"))
        state_counts[state] += 1
        binding = snapshot.get("scene_binding")
        key = _scene_key(binding)
        scene = scene_rows.setdefault(
            key,
            {
                "scene_binding": binding,
                "run_count": 0,
                "succeeded_runs": 0,
                "verified_runs": 0,
                "closed_runs": 0,
                "evidence_complete_runs": 0,
                "sandbox_tool_runs": 0,
                "consumed_runs": 0,
                "feedback_count": 0,
            },
        )
        scene["run_count"] += 1

        if snapshot.get("admission") is not None:
            admitted_runs += 1
        succeeded = "WorkflowSucceeded" in event_types
        verified = "WorkflowVerified" in event_types
        closed = "WorkflowClosed" in event_types
        evidence_complete = bool(snapshot.get("evidence"))
        sandbox_invocations = [
            event
            for event in run_events
            if event.get("event_type") == "ToolInvocationRecorded"
        ]
        if sandbox_invocations:
            sandbox_tool_invocations += len(sandbox_invocations)
            sandbox_tool_receipt_runs += int(evidence_complete)
            scene["sandbox_tool_runs"] += 1
        if succeeded:
            success_runs += 1
            scene["succeeded_runs"] += 1
        if verified:
            verified_runs += 1
            scene["verified_runs"] += 1
        if "PRMerged" in event_types:
            merged_runs += 1
        if closed:
            closed_runs += 1
            scene["closed_runs"] += 1
        if evidence_complete:
            evidence_complete_runs += 1
            scene["evidence_complete_runs"] += 1
        if "WorkflowRecovered" in event_types:
            recovered_runs += 1
        if "ApprovalRequested" in event_types:
            approval_runs += 1
        if "StepRetryScheduled" in event_types:
            retry_runs += 1
        if "WorkflowFailed" in event_types or "StepFailed" in event_types:
            failed_runs += 1
        if "BackendUnavailable" in event_types or "WorkerLeaseExpired" in event_types:
            unavailable_runs += 1
        run_feedback = feedback_by_run.get(snapshot["workflow_run_id"], [])
        consumed_feedback = [
            item for item in run_feedback if item["consumption_state"] != "rejected"
        ]
        scene["feedback_count"] += len(run_feedback)
        if consumed_feedback:
            scene["consumed_runs"] += 1
        duration = _duration_seconds(run_events)
        if duration is not None:
            durations.append(duration)
        item = _review_item(snapshot, event_types)
        if item is not None:
            review_queue.append(item)

    request_rows = build_request_eval_dataset(omo_dir)["rows"]
    if scene_id is not None:
        request_rows = [
            row
            for row in request_rows
            if (row.get("scene_binding") or {}).get("scene_id") == scene_id
        ]
    request_states = Counter(
        row["labels"]["current_state"] for row in request_rows
    )
    workflow_requests = {
        "request_count": len(request_rows),
        "pending_count": sum(
            row["labels"]["current_state"] == "planned" for row in request_rows
        ),
        "admitted_count": sum(row["labels"]["admitted"] for row in request_rows),
        "approval_required_count": sum(
            row["approval_required"] for row in request_rows
        ),
        "states": dict(sorted(request_states.items())),
        "next_action": (
            "review_pending_workflow_requests"
            if any(row["labels"]["current_state"] == "planned" for row in request_rows)
            else "record_more_workflow_requests"
        ),
    }

    active_runs = sum(
        count for state, count in state_counts.items() if state not in {"closed", "cancelled"}
    )
    consumed_feedback = [
        item
        for items in feedback_by_run.values()
        for item in items
        if item["consumption_state"] != "rejected"
    ]
    eligible_closed_runs = sum(
        1
        for snapshot in snapshots
        if snapshot.get("state") == "closed" and snapshot.get("evidence")
    )
    consumed_run_ids = {item["workflow_run_id"] for item in consumed_feedback}
    feedback_states = Counter(
        item["consumption_state"]
        for items in feedback_by_run.values()
        for item in items
    )
    eligible_outcomes = [
        {
            "workflow_run_id": snapshot["workflow_run_id"],
            "outcome_id": f"outcome:{snapshot['workflow_run_id']}",
            "state": snapshot.get("state"),
            "scene_binding": snapshot.get("scene_binding"),
            "evidence_count": len(snapshot.get("evidence") or []),
        }
        for snapshot in snapshots
        if snapshot.get("state") in ELIGIBLE_WORKFLOW_STATES
        and snapshot.get("scene_binding")
    ]
    consumption = {
        "status": (
            "observed"
            if consumed_feedback
            else "rejected"
            if feedback_by_run
            else "not_observed"
        ),
        "consumed_runs": len(consumed_run_ids),
        "feedback_count": sum(len(items) for items in feedback_by_run.values()),
        "observed_event_types": [],
        "eligible_closed_runs": eligible_closed_runs,
        "consumption_rate_among_eligible_closed_runs": _operations_rate(
            len(consumed_run_ids), eligible_closed_runs
        ),
        "states": dict(sorted(feedback_states.items())),
        "eligible_outcomes": eligible_outcomes,
        "feedback": [
            {
                key: item[key]
                for key in (
                    "feedback_id",
                    "workflow_run_id",
                    "outcome_id",
                    "scene_binding",
                    "consumption_state",
                    "consumer_ref",
                    "result_ref",
                    "evidence_refs",
                    "value",
                    "observed_at",
                    "recorded_at",
                )
            }
            for items in feedback_by_run.values()
            for item in items
        ],
        "next_action": (
            "review_feedback_and_value"
            if consumed_feedback
            else "record_explicit_outcome_consumption_feedback"
        ),
    }
    return {
        "schema_version": OPERATIONS_SCHEMA_VERSION,
        "status": "live",
        "source": {
            "kind": "omo_append_only_event_log",
            "path": "_knowledge/workflow-mesh/events.jsonl",
            "projection": "event_derived",
        },
        "filter": {"scene_id": scene_id},
        "summary": {
            "run_count": len(snapshots),
            "active_runs": active_runs,
            "admitted_runs": admitted_runs,
            "succeeded_runs": success_runs,
            "failed_runs": failed_runs,
            "unavailable_runs": unavailable_runs,
            "verified_runs": verified_runs,
            "merged_runs": merged_runs,
            "closed_runs": closed_runs,
            "evidence_complete_runs": evidence_complete_runs,
            "recovered_runs": recovered_runs,
            "approval_runs": approval_runs,
            "retry_runs": retry_runs,
            "average_duration_seconds": round(sum(durations) / len(durations), 3)
            if durations
            else None,
            "rates": {
                "success_rate_among_admitted": _operations_rate(success_runs, admitted_runs),
                "verification_rate_among_succeeded": _operations_rate(verified_runs, success_runs),
                "closeout_rate_among_verified": _operations_rate(closed_runs, verified_runs),
            },
            "states": dict(sorted(state_counts.items())),
        },
        "by_scene": sorted(
            scene_rows.values(),
            key=lambda row: _scene_key(row.get("scene_binding")),
        ),
        "review_queue": review_queue,
        "workflow_requests": workflow_requests,
        "consumption": consumption,
        "sandbox_tools": {
            "status": "observed" if sandbox_tool_invocations else "not_observed",
            "activation": "sandbox",
            "external_side_effects": "disabled",
            "invocation_count": sandbox_tool_invocations,
            "receipt_run_count": sandbox_tool_receipt_runs,
            "next_action": (
                "review_sandbox_receipt_and_promote_only_with_real_scene"
                if sandbox_tool_invocations
                else "run_one_admitted_sandbox_tool_probe"
            ),
        },
        "knowledge_action": build_knowledge_action_snapshot(omo_dir, scene_id=scene_id),
    }


__all__ = [
    "OPERATIONS_SCHEMA_VERSION",
    "SELECTION_EVAL_SCHEMA_VERSION",
    "build_eval_dataset",
    "build_external_resource_selection_dataset",
    "build_operations_snapshot",
    "build_request_eval_dataset",
    "evaluate_policy",
    "evaluate_selection_policy",
    "propose_policy_feedback",
    "propose_selection_policy_feedback",
]
