from __future__ import annotations


def _timestamp_slug(now: str) -> str:
    return now.replace(":", "-")


def contract_request_ref(task_id: str, now: str) -> str:
    return f".omo/workers/runs/{task_id}-contract-request-{_timestamp_slug(now)}.yaml"


def build_contract_request(
    *,
    task_id: str,
    task_ref: str,
    deliverables: list[str],
    requested_at: str,
    requested_by: str,
    request_ref: str,
) -> dict[str, object]:
    request_id = request_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "version": 1,
        "request_id": request_id,
        "task_id": task_id,
        "request_status": "requested",
        "deliverables": list(deliverables),
        "requested_at": requested_at,
        "requested_by": requested_by,
        "refs": {
            "task_ref": task_ref,
            "overlay_status_ref": ".omo/workers/governance-overlay/current.yaml",
        },
    }


def build_contract_proposal(
    *,
    task_id: str,
    task_ref: str,
    deliverables: list[str],
    requested_by: str,
    request_ref: str,
) -> dict[str, object]:
    request_id = request_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "id": f"{request_id}-proposal",
        "title": f"Declare contract deliverables for {task_id}",
        "operation_level": "L2",
        "requested_by": requested_by,
        "target": {"ref": task_ref},
        "changes": {"set": {"deliverables": list(deliverables)}},
        "change_summary": f"Declare contract deliverables for {task_id}",
        "impact": "Provides explicit write scope so governance overlay can safely advance from contract gap to launch.",
        "verification_plan": [
            "python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo",
        ],
        "rollback_plan": [
            f"Restore {task_ref} deliverables to the previous list if the declared scope is incorrect.",
        ],
        "secret_refs": [],
        "trace_id": f"trace-{request_id}",
    }
