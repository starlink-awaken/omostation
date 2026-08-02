"""只读投影：判断外部场景试运行是否具备晋升为正式 Workflow 的条件。

本模块只消费已经落盘的试运行、评审、Workflow Mesh 运行、外部 receipt 和
结果反馈。它不创建 WorkflowRun、不执行 admission、不调用 provider，也不改变
任何准入状态。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .omo_external_receipt import RECEIPT_SCHEMA
from .omo_external_scene_trial import read_external_scene_trials
from .omo_external_scene_trial_feedback import read_external_scene_trial_feedback
from .outcome_feedback import (
    ELIGIBLE_WORKFLOW_STATES,
    OUTCOME_FEEDBACK_SCHEMA,
    read_outcome_feedback,
)
from .workflow_mesh import WorkflowMeshStore

READINESS_SCHEMA = "external-scene-trial-promotion-readiness/v1"
_REVIEW_ACTION = "continue"
_POSITIVE_FEEDBACK_STATES = frozenset(
    {"reviewed", "adopted", "submitted", "dispatched", "cited"}
)
_SCENE_FIELDS = ("scene_id", "journey_id", "outcome_metric")


def _scene_binding(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    result = {field: str(value.get(field) or "").strip() for field in _SCENE_FIELDS}
    return result if all(result.values()) else None


def _same_scene(left: Any, right: Any) -> bool:
    left_binding = _scene_binding(left)
    right_binding = _scene_binding(right)
    return left_binding is not None and left_binding == right_binding


def _latest_reviews(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        trial_id = str(record.get("trial_id") or "").strip()
        if trial_id:
            latest[trial_id] = record
    return latest


def _receipt_summaries(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = snapshot.get("evidence")
    if not isinstance(evidence, Mapping):
        return []
    receipts: list[dict[str, Any]] = []
    for value in evidence.values():
        if not isinstance(value, Mapping):
            continue
        if value.get("evidence_schema") != RECEIPT_SCHEMA:
            continue
        receipt_id = str(value.get("receipt_id") or "").strip()
        result_state = str(value.get("result_state") or "").strip()
        if not receipt_id or result_state not in {"succeeded", "degraded"}:
            continue
        receipts.append(
            {
                "receipt_id": receipt_id,
                "resource_id": str(value.get("resource_id") or "").strip(),
                "result_state": result_state,
                "observed_at": str(value.get("observed_at") or "").strip(),
            }
        )
    return receipts


def _feedback_summaries(
    feedback: list[dict[str, Any]], run_ids: set[str], binding: Mapping[str, str]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in feedback:
        run_id = str(record.get("workflow_run_id") or "").strip()
        if run_id not in run_ids or not _same_scene(record.get("scene_binding"), binding):
            continue
        result.append(
            {
                "feedback_id": str(record.get("feedback_id") or "").strip(),
                "outcome_id": str(record.get("outcome_id") or "").strip(),
                "consumption_state": str(record.get("consumption_state") or "").strip(),
                "consumer_ref": str(record.get("consumer_ref") or "").strip(),
                "observed_at": str(record.get("observed_at") or "").strip(),
            }
        )
    return result


def _item(
    trial: Mapping[str, Any],
    review: Mapping[str, Any] | None,
    snapshots: list[Mapping[str, Any]],
    feedback: list[dict[str, Any]],
) -> dict[str, Any]:
    binding = _scene_binding(trial.get("scene_binding"))
    assert binding is not None
    matching = [
        snapshot
        for snapshot in snapshots
        if _same_scene(snapshot.get("scene_binding"), binding)
    ]
    run_ids = {
        str(snapshot.get("workflow_run_id") or "").strip()
        for snapshot in matching
        if str(snapshot.get("workflow_run_id") or "").strip()
    }
    eligible = [
        snapshot
        for snapshot in matching
        if snapshot.get("state") in ELIGIBLE_WORKFLOW_STATES
    ]
    receipts: list[dict[str, Any]] = []
    for snapshot in eligible:
        receipts.extend(_receipt_summaries(snapshot))
    outcome_records = _feedback_summaries(feedback, {
        str(snapshot.get("workflow_run_id") or "").strip() for snapshot in eligible
    }, binding)
    positive_outcomes = [
        record
        for record in outcome_records
        if record["consumption_state"] in _POSITIVE_FEEDBACK_STATES
    ]
    rejected_outcomes = [
        record for record in outcome_records if record["consumption_state"] == "rejected"
    ]

    checks = {
        "trial_recorded": True,
        "review_continued": bool(review and review.get("review_action") == _REVIEW_ACTION),
        "workflow_run_present": bool(run_ids),
        "workflow_run_eligible": bool(eligible),
        "external_receipt_recorded": bool(receipts),
        "outcome_feedback_recorded": bool(positive_outcomes),
    }
    blockers: list[str] = []
    if review is None:
        blockers.append("review_missing")
    elif review.get("review_action") != _REVIEW_ACTION:
        blockers.append("review_not_continued")
    if not run_ids:
        blockers.append("workflow_run_missing")
    elif not eligible:
        blockers.append("workflow_run_not_eligible")
    if eligible and not receipts:
        blockers.append("external_receipt_missing")
    if rejected_outcomes:
        blockers.append("outcome_feedback_rejected")
    elif not positive_outcomes:
        blockers.append("outcome_feedback_missing")

    return {
        "trial_id": trial.get("trial_id"),
        "scene_binding": binding,
        "consumer_ref": trial.get("consumer_ref"),
        "metric": trial.get("metric"),
        "latest_review": (
            {
                "feedback_id": review.get("feedback_id"),
                "review_action": review.get("review_action"),
                "reviewer_ref": review.get("reviewer_ref"),
                "review_ref": review.get("review_ref"),
                "observed_at": review.get("observed_at"),
            }
            if review
            else None
        ),
        "checks": checks,
        "matched_workflow_run_ids": sorted(run_ids),
        "workflow_states": sorted(
            {str(snapshot.get("state")) for snapshot in matching if snapshot.get("state")}
        ),
        "external_receipts": receipts,
        "outcome_feedback": outcome_records,
        "blockers": blockers,
        "status": "ready" if not blockers else "blocked",
        "next_action": (
            "可提交正式 Workflow Mesh 晋升提案；本投影不会自动晋升或激活。"
            if not blockers
            else "补齐阻断项后重新评估；当前仅允许 proposal-only 试运行。"
        ),
    }


def build_external_scene_trial_promotion_readiness(
    omo_dir: Path | str, *, scene_id: str | None = None
) -> dict[str, Any]:
    """构建一个不产生副作用的外部场景晋升就绪度快照。"""
    root = Path(omo_dir)
    trials = read_external_scene_trials(root)
    reviews = _latest_reviews(read_external_scene_trial_feedback(root))
    feedback = read_outcome_feedback(root)
    snapshots = WorkflowMeshStore(root).snapshots()
    items = []
    for trial in trials:
        binding = _scene_binding(trial.get("scene_binding"))
        if binding is None or (scene_id and binding["scene_id"] != scene_id):
            continue
        trial_id = str(trial.get("trial_id") or "").strip()
        items.append(_item(trial, reviews.get(trial_id), snapshots, feedback))
    ready_count = sum(item["status"] == "ready" for item in items)
    blocked_count = len(items) - ready_count
    status = "empty" if not items else ("ready" if ready_count else "blocked")
    return {
        "schema": READINESS_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": "forbidden",
        "admission_mutation": "forbidden",
        "external_side_effects": "disabled",
        "raw_content_policy": "never_read_or_export",
        "source": "omo.external_scene_trial_promotion_readiness",
        "status": status,
        "scene_id": scene_id,
        "items": items,
        "summary": {
            "trial_count": len(items),
            "ready_count": ready_count,
            "blocked_count": blocked_count,
        },
        "next_action": (
            "先记录场景试运行和人工评审，再等待真实消费者 WorkflowRun、外部 receipt 与结果反馈。"
            if not items
            else "只对 status=ready 的场景提交人工晋升提案；系统不会自动改变准入状态。"
        ),
    }


__all__ = [
    "READINESS_SCHEMA",
    "build_external_scene_trial_promotion_readiness",
]
