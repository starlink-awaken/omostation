"""Work-case API projection.

The route intentionally fails closed until a governed OMO work-case projection
is registered.  It must never fabricate operational cases for the Cockpit UI.
"""

from fastapi import APIRouter, HTTPException, Query

from cockpit.web.api_tasks_data import get_tasks_from_omo

router = APIRouter(tags=["work-cases"])


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
        items.append(
            {
                "id": task["id"],
                "title": task["title"],
                "status": work_case.get("status", "planned"),
                "risk": work_case.get("risk", "medium"),
                "next_action": work_case.get("next_action", "等待案件方案生成"),
            }
        )
    return {"items": items}
