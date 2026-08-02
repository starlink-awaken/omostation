"""Knowledge-to-action receipts for the governed J2 journey."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request

_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.knowledge_action import KnowledgeActionError, build_knowledge_action_snapshot, record_knowledge_action
except Exception as exc:  # OMO is optional while Cockpit is being bootstrapped.
    build_knowledge_action_snapshot = None  # type: ignore[assignment]
    record_knowledge_action = None  # type: ignore[assignment]
    KnowledgeActionError = ValueError  # type: ignore[assignment,misc]
    _OMO_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_IMPORT_ERROR = None


router = APIRouter(prefix="/api/knowledge", tags=["knowledge-action"])


def _unavailable(error_type: str, next_action: str) -> dict[str, Any]:
    return {
        "schema_version": "knowledge-action-operations/v1",
        "status": "unavailable",
        "source": {"kind": "omo_append_only_knowledge_action_log"},
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "error_type": error_type,
        "next_action": next_action,
    }


@router.get("/action-operations")
async def get_knowledge_action_operations(
    scene_id: str | None = Query(None, description="Optional scene filter"),
) -> dict[str, Any]:
    """Return the log-derived knowledge-to-action funnel."""
    if build_knowledge_action_snapshot is None:
        projection = _unavailable(
            type(_OMO_IMPORT_ERROR).__name__ if _OMO_IMPORT_ERROR else "ImportError",
            "安装并挂载 OMO 运行时后重试。",
        )
        return {"ok": False, "status": "unavailable", "operations": projection}
    try:
        projection = build_knowledge_action_snapshot(_REPO_ROOT / ".omo", scene_id=scene_id)
    except (OSError, ValueError, TypeError) as exc:
        projection = _unavailable(type(exc).__name__, "检查知识行动日志与契约后重试。")
        return {"ok": False, "status": "unavailable", "operations": projection}
    return {"ok": True, "status": "live", "operations": projection}


@router.post("/action-receipt")
async def post_knowledge_action_receipt(request: Request) -> dict[str, Any]:
    """Persist a privacy-safe receipt; this route never stores source content."""
    if record_knowledge_action is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "knowledge_action_unavailable",
            "message": "OMO knowledge-action broker is unavailable",
        }
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise KnowledgeActionError("knowledge action payload must be an object")
        payload = dict(payload)
        actor = str(payload.pop("actor_ref", "cockpit-user") or "cockpit-user")
        result = record_knowledge_action(_REPO_ROOT / ".omo", payload, actor=actor)
    except (KnowledgeActionError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "knowledge_action_invalid",
            "message": str(exc),
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "knowledge_action_unavailable",
            "message": f"行动回执持久化不可用: {type(exc).__name__}",
        }
    return {"ok": True, "status": result["status"], "action": result["action"]}
