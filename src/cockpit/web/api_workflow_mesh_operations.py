"""Read-only Workflow Mesh operations projection for Cockpit."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import math
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
_IRIS_SRC = _REPO_ROOT / "projects" / "kairon" / "packages" / "iris" / "src"
if str(_IRIS_SRC) not in sys.path:
    sys.path.insert(0, str(_IRIS_SRC))

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
    from omo.personal_episode import PersonalLocalSignal
except Exception as exc:  # The local-signal ingress degrades on its own.
    PersonalLocalSignal = None  # type: ignore[assignment,misc]
    _PERSONAL_LOCAL_SIGNAL_IMPORT_ERROR: Exception | None = exc
else:
    _PERSONAL_LOCAL_SIGNAL_IMPORT_ERROR = None

try:
    from omo.personal_episode import EpisodeDraftSnapshot
except Exception as exc:  # Available after OMO gitlink sync (.subtrees/omo).
    EpisodeDraftSnapshot = None  # type: ignore[assignment,misc]
    _DRAFT_SNAPSHOT_IMPORT_ERROR: Exception | None = exc
else:
    _DRAFT_SNAPSHOT_IMPORT_ERROR = None

try:
    from iris.connectors.local_files import LocalFilesConnector
except Exception as exc:  # Iris is an optional runtime dependency for Cockpit.
    LocalFilesConnector = None  # type: ignore[assignment,misc]
    _IRIS_IMPORT_ERROR: Exception | None = exc
else:
    _IRIS_IMPORT_ERROR = None

try:
    from omo.sovereignty import SovereigntyService
    from omo.sovereignty.roles import STATUS_ACTIVE
except Exception as exc:  # Sovereignty is an optional runtime dependency for Cockpit.
    SovereigntyService = None  # type: ignore[assignment,misc]
    STATUS_ACTIVE = "active"
    _SOVEREIGNTY_IMPORT_ERROR: Exception | None = exc
else:
    _SOVEREIGNTY_IMPORT_ERROR = None

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


PERSONAL_SIGNAL_SOURCE_ID = "iris-local-files"
PERSONAL_SIGNAL_URI_PREFIX = "iris://local-files/"


def _personal_signal_dir() -> Path:
    """Resolve the server-owned local Markdown directory, never a caller path."""
    configured = os.environ.get("PERSONAL_SIGNAL_DIR")
    if not configured or not configured.strip():
        raise PersonalEpisodeError("missing_config", "PERSONAL_SIGNAL_DIR is not set")
    return Path(configured).expanduser().resolve()


def _local_files_connector(allowed_dir: Path) -> Any:
    """Construct Iris's read-only local-files connector scoped to ``allowed_dir``."""
    if LocalFilesConnector is None:
        raise RuntimeError("iris local-files connector unavailable")
    # Iris's directory is server-owned configuration: scope the connector to
    # PERSONAL_SIGNAL_DIR through the documented IRIS_* env override, so no
    # caller-supplied path and no user config file can redirect it.
    os.environ["IRIS_LOCAL_FILES_DIRECTORY"] = str(allowed_dir)
    return LocalFilesConnector()


