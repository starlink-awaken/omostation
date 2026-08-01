"""Event-derived Workflow Mesh evaluation dataset and policy proposals."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .workflow_mesh import WorkflowMeshStore


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


__all__ = ["build_eval_dataset", "evaluate_policy", "propose_policy_feedback"]
