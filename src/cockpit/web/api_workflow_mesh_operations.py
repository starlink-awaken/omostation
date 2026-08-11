"""Read-only Workflow Mesh operations projection for Cockpit."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx

try:
    from fastapi import APIRouter, Query, Request
except ImportError:
    APIRouter = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]
    Request = None  # type: ignore[assignment,misc]

try:
    from fastapi.responses import JSONResponse
except ImportError:
    JSONResponse = None  # type: ignore[assignment,misc]


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

try:
    from omo.engineering_delivery_consumer import (
        EngineeringDeliveryConsumerError,
        build_engineering_delivery_review_queue,
        record_engineering_delivery_review,
    )
except Exception as exc:  # Keep the existing Workflow Mesh routes independently available.
    EngineeringDeliveryConsumerError = ValueError  # type: ignore[assignment,misc]
    build_engineering_delivery_review_queue = None  # type: ignore[assignment]
    record_engineering_delivery_review = None  # type: ignore[assignment]
    _ENGINEERING_DELIVERY_IMPORT_ERROR: Exception | None = exc
else:
    _ENGINEERING_DELIVERY_IMPORT_ERROR = None

try:
    from omo.episode_projection import build_episode_projection_snapshot_from_path
except Exception as exc:  # Keep the episode projection route independently unavailable.
    build_episode_projection_snapshot_from_path = None  # type: ignore[assignment]
    _EPISODE_PROJECTION_IMPORT_ERROR: Exception | None = exc
else:
    _EPISODE_PROJECTION_IMPORT_ERROR = None

try:
    from omo.event_ledger import LedgerBroker
    from omo.personal_episode import CAPABILITY, PersonalEpisodeError, PersonalEpisodeService
except Exception as exc:  # Keep the existing Workflow Mesh routes independently available.
    CAPABILITY = "bos://personal/followup/draft"
    LedgerBroker = None  # type: ignore[assignment]
    PersonalEpisodeError = ValueError  # type: ignore[assignment,misc]
    PersonalEpisodeService = None  # type: ignore[assignment]
    _PERSONAL_EPISODE_IMPORT_ERROR: Exception | None = exc
else:
    _PERSONAL_EPISODE_IMPORT_ERROR = None

try:
    from agora.mcp.policy_enforcement import PEPDenied, complete, enforce, reset_pep_provider_cache
except Exception as exc:  # An effectful local draft must fail closed without Agora PEP.
    PEPDenied = RuntimeError  # type: ignore[assignment,misc]
    complete = None  # type: ignore[assignment]
    enforce = None  # type: ignore[assignment]
    reset_pep_provider_cache = None  # type: ignore[assignment]
    _PEP_IMPORT_ERROR: Exception | None = exc
else:
    _PEP_IMPORT_ERROR = None


router = APIRouter(prefix="/api/workflow-mesh", tags=["workflow-mesh"]) if APIRouter else None
from cockpit.web._agora_ports import agora_http_endpoint

_AGORA_HTTP_ENDPOINT = agora_http_endpoint()
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


def _event_ledger_db_path() -> Path:
    """Resolve the existing Event Ledger SQLite path without creating it."""
    env = os.environ.get("OMO_EVENT_LEDGER_DB")
    if env:
        return Path(env).resolve()
    return (_REPO_ROOT / "runtime" / "omo" / "event-ledger.sqlite3").resolve()


def _personal_draft_dir() -> Path:
    """Resolve the server-owned local draft directory, never a caller path."""
    configured = os.environ.get("PERSONAL_DRAFT_DIR")
    if configured:
        return Path(configured).resolve()
    return (_REPO_ROOT / "runtime" / "omo" / "personal-drafts").resolve()


@contextmanager
def _personal_episode_service() -> Any:
    """Create one request-local OMO service and always close its SQLite broker."""
    if PersonalEpisodeService is None or LedgerBroker is None:
        raise RuntimeError("personal episode runtime unavailable")
    broker = LedgerBroker.connect(_event_ledger_db_path())
    try:
        yield PersonalEpisodeService(broker)
    finally:
        broker.close()


def _personal_error(reason: str, *, status_code: int = 409) -> Any:
    """Return a non-success response without leaking broker or PEP internals."""
    payload = {"ok": False, "status": "blocked", "error": reason}
    if JSONResponse is None:
        return payload
    return JSONResponse(status_code=status_code, content=payload)


def _personal_request(body: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise PersonalEpisodeError("invalid_request", "request body must be an object")
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise PersonalEpisodeError("invalid_request", f"unsupported fields: {unknown}")
    return body


def _required_text(body: dict[str, Any], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PersonalEpisodeError("invalid_request", f"{field} must be non-empty")
    return value.strip()


def _write_local_draft(context: Any, draft: dict[str, str]) -> Path:
    """Atomically persist one server-named, never-send JSON artifact."""
    draft_dir = _personal_draft_dir()
    draft_dir.mkdir(parents=True, exist_ok=True)
    stable_name = hashlib.sha256(
        f"{context.episode_id}|{context.action_id}".encode()
    ).hexdigest()[:24]
    target = draft_dir / f"personal-followup-{stable_name}.json"
    payload = {**draft, "never_send": True}
    descriptor, temporary_name = tempfile.mkstemp(
        dir=draft_dir,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


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

    @router.get("/engineering-delivery/review-queue")
    async def get_engineering_delivery_review_queue(
        workflow_run_id: str | None = Query(None, description="Optional WorkflowRun filter"),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Expose the OMO-owned engineering delivery review queue read-only."""
        controls = {
            "read_only": True,
            "workflow_state_mutation": False,
            "provider_invocation": False,
            "automatic_promotion": False,
        }
        if build_engineering_delivery_review_queue is None:
            return {
                "ok": False,
                "status": "unavailable",
                "schema": "engineering-delivery-review-queue/v1",
                "error": "engineering_delivery_review_queue_unavailable",
                "next_action": "安装并挂载 OMO 工程交付消费者后重试。",
                **controls,
            }
        try:
            projection = build_engineering_delivery_review_queue(
                _REPO_ROOT / ".omo",
                workflow_run_id=workflow_run_id,
            )
        except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "schema": "engineering-delivery-review-queue/v1",
                "error": type(exc).__name__,
                "next_action": "检查 OMO 工程交付回执和反馈日志后重试。",
                **controls,
            }
        return {
            "ok": True,
            "status": "live",
            "projection": projection,
            **controls,
        }

    @router.get("/episode-projections")
    async def get_episode_projections(
        principal_id: str = Query(..., description="Principal identity for the episode projection"),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Expose the OMO-owned W2-04 episode projection read-only.

        The endpoint only resolves the existing Event Ledger database path and
        delegates to ``omo.episode_projection``.  It never appends, writes
        scene cards, approves, executes, or triggers external side effects.
        """
        controls = {
            "read_only": True,
            "workflow_state_mutation": False,
            "provider_invocation": False,
            "automatic_promotion": False,
        }
        if build_episode_projection_snapshot_from_path is None:
            return {
                "ok": False,
                "status": "unavailable",
                "schema": "episode-projections/v1",
                "principal_id": principal_id,
                "error": "episode_projection_unavailable",
                "error_type": type(_EPISODE_PROJECTION_IMPORT_ERROR).__name__
                if _EPISODE_PROJECTION_IMPORT_ERROR
                else "ImportError",
                "next_action": "安装并挂载 OMO episode_projection 投影后重试。",
                **controls,
            }
        db_path = _event_ledger_db_path()
        if not db_path.exists():
            return {
                "ok": False,
                "status": "unavailable",
                "schema": "episode-projections/v1",
                "principal_id": principal_id,
                "error": "episode_projection_ledger_missing",
                "next_action": "确认 Event Ledger 数据库已初始化后重试。",
                "db_path": str(db_path),
                **controls,
            }
        try:
            projection = build_episode_projection_snapshot_from_path(
                db_path,
                principal_id=principal_id,
            )
        except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
            _logger.info("episode_projection_failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "status": "unavailable",
                "schema": "episode-projections/v1",
                "principal_id": principal_id,
                "error": "episode_projection_failed",
                "message": f"episode 投影不可用: {type(exc).__name__}",
                "next_action": "检查 Event Ledger 数据与 OMO episode_projection 契约后重试。",
                **controls,
            }
        return {
            "ok": projection.get("status") == "live",
            "status": projection.get("status", "unavailable"),
            "schema": "episode-projections/v1",
            "principal_id": principal_id,
            "projection": projection,
            **controls,
        }

    @router.post("/personal-episode/start")
    async def post_personal_episode_start(request: Request) -> Any:  # type: ignore[valid-type]
        """Create one human-confirmation-required personal Inbox episode."""
        if PersonalEpisodeService is None:
            return _personal_error("personal_episode_unavailable", status_code=503)
        try:
            body = _personal_request(
                await request.json(),
                {
                    "principal_id",
                    "role_id",
                    "responsibility_id",
                    "executor_id",
                    "request_id",
                    "summary",
                    "why_now",
                    "deadline",
                },
            )
            with _personal_episode_service() as service:
                episode = service.start(
                    principal_id=_required_text(body, "principal_id"),
                    role_id=_required_text(body, "role_id"),
                    responsibility_id=_required_text(body, "responsibility_id"),
                    executor_id=_required_text(body, "executor_id"),
                    request_id=_required_text(body, "request_id"),
                    summary=_required_text(body, "summary"),
                    why_now=str(body.get("why_now") or ""),
                    deadline=str(body["deadline"]) if body.get("deadline") is not None else None,
                )
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_episode_start_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_start_invalid"))
        return {"ok": True, "status": "pending_confirmation", "episode": episode.to_dict()}

    @router.post("/personal-episode/confirm")
    async def post_personal_episode_confirm(request: Request) -> Any:  # type: ignore[valid-type]
        """Grant the exact revocable A2/R0 mandate after an explicit human confirm."""
        if PersonalEpisodeService is None:
            return _personal_error("personal_episode_unavailable", status_code=503)
        try:
            body = _personal_request(
                await request.json(),
                {"episode_id", "principal_id", "executor_id", "human_confirmed"},
            )
            with _personal_episode_service() as service:
                confirmation = service.confirm(
                    episode_id=_required_text(body, "episode_id"),
                    principal_id=_required_text(body, "principal_id"),
                    executor_id=_required_text(body, "executor_id"),
                    human_confirmed=body.get("human_confirmed") is True,
                )
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_episode_confirm_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_confirm_invalid"))
        return {"ok": True, "status": "confirmed", "confirmation": confirmation.to_dict()}

    @router.post("/personal-episode/execute")
    async def post_personal_episode_execute(request: Request) -> Any:  # type: ignore[valid-type]
        """PEP-gate and create one server-owned never-send local draft artifact."""
        if PersonalEpisodeService is None or enforce is None or complete is None:
            return _personal_error("personal_episode_execution_unavailable", status_code=503)
        artifact: Path | None = None
        decision = receipt = None
        terminal_confirmed = False
        try:
            body = _personal_request(
                await request.json(),
                {"episode_id", "principal_id", "title", "context", "deadline", "next_action"},
            )
            with _personal_episode_service() as service:
                context = service.reload_execution_context(
                    _required_text(body, "episode_id"), _required_text(body, "principal_id")
                )
                draft = {
                    field: _required_text(body, field)
                    for field in ("title", "context", "deadline", "next_action")
                }
                # Trusted-local default only; an explicit deployment binding wins unchanged.
                if not os.environ.get("AGORA_PEP_PROVIDER"):
                    os.environ["AGORA_PEP_PROVIDER"] = "omo.sovereignty.enforcement:AgoraPepProvider"
                    if reset_pep_provider_cache is not None:
                        reset_pep_provider_cache()
                decision, receipt = enforce(
                    uri=CAPABILITY,
                    tool_name="personal_followup_draft",
                    operation="write",
                    caller_id=context.executor_id,
                    arguments={"_omo_policy": context.omo_policy},
                    payload=draft,
                )
                artifact = _write_local_draft(context, draft)
                evidence_uri = artifact.resolve().as_uri()
                complete(decision, receipt, succeeded=True, result={"evidence_uri": evidence_uri})
                terminal_confirmed = True
                service.record_evidence(context, evidence_uri)
        except (PersonalEpisodeError, PEPDenied, OSError, TypeError, ValueError) as exc:
            if artifact is not None and not terminal_confirmed:
                artifact.unlink(missing_ok=True)
            if (decision is not None or receipt is not None) and not terminal_confirmed:
                try:
                    complete(decision, receipt, succeeded=False, error=type(exc).__name__)
                except Exception as terminal_exc:  # Terminal failure is evidence, not a silent cleanup detail.
                    _logger.warning("personal_episode_terminal_failure: %s", type(terminal_exc).__name__)
            _logger.info("personal_episode_execute_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_execution_blocked"))
        return {
            "ok": True,
            "status": "completed",
            "episode_id": context.episode_id,
            "evidence_uri": evidence_uri,
        }

    @router.post("/personal-episode/feedback")
    async def post_personal_episode_feedback(request: Request) -> Any:  # type: ignore[valid-type]
        """Append one closed-vocabulary human outcome to the causal episode."""
        if PersonalEpisodeService is None:
            return _personal_error("personal_episode_unavailable", status_code=503)
        try:
            body = _personal_request(await request.json(), {"episode_id", "principal_id", "verdict"})
            with _personal_episode_service() as service:
                context = service.reload_execution_context(
                    _required_text(body, "episode_id"), _required_text(body, "principal_id")
                )
                sequence = service.record_outcome(context, _required_text(body, "verdict"))
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_episode_feedback_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_feedback_invalid"))
        return {"ok": True, "status": "recorded", "sequence": sequence}

    @router.post("/engineering-delivery/review")
    async def post_engineering_delivery_review(request: Request) -> dict[str, Any]:  # type: ignore[valid-type]
        """Record one human engineering-delivery decision through the OMO broker."""
        controls = {
            "workflow_state_mutation": False,
            "provider_invocation": False,
            "automatic_promotion": False,
        }
        if record_engineering_delivery_review is None:
            return {
                "ok": False,
                "status": "unavailable",
                "error": "engineering_delivery_review_unavailable",
                "next_action": "安装并挂载 OMO 工程交付消费者后重试。",
                **controls,
            }
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise EngineeringDeliveryConsumerError("review envelope must be an object")
            allowed = {
                "workflow_run_id",
                "actor_ref",
                "delivery_id",
                "decision",
                "reviewed_at",
                "evidence_refs",
            }
            unknown = sorted(set(body) - allowed)
            if unknown:
                raise EngineeringDeliveryConsumerError(f"unsupported review envelope fields: {unknown}")
            payload = {
                key: body[key] for key in ("delivery_id", "decision", "reviewed_at", "evidence_refs") if key in body
            }
            result = record_engineering_delivery_review(
                _REPO_ROOT / ".omo",
                payload,
                workflow_run_id=str(body.get("workflow_run_id") or ""),
                actor=str(body.get("actor_ref") or "cockpit-user"),
            )
        except (EngineeringDeliveryConsumerError, ValueError, TypeError) as exc:
            return {
                "ok": False,
                "status": "invalid",
                "error": "engineering_delivery_review_invalid",
                "message": str(exc),
                **controls,
            }
        except OSError as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "error": "engineering_delivery_review_unavailable",
                "message": f"人工复核持久化不可用: {type(exc).__name__}",
                **controls,
            }
        return {
            "ok": True,
            "status": result["status"],
            "review": result,
            **controls,
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