def _resolve_local_signal(
    *,
    item_id: str,
    principal_id: str,
    role_id: str,
    responsibility_id: str,
    executor_id: str,
) -> Any:
    """Resolve an opaque item into a trusted PersonalLocalSignal descriptor.

    Every verification is performed server-side on the resolved path: the
    item must be a regular ``.md`` file strictly inside ``PERSONAL_SIGNAL_DIR``
    (``Path.relative_to`` rejects traversal and symlink escape), must have a
    non-empty title, and the digest is computed from the resolved file bytes.
    The returned descriptor never contains the absolute path or file body.
    """
    allowed_dir = _personal_signal_dir()
    if not allowed_dir.is_dir():
        raise PersonalEpisodeError("missing_config", "PERSONAL_SIGNAL_DIR must be a directory")
    connector = _local_files_connector(allowed_dir)
    try:
        note = connector.get_item(item_id)
    except (ValueError, OSError) as exc:
        raise PersonalEpisodeError(
            "item_not_found", "no local item matches the given item_id"
        ) from exc
    if note is None:
        raise PersonalEpisodeError("item_not_found", "no local item matches the given item_id")
    resolved = Path(note.source_path).resolve()
    try:
        resolved.relative_to(allowed_dir)
    except ValueError:
        raise PersonalEpisodeError(
            "source_outside_allowed_dir", "resolved item escapes the allowed directory"
        ) from None
    if resolved == allowed_dir or not resolved.is_file() or resolved.suffix.lower() != ".md":
        raise PersonalEpisodeError("not_markdown", "item must be a regular markdown file")
    title = (note.title or resolved.stem).strip()
    if not title:
        raise PersonalEpisodeError("empty_title", "item must have a non-empty title")
    return PersonalLocalSignal(
        source_id=PERSONAL_SIGNAL_SOURCE_ID,
        item_id=item_id,
        title=title,
        content_sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        source_uri=f"{PERSONAL_SIGNAL_URI_PREFIX}{item_id}",
        principal_id=principal_id,
        role_id=role_id,
        responsibility_id=responsibility_id,
        executor_id=executor_id,
    )


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


