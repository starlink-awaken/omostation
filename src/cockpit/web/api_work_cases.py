"""Work-case API projection.

The route intentionally fails closed until a governed OMO work-case projection
is registered.  It must never fabricate operational cases for the Cockpit UI.
"""

from fastapi import APIRouter, HTTPException, Query

from cockpit.web.api_tasks_data import WORKSPACE_DIR, get_tasks_from_omo

router = APIRouter(tags=["work-cases"])


def create_work_case_draft(omo_dir, *, case_id: str, title: str, source_ref: str):
    """Late-bind the OMO ingress so a missing dependency fails closed."""
    from omo.work_case import create_work_case_draft as create_draft

    return create_draft(omo_dir, case_id=case_id, title=title, source_ref=source_ref)


def request_work_case_plan_confirmation(omo_dir, *, case_id: str, plan_digest: str):
    from omo.work_case import request_work_case_plan_confirmation as request_plan

    return request_plan(omo_dir, case_id=case_id, plan_digest=plan_digest)


def record_work_case_submission(omo_dir, *, case_id: str, unit_id: str, digest: str, valid: bool):
    from omo.work_case import record_work_case_submission as record_submission

    return record_submission(omo_dir, case_id=case_id, unit_id=unit_id, digest=digest, valid=valid)


@router.get("/api/work-cases")
async def list_work_cases(scope: str = Query(default="active")) -> dict[str, object]:
    """Project only OMO tasks explicitly marked as work cases."""
    if scope != "active":
        raise HTTPException(status_code=422, detail="unsupported work-case scope")

    items = []
    for task in get_tasks_from_omo():
        work_case = task.get("work_case")
        if not isinstance(work_case, dict):
            continue
        submissions = [item for item in work_case.get("submissions", []) if isinstance(item, dict)]
        valid_submission_units = {str(item.get("unit_id")) for item in submissions if item.get("valid") is True}
        items.append(
            {
                "id": task["id"],
                "title": task["title"],
                "status": work_case.get("status", "planned"),
                "risk": work_case.get("risk", "medium"),
                "next_action": work_case.get("next_action", "等待案件方案生成"),
                "plan_confirmed": work_case.get("plan_confirmed") is True,
                "valid_submission_count": len(valid_submission_units),
                "submission_version_count": len(submissions),
            }
        )
    return {"items": items}


@router.post("/api/work-cases/drafts")
async def create_work_case_draft_endpoint(payload: dict[str, object]) -> dict[str, object]:
    case_id = str(payload.get("case_id") or "").strip()
    title = str(payload.get("title") or "").strip()
    source_ref = str(payload.get("source_ref") or "").strip()
    if not case_id or not title or not source_ref:
        raise HTTPException(status_code=422, detail="case_id, title, and source_ref are required")
    try:
        created = create_work_case_draft(WORKSPACE_DIR / ".omo", case_id=case_id, title=title, source_ref=source_ref)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="work-case ingress is unavailable") from exc
    return {"id": created["id"], "status": created["work_case"]["status"]}


@router.post("/api/work-cases/{case_id}/plan-requests")
async def request_work_case_plan_endpoint(case_id: str, payload: dict[str, object]) -> dict[str, object]:
    plan_digest = str(payload.get("plan_digest") or "").strip()
    if not plan_digest:
        raise HTTPException(status_code=422, detail="plan_digest is required")
    try:
        request_work_case_plan_confirmation(WORKSPACE_DIR / ".omo", case_id=case_id, plan_digest=plan_digest)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="work-case plan ingress is unavailable") from exc
    return {"id": case_id, "status": "awaiting_confirmation"}


@router.post("/api/work-cases/{case_id}/submissions")
async def record_work_case_submission_endpoint(case_id: str, payload: dict[str, object]) -> dict[str, object]:
    unit_id = str(payload.get("unit_id") or "").strip()
    digest = str(payload.get("digest") or "").strip()
    valid = payload.get("valid") is True
    if not unit_id or not digest:
        raise HTTPException(status_code=422, detail="unit_id and digest are required")
    try:
        record_work_case_submission(WORKSPACE_DIR / ".omo", case_id=case_id, unit_id=unit_id, digest=digest, valid=valid)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="work-case submission ingress is unavailable") from exc
    return {"id": case_id, "status": "submission_recorded"}
