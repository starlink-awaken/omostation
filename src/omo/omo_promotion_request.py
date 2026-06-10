from __future__ import annotations


def _timestamp_slug(now: str) -> str:
    return now.replace(":", "-")


def promotion_approval_ref(task_id: str, now: str) -> str:
    return f".omo/workers/runs/{task_id}-promotion-approval-{_timestamp_slug(now)}.yaml"


def build_promotion_approval_request(
    *,
    task_id: str,
    task_ref: str,
    requested_operation_level: str,
    requested_at: str,
    approval_ref: str,
) -> dict[str, object]:
    approval_id = approval_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "version": 1,
        "approval_id": approval_id,
        "task_id": task_id,
        "approval_status": "requested",
        "requested_operation_level": requested_operation_level,
        "approval_scope": "task.promote_apply",
        "requested_at": requested_at,
        "approved_at": None,
        "expires_at": None,
        "approver": None,
        "refs": {
            "task_ref": task_ref,
            "readiness_ref": ".omo/workers/promotion/readiness.yaml",
        },
        "evidence": {
            "request_evidence": [],
            "approval_evidence": [],
        },
    }


def build_promotion_approval_proposal(
    *,
    task_id: str,
    requested_by: str,
    approval_ref: str,
) -> dict[str, object]:
    approval_id = approval_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "id": f"{approval_id}-proposal",
        "title": f"Grant promotion approval for {task_id}",
        "operation_level": "L2",
        "requested_by": requested_by,
        "target": {"ref": approval_ref},
        "changes": {"set": {"approval_status": "granted"}},
        "change_summary": f"Grant promotion approval for {task_id}",
        "impact": "Releases a planned task into the promotion approval chain.",
        "verification_plan": [
            f"python3 scripts/omo_worker.py task promote-eval {task_id} --omo-dir .omo",
        ],
        "rollback_plan": [
            f"Set {approval_ref} approval_status back to requested if the release must be withdrawn.",
        ],
        "secret_refs": [],
        "trace_id": f"trace-{approval_id}",
    }