def _optional_burden(body: dict[str, Any], field: str) -> float | None:
    """Extract an optional non-negative finite numeric burden field.

    Returns None when the field is absent; otherwise validates that the
    value is a real number (rejecting bool, NaN, inf, negative).  The
    OMO layer re-validates, but catching at the boundary gives a clean
    error without touching the ledger.
    """
    if field not in body or body[field] is None:
        return None
    value = body[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PersonalEpisodeError("invalid_burden", f"{field} must be a number")
    v = float(value)
    if v < 0 or not math.isfinite(v):
        raise PersonalEpisodeError("invalid_burden", f"{field} must be non-negative and finite")
    return v


def _projection_value_is_private(value: Any) -> bool:
    """Reject path- and connector-shaped strings from the public projection."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    lowered = stripped.lower()
    return (
        "file://" in lowered
        or "iris://" in lowered
        or stripped.startswith(("/", "~/"))
        or "/users/" in lowered
    )


def _projection_fields(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Copy explicitly public scalar fields from one projection mapping."""
    if not isinstance(source, dict):
        return {}
    result: dict[str, Any] = {}
    for field in fields:
        if field not in source:
            continue
        value = source.get(field)
        if value is None or isinstance(value, (str, int, float, bool)):
            if not _projection_value_is_private(value):
                result[field] = value
    return result


def _episode_projection_http_dto(projection: Any) -> dict[str, Any]:
    """Build the public allowlisted DTO without mutating OMO's ledger view."""
    if not isinstance(projection, dict):
        return {}

    episodes: list[dict[str, Any]] = []
    for raw_episode in projection.get("episodes", []):
        episode = _projection_fields(
            raw_episode,
            (
                "episode_id",
                "schema_version",
                "opened_at",
                "closed_at",
                "status",
                "name",
                "event_count",
            ),
        )
        members: list[dict[str, Any]] = []
        if isinstance(raw_episode, dict):
            for raw_member in raw_episode.get("contains_event_refs", []):
                member = _projection_fields(
                    raw_member,
                    ("event_id", "schema_version", "emitted_at"),
                )
                raw_payload = raw_member.get("payload", {}) if isinstance(raw_member, dict) else {}
                member["payload"] = _projection_fields(
                    raw_payload,
                    (
                        "episode_id",
                        "request_id",
                        "summary",
                        "why_now",
                        "deadline",
                        "status",
                        "confidence",
                        "role_id",
                        "responsibility_id",
                        "action_id",
                        "output_origin",
                        "feedback_id",
                        "verdict",
                        "review_duration_seconds",
                        "estimated_time_saved_seconds",
                    ),
                )
                members.append(member)
        episode["contains_event_refs"] = members
        episodes.append(episode)

    raw_portfolio = projection.get("role_portfolio", {})
    role_portfolio = _projection_fields(raw_portfolio, ("principal_id",))
    assignments: list[dict[str, Any]] = []
    responsibilities: list[dict[str, Any]] = []
    if isinstance(raw_portfolio, dict):
        for raw_assignment in raw_portfolio.get("active_assignments", []):
            assignment = _projection_fields(
                raw_assignment,
                (
                    "assignment_id",
                    "principal_id",
                    "role_id",
                    "role_name",
                    "role_scope",
                    "version",
                    "status",
                ),
            )
            if isinstance(raw_assignment, dict):
                assignment["responsibilities"] = [
                    _projection_fields(item, ("resp_id", "responsibility_id", "name", "version"))
                    for item in raw_assignment.get("responsibilities", [])
                    if isinstance(item, dict)
                ]
            assignments.append(assignment)
        responsibilities = [
            _projection_fields(item, ("resp_id", "responsibility_id", "name", "version"))
            for item in raw_portfolio.get("responsibilities", [])
            if isinstance(item, dict)
        ]
        raw_counts = raw_portfolio.get("episode_counts", {})
        episode_counts = {
            key: value
            for key, value in raw_counts.items()
            if isinstance(key, str)
            and not _projection_value_is_private(key)
            and isinstance(value, int)
            and not isinstance(value, bool)
        } if isinstance(raw_counts, dict) else {}
    else:
        episode_counts = {}
    role_portfolio.update(
        {
            "active_assignments": assignments,
            "responsibilities": responsibilities,
            "episode_counts": episode_counts,
        }
    )

    inbox = [
        _projection_fields(
            item,
            (
                "card_type",
                "episode",
                "principal",
                "role",
                "responsibility",
                "request",
                "summary",
                "why_now",
                "risk",
                "authority",
                "deadline",
                "status",
                "confidence",
            ),
        )
        for item in projection.get("inbox", [])
        if isinstance(item, dict)
    ]
    blocked = [
        _projection_fields(item, ("event_id", "event_type", "sequence", "reason"))
        for item in projection.get("blocked", [])
        if isinstance(item, dict)
    ]
    raw_controls = projection.get("controls", {})
    controls = _projection_fields(
        raw_controls,
        (
            "events_read",
            "events_ignored",
            "events_blocked",
            "ledger_count_before",
            "ledger_count_after",
            "ledger_unchanged",
        ),
    )
    if isinstance(raw_controls, dict):
        controls["chain_before"] = _projection_fields(raw_controls.get("chain_before"), ("ok", "total"))
        controls["chain_after"] = _projection_fields(raw_controls.get("chain_after"), ("ok", "total"))

    dto = _projection_fields(projection, ("schema_version", "status", "principal_id"))
    dto.update(
        {
            "episodes": episodes,
            "role_portfolio": role_portfolio,
            "inbox": inbox,
            "blocked": blocked,
            "controls": controls,
        }
    )
    return dto


def _write_local_draft(
    context: Any, draft: dict[str, str], output_origin: str = "system"
) -> Path:
    """Atomically persist one server-named, never-send JSON artifact."""
    draft_dir = _personal_draft_dir()
    draft_dir.mkdir(parents=True, exist_ok=True)
    stable_name = hashlib.sha256(
        f"{context.episode_id}|{context.action_id}".encode()
    ).hexdigest()[:24]
    target = draft_dir / f"personal-followup-{stable_name}.json"
    payload = {**draft, "never_send": True, "output_origin": output_origin}
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


_DRAFT_FIELDS = frozenset({"title", "context", "deadline", "next_action"})


def _normalize_resp_input(responsibilities: list[str]) -> tuple[list, set[str]]:
    """Normalize caller responsibility strings for OMO assign() and comparison.

    ``responsibility:xxx`` → mapping dict (exact resp_id, no re-slug);
    plain string → left as-is for OMO slug+prefix normalization.
    Returns ``(items_for_assign, expected_canonical_ids)``.
    """
    import re

    def _slugify(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
        return slug or "item"

    items: list = []
    expected: set[str] = set()
    for r in responsibilities:
        r = r.strip()
        if r.startswith("responsibility:"):
            suffix = r.split(":", 1)[1]
            items.append({"resp_id": r, "name": suffix})
            expected.add(r)
        else:
            items.append(r)
            expected.add(f"responsibility:{_slugify(r)}")
    return items, expected


def _build_draft_from_snapshot(snapshot: Any) -> dict[str, str]:
    """Deterministically build a safe draft dict from a persisted Episode snapshot.

    Only uses fields already in the ledger event — summary, why_now,
    deadline.  Never touches raw signal body, filesystem paths, or URIs.
    """
    summary = str(getattr(snapshot, "summary", "") or "").strip()
    why_now = str(getattr(snapshot, "why_now", "") or "").strip()
    deadline = str(getattr(snapshot, "deadline", "") or "").strip()
    context_text = f"{summary}. {why_now}." if why_now else f"{summary}."
    return {
        "title": summary or "Personal follow-up draft",
        "context": context_text.strip(),
        "deadline": deadline,
        "next_action": "Review and edit the local draft.",
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
            "projection": _episode_projection_http_dto(projection),
            **controls,
        }

    @router.post("/personal-episode/setup")
    async def post_personal_episode_setup(request: Request) -> Any:  # type: ignore[valid-type]
        """Idempotently assign the trusted-local personal steward role.

        If the (principal, role) pair is already active, returns immediately
        without error — safe to call repeatedly.  This is the single seed
        step that makes every subsequent personal-episode flow possible.
        """
        if SovereigntyService is None or LedgerBroker is None:
            return _personal_error("sovereignty_unavailable", status_code=503)
        try:
            body = _personal_request(
                await request.json(),
                {"principal_id", "role_id", "role_name", "scope", "responsibilities"},
            )
            principal_id = _required_text(body, "principal_id")
            role_id = _required_text(body, "role_id")
            role_name = str(body.get("role_name") or "Personal Steward")
            scope = str(body.get("scope") or "personal")
            responsibilities = body.get("responsibilities")
            if responsibilities is not None:
                if not isinstance(responsibilities, list) or not all(
                    isinstance(r, str) and r.strip() for r in responsibilities
                ):
                    raise PersonalEpisodeError(
                        "invalid_request", "responsibilities must be a list of non-empty strings"
                    )
                resp_items, expected_ids = _normalize_resp_input(responsibilities)
            else:
                resp_items, expected_ids = None, set()
            broker = LedgerBroker.connect(_event_ledger_db_path())
            try:
                service = SovereigntyService(broker)
                existing = service.current_assignment(principal_id, role_id)
                if existing is not None and existing.status == STATUS_ACTIVE:
                    # Idempotent only when the existing assignment matches
                    # the caller's expectations — silent drift is blocked.
                    if existing.role_scope != scope:
                        raise PersonalEpisodeError(
                            "scope_conflict",
                            f"active role scope is '{existing.role_scope}', "
                            f"caller requested '{scope}'",
                        )
                    if existing.role_name != role_name:
                        raise PersonalEpisodeError(
                            "role_name_conflict",
                            f"active role name is '{existing.role_name}', "
                            f"caller requested '{role_name}'",
                        )
                    if expected_ids:
                        existing_resp = {r.resp_id for r in existing.responsibilities}
                        missing = expected_ids - existing_resp
                        if missing:
                            raise PersonalEpisodeError(
                                "responsibility_conflict",
                                f"active assignment lacks responsibilities: {sorted(missing)}",
                            )
                    return {
                        "ok": True,
                        "status": "already_active",
                        "assignment": {
                            "assignment_id": existing.assignment_id,
                            "role_id": role_id,
                            "version": existing.version,
                        },
                    }
                service.assign(
                    principal_id,
                    role_id,
                    role_name=role_name,
                    scope=scope,
                    responsibilities=resp_items,
                )
            finally:
                broker.close()
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_episode_setup_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_setup_invalid"))
        return {
            "ok": True,
            "status": "assigned",
            "assignment": {"role_id": role_id},
        }

    @router.get("/personal-episode/status")
    async def get_personal_episode_status(
        principal_id: str = Query(..., description="Principal identity for status lookup"),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Read-only personal episode status — no mutation, no side effects.

        Delegates to the existing W2-04 episode projection for the compact
        inbox/episode summary and additionally projects the OMO read-only
        principal observation (readiness gate, weekly samples, evidence
        origin counts).  The observation never mutates the ledger — it only
        calls ``broker.read()``.
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
                "error": "episode_projection_unavailable",
                "principal_id": principal_id,
                **controls,
            }
        db_path = _event_ledger_db_path()
        if not db_path.exists():
            return {
                "ok": False,
                "status": "unavailable",
                "error": "episode_projection_ledger_missing",
                "principal_id": principal_id,
                **controls,
            }
        try:
            projection = build_episode_projection_snapshot_from_path(
                db_path, principal_id=principal_id
            )
        except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
            _logger.info("personal_episode_status_failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "status": "unavailable",
                "error": "episode_projection_failed",
                "principal_id": principal_id,
                **controls,
            }
        inbox = projection.get("inbox", [])
        episodes = projection.get("episodes", [])
        pending = [c for c in inbox if c.get("status") == "pending_confirmation"]

        # OMO read-only observation: readiness gate, weekly samples, gaps.
        observation: dict[str, Any] | None = None
        if PersonalEpisodeService is None:
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "status": "unavailable",
                    "error": "personal_episode_observation_unavailable",
                    "principal_id": principal_id,
                    **controls,
                },
            ) if JSONResponse is not None else {
                "ok": False,
                "status": "unavailable",
                "error": "personal_episode_observation_unavailable",
                "principal_id": principal_id,
                **controls,
            }
        try:
            with _personal_episode_service() as service:
                obs = service.observe_principal(principal_id)
            observation = obs.to_dict()
        except (
            AttributeError,
            PersonalEpisodeError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            _logger.info("personal_episode_observation_failed: %s", type(exc).__name__)
            payload = {
                "ok": False,
                "status": "unavailable",
                "error": "personal_episode_observation_failed",
                "principal_id": principal_id,
                **controls,
            }
            return JSONResponse(status_code=503, content=payload) if JSONResponse is not None else payload

        response: dict[str, Any] = {
            "ok": projection.get("status") == "live",
            "status": projection.get("status", "unavailable"),
            "principal_id": principal_id,
            "summary": {
                "total_episodes": len(episodes),
                "pending_confirmation": len(pending),
                "inbox_cards": len(inbox),
            },
            "pending": pending,
            "controls": controls,
        }
        if observation is not None:
            response["observation"] = observation
        return response

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
            episode_id = _required_text(body, "episode_id")
            principal_id = _required_text(body, "principal_id")
            provided = {f for f in _DRAFT_FIELDS if f in body}
            if provided and provided != _DRAFT_FIELDS:
                raise PersonalEpisodeError(
                    "invalid_request",
                    "either provide all draft fields (title, context, deadline, next_action) "
                    "or omit them all for a system-built draft",
                )
            with _personal_episode_service() as service:
                context = service.reload_execution_context(episode_id, principal_id)
                if provided:
                    # Caller-authored full draft — validate each field
                    draft = {
                        field: _required_text(body, field)
                        for field in _DRAFT_FIELDS
                    }
                    output_origin = "user_provided"
                else:
                    # System-built draft from safe persisted Episode snapshot
                    if not hasattr(service, "get_draft_snapshot"):
                        raise PersonalEpisodeError(
                            "draft_snapshot_unavailable",
                            "OMO runtime does not provide get_draft_snapshot; sync submodule",
                        )
                    snapshot = service.get_draft_snapshot(episode_id, principal_id)
                    draft = _build_draft_from_snapshot(snapshot)
                    output_origin = "system"
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
                artifact = _write_local_draft(context, draft, output_origin=output_origin)
                evidence_uri = artifact.resolve().as_uri()
                complete(decision, receipt, succeeded=True, result={"evidence_uri": evidence_uri})
                terminal_confirmed = True
                service.record_evidence(context, evidence_uri, output_origin=output_origin)
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
            "local_draft_recorded": True,
            "output_origin": output_origin,
        }

    @router.post("/personal-episode/feedback")
    async def post_personal_episode_feedback(request: Request) -> Any:  # type: ignore[valid-type]
        """Append one closed-vocabulary human outcome to the causal episode.

        Optional ``review_duration_seconds`` and
        ``estimated_time_saved_seconds`` are non-negative finite values;
        omitted values stay null.  The verdict vocabulary includes
        accept/edit/reject/defer/ignore.
        """
        if PersonalEpisodeService is None:
            return _personal_error("personal_episode_unavailable", status_code=503)
        try:
            body = _personal_request(
                await request.json(),
                {
                    "episode_id",
                    "principal_id",
                    "feedback_id",
                    "verdict",
                    "review_duration_seconds",
                    "estimated_time_saved_seconds",
                },
            )
            review_duration = _optional_burden(body, "review_duration_seconds")
            estimated_saved = _optional_burden(body, "estimated_time_saved_seconds")
            feedback_id = _required_text(body, "feedback_id") if "feedback_id" in body else None
            with _personal_episode_service() as service:
                context = service.reload_execution_context(
                    _required_text(body, "episode_id"), _required_text(body, "principal_id")
                )
                sequence = service.record_outcome(
                    context,
                    _required_text(body, "verdict"),
                    feedback_id=feedback_id,
                    review_duration_seconds=review_duration,
                    estimated_time_saved_seconds=estimated_saved,
                )
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_episode_feedback_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_episode_feedback_invalid"))
        return {"ok": True, "status": "recorded", "sequence": sequence}

    @router.post("/personal-signal/ingest")
    async def post_personal_signal_ingest(request: Request) -> Any:  # type: ignore[valid-type]
        """Resolve one private local Markdown item into a causal Inbox episode.

        The body carries only the opaque ``item_id`` plus the sovereignty
        identity fields; the server resolves the item through Iris and verifies
        it is a regular ``.md`` file strictly inside ``PERSONAL_SIGNAL_DIR``
        before building a ``PersonalLocalSignal`` and delegating to OMO.  The
        raw body, file content and absolute paths are never logged or stored.
        """
        if PersonalEpisodeService is None or PersonalLocalSignal is None or LocalFilesConnector is None:
            return _personal_error("personal_signal_unavailable", status_code=503)
        try:
            body = _personal_request(
                await request.json(),
                {"item_id", "principal_id", "role_id", "responsibility_id", "executor_id"},
            )
            signal = _resolve_local_signal(
                item_id=_required_text(body, "item_id"),
                principal_id=_required_text(body, "principal_id"),
                role_id=_required_text(body, "role_id"),
                responsibility_id=_required_text(body, "responsibility_id"),
                executor_id=_required_text(body, "executor_id"),
            )
            with _personal_episode_service() as service:
                result = service.ingest_local_signal(signal)
        except (PersonalEpisodeError, OSError, TypeError, ValueError) as exc:
            _logger.info("personal_signal_ingest_blocked: %s", type(exc).__name__)
            return _personal_error(getattr(exc, "reason", "personal_signal_ingest_invalid"))
        return {
            "ok": True,
            "status": "pending_confirmation",
            "signal": {
                "signal_event_id": result.signal_event_id,
                "signal_id": result.signal_id,
            },
            "episode": result.episode.to_dict(),
        }

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
