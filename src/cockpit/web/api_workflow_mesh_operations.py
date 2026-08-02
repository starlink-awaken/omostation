"""Read-only Workflow Mesh operations projection for Cockpit."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

try:
    from fastapi import APIRouter, Query
except ImportError:
    APIRouter = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]


_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.workflow_eval import build_operations_snapshot
except Exception as exc:  # OMO is an optional runtime dependency for Cockpit.
    build_operations_snapshot = None  # type: ignore[assignment]
    _OMO_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_IMPORT_ERROR = None


router = APIRouter(prefix="/api/workflow-mesh", tags=["workflow-mesh"]) if APIRouter else None


def _unavailable_projection(error_type: str, next_action: str) -> dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "schema_version": "workflow-mesh-operations/v1",
        "status": "unavailable",
        "source": {"kind": "omo_append_only_event_log"},
        "generated_at": now_iso,
        "error_type": error_type,
        "next_action": next_action,
    }


if router:

    @router.get("/operations")
    async def get_workflow_mesh_operations(
        scene_id: str | None = Query(None, description="Optional scene filter"),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Return the OMO-owned operations projection without mutating state."""
        if build_operations_snapshot is None:
            projection = _unavailable_projection(
                type(_OMO_IMPORT_ERROR).__name__ if _OMO_IMPORT_ERROR else "ImportError",
                "安装并挂载 OMO 运行时后重试。",
            )
            return {"ok": False, "status": "unavailable", "operations": projection}
        try:
            projection = build_operations_snapshot(_REPO_ROOT / ".omo", scene_id=scene_id)
        except Exception as exc:  # Defensive read-only degradation for the product surface.
            projection = _unavailable_projection(
                type(exc).__name__,
                "检查 OMO 事件日志与 Workflow Mesh 事件契约后重试。",
            )
            return {"ok": False, "status": "unavailable", "operations": projection}
        return {
            "ok": projection.get("status") == "live",
            "status": projection.get("status", "unavailable"),
            "operations": projection,
        }

