"""Read-only Workflow Mesh operations projection for Cockpit."""

from __future__ import annotations

import datetime
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

try:
    from fastapi import APIRouter, Query, Request
except ImportError:
    APIRouter = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]
    Request = None  # type: ignore[assignment,misc]


_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.omo_external_receipt import (
        ExternalReceiptError,
        record_external_receipt,
    )
    from omo.outcome_feedback import OutcomeFeedbackError, record_outcome_feedback
    from omo.workflow_eval import build_operations_snapshot
except Exception as exc:  # OMO is an optional runtime dependency for Cockpit.
    build_operations_snapshot = None  # type: ignore[assignment]
    record_external_receipt = None  # type: ignore[assignment]
    record_outcome_feedback = None  # type: ignore[assignment]
    ExternalReceiptError = ValueError  # type: ignore[assignment,misc]
    OutcomeFeedbackError = ValueError  # type: ignore[assignment,misc]
    _OMO_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_IMPORT_ERROR = None


router = APIRouter(prefix="/api/workflow-mesh", tags=["workflow-mesh"]) if APIRouter else None
_AGORA_HTTP_ENDPOINT = os.environ.get("AGORA_HTTP_ENDPOINT", "http://127.0.0.1:7422")
_logger = logging.getLogger(__name__)


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


async def _read_capability_health(required_capabilities: list[str]) -> dict[str, Any]:
    """Read Agora's evidence projection without creating a connection or run."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.post(
            f"{_AGORA_HTTP_ENDPOINT}/v1/tools/call",
            json={
                "name": "workflow_capability_health",
                "arguments": {"required_capabilities": required_capabilities},
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Agora capability health returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise RuntimeError("Agora capability health response is invalid")
    health = payload.get("result")
    if not isinstance(health, dict) or health.get("source") != "agora.workflow_health":
        raise RuntimeError("Agora capability health projection is missing provenance")
    return health


if router:

    @router.get("/capability-health")
    async def get_workflow_capability_health(
        required_capabilities: list[str] = Query(default=[]),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Expose server-owned health evidence for the admission preview flow."""
        capabilities = list(dict.fromkeys(item.strip() for item in required_capabilities if item.strip()))
        if not capabilities:
            return {
                "ok": False,
                "status": "invalid",
                "error": "required_capabilities_required",
                "message": "至少需要一个 required_capabilities。",
            }
        try:
            health = await _read_capability_health(capabilities)
        except (httpx.HTTPError, OSError, RuntimeError, ValueError, TypeError) as exc:
            _logger.info("workflow_capability_health_unavailable: %s", type(exc).__name__)
            return {
                "ok": False,
                "status": "unavailable",
                "error": "capability_health_unavailable",
                "message": "Agora capability health 不可用，已停止准入链路。",
                "required_capabilities": capabilities,
                "external_side_effects": "disabled",
                "worker_launch": False,
            }
        return {
            "ok": True,
            "status": health.get("status", "unhealthy"),
            "source": health["source"],
            "observed_at": health.get("observed_at"),
            "required_capabilities": capabilities,
            "capability_health": health,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }

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

    @router.post("/outcome-feedback")
    async def post_workflow_mesh_outcome_feedback(request: Request) -> dict[str, Any]:  # type: ignore[valid-type]
        """Persist an explicit, privacy-safe consumption receipt through OMO."""
        if record_outcome_feedback is None:
            projection = _unavailable_projection(
                type(_OMO_IMPORT_ERROR).__name__ if _OMO_IMPORT_ERROR else "ImportError",
                "安装并挂载 OMO 运行时后重试。",
            )
            return {"ok": False, "status": "unavailable", "feedback": projection}
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise OutcomeFeedbackError("feedback payload must be an object")
            payload = dict(payload)
            actor = str(payload.pop("actor_ref", "cockpit-user") or "cockpit-user")
            result = record_outcome_feedback(_REPO_ROOT / ".omo", payload, actor=actor)
        except (OutcomeFeedbackError, ValueError, TypeError) as exc:
            return {
                "ok": False,
                "status": "invalid",
                "error": "outcome_feedback_invalid",
                "message": str(exc),
            }
        except OSError as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "error": "outcome_feedback_unavailable",
                "message": f"反馈持久化不可用: {type(exc).__name__}",
            }
        return {
            "ok": True,
            "status": result["status"],
            "feedback": result["feedback"],
        }

    @router.post("/external-receipt")
    async def post_workflow_mesh_external_receipt(request: Request) -> dict[str, Any]:  # type: ignore[valid-type]
        """Persist a safe receipt from an already completed external operation."""
        if record_external_receipt is None:
            projection = _unavailable_projection(
                type(_OMO_IMPORT_ERROR).__name__ if _OMO_IMPORT_ERROR else "ImportError",
                "安装并挂载 OMO 运行时后重试。",
            )
            return {"ok": False, "status": "unavailable", "receipt": projection}
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ExternalReceiptError("receipt payload must be an object")
            allowed = {"workflow_run_id", "step_run_id", "producer", "receipt"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise ExternalReceiptError(f"unsupported receipt envelope fields: {unknown}")
            receipt = payload.get("receipt")
            result = record_external_receipt(
                _REPO_ROOT / ".omo",
                receipt,
                workflow_run_id=str(payload.get("workflow_run_id") or ""),
                step_run_id=str(payload.get("step_run_id") or "").strip() or None,
                producer=str(payload.get("producer") or "cockpit-ui://workflow-mesh-operations").strip(),
            )
        except (ExternalReceiptError, ValueError, TypeError) as exc:
            return {
                "ok": False,
                "status": "invalid",
                "error": "external_receipt_invalid",
                "message": str(exc),
            }
        except OSError as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "error": "external_receipt_unavailable",
                "message": f"外部回执持久化不可用: {type(exc).__name__}",
            }
        event_payload = result.get("payload") or {}
        return {
            "ok": True,
            "status": "recorded",
            "receipt": {
                "event_id": result.get("event_id"),
                "evidence_id": event_payload.get("evidence_id"),
                "receipt_id": event_payload.get("receipt_id"),
                "workflow_run_id": result.get("workflow_run_id"),
                "resource_id": event_payload.get("resource_id"),
                "result_state": event_payload.get("result_state"),
                "observed_at": event_payload.get("observed_at"),
                "provenance_ref": event_payload.get("provenance_ref"),
            },
        }
