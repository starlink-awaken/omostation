"""Work-case API projection.

The route intentionally fails closed until a governed OMO work-case projection
is registered.  It must never fabricate operational cases for the Cockpit UI.
"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["work-cases"])


@router.get("/api/work-cases")
async def list_work_cases(scope: str = Query(default="active")) -> dict[str, object]:
    """Return the active work-case projection once its OMO owner is available."""
    del scope
    raise HTTPException(status_code=503, detail="work-case projection is unavailable")
