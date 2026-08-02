"""Read-only External Connection Fabric projection for Cockpit."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request

_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.omo_external_evaluation import record_external_resource_evaluation
    from omo.omo_external_pack import (
        ExternalResourcePackProposalError,
        record_external_resource_pack_proposal,
    )
    from omo.omo_external_resources import read_latest_external_resource_observation
    from omo.omo_external_scene_trial import read_external_scene_trials
    from omo.omo_external_scene_trial_feedback import (
        ExternalSceneTrialFeedbackError,
        read_external_scene_trial_feedback,
        record_external_scene_trial_feedback,
    )
    from omo.workflow_eval import (
        build_external_resource_selection_dataset,
        propose_selection_policy_feedback,
    )
except Exception as exc:  # OMO is optional while Cockpit is being bootstrapped.
    read_latest_external_resource_observation = None  # type: ignore[assignment]
    record_external_resource_evaluation = None  # type: ignore[assignment]
    record_external_resource_pack_proposal = None  # type: ignore[assignment]
    read_external_scene_trials = None  # type: ignore[assignment]
    read_external_scene_trial_feedback = None  # type: ignore[assignment]
    record_external_scene_trial_feedback = None  # type: ignore[assignment]
    ExternalSceneTrialFeedbackError = ValueError
    ExternalResourcePackProposalError = ValueError
    build_external_resource_selection_dataset = None  # type: ignore[assignment]
    propose_selection_policy_feedback = None  # type: ignore[assignment]
    _OMO_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_IMPORT_ERROR = None


def _load_catalog_module() -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / "external-resource-catalog.py"
    spec = importlib.util.spec_from_file_location(
        "cockpit_external_resource_catalog_projection", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError("external resource catalog projection is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _catalog_module = _load_catalog_module()
    collect_external_resources = _catalog_module.collect_external_resources
    evaluate_external_resources = _catalog_module.evaluate_external_resources
except Exception as exc:  # Discovery is allowed to degrade independently.
    collect_external_resources = None  # type: ignore[assignment]
    evaluate_external_resources = None  # type: ignore[assignment]
    _CATALOG_IMPORT_ERROR: Exception | None = exc
else:
    _CATALOG_IMPORT_ERROR = None


def _load_pack_module() -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / "external-resource-pack.py"
    spec = importlib.util.spec_from_file_location(
        "cockpit_external_resource_pack_projection", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError("external resource pack checker is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _pack_module = _load_pack_module()
    check_external_resource_pack = _pack_module.check_external_resource_pack
    ExternalResourcePackError = _pack_module.ExternalResourcePackError
except Exception as exc:
    check_external_resource_pack = None  # type: ignore[assignment]
    ExternalResourcePackError = ValueError
    _PACK_IMPORT_ERROR: Exception | None = exc
else:
    _PACK_IMPORT_ERROR = None


router = APIRouter(prefix="/api/external-resources", tags=["external-resources"])

_REVIEW_QUEUE_SCHEMA = "external-resource-review-queue/v1"
_SCENE_TRIAL_REVIEW_SCHEMA = "external-scene-trial-review/v1"
_REVIEW_SNAPSHOT_FIELDS = (
    "id",
    "provider",
    "protocol",
    "version",
    "capabilities",
    "mode",
    "lifecycle",
    "availability",
    "reason_codes",
    "health",
    "permission_ref",
    "expires_at",
    "review_at",
    "rollback_plan",
)


def _unavailable_projection(error_type: str, next_action: str) -> dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": now_iso,
        "health_ttl_seconds": 900,
        "catalog_ttl_seconds": 3600,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [],
        "errors": [{"entry_point": "cockpit", "status": "unavailable", "error": error_type}],
        "summary": {
            "resource_count": 0,
            "unavailable_count": 0,
            "error_count": 1,
            "by_kind": {},
            "by_availability": {},
        },
        "status": "unavailable",
        "next_action": next_action,
    }


def _latest_observation() -> dict[str, Any] | None:
    if read_latest_external_resource_observation is None:
        return None
    observation = read_latest_external_resource_observation(_REPO_ROOT / ".omo")
    if not isinstance(observation, Mapping):
        return None
    return dict(observation)


def _latest_catalog() -> dict[str, Any] | None:
    observation = _latest_observation()
    if observation is None:
        return None
    catalog = observation.get("catalog")
    if not isinstance(catalog, Mapping):
        return None
    if catalog.get("schema") != "external-resource-catalog/v1":
        return None
    if catalog.get("activation") != "forbidden":
        return None
    return dict(catalog)


def _safe_review_snapshot(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("review snapshot must be an object")
    return {
        field: value[field]
        for field in _REVIEW_SNAPSHOT_FIELDS
        if field in value
    }


def _review_queue_projection(observation: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project the latest delta; this is not a durable approval queue."""
    base = {
        "schema": _REVIEW_QUEUE_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "source": "omo.external_resource_observation",
        "queue_semantics": "latest_observation_delta",
        "items": [],
        "summary": {
            "review_required_count": 0,
            "operational_observation_count": 0,
            "risk_codes": [],
        },
    }
    if observation is None:
        return {
            **base,
            "status": "empty",
            "next_action": "先运行受治理的外部资源观测，再查看人工复核队列。",
        }
    if observation.get("schema") != "external-resource-observation/v1":
        raise ValueError("external resource observation schema is invalid")
    catalog = observation.get("catalog")
    if not isinstance(catalog, Mapping):
        raise ValueError("external resource observation catalog is invalid")
    changes = catalog.get("changes")
    if changes is None:
        changes = {}
    if not isinstance(changes, Mapping):
        raise ValueError("external resource catalog changes are invalid")
    if changes and changes.get("schema") != "external-resource-catalog-diff/v1":
        raise ValueError("external resource catalog diff schema is invalid")
    raw_changes = changes.get("changes", [])
    if not isinstance(raw_changes, list):
        raise ValueError("external resource catalog diff changes are invalid")

    items: list[dict[str, Any]] = []
    operational_count = 0
    risk_codes: set[str] = set()
    for change in raw_changes:
        if not isinstance(change, Mapping):
            raise ValueError("external resource catalog change is invalid")
        codes = sorted(
            {
                str(code).strip()
                for code in change.get("risk_codes", [])
                if str(code).strip()
            }
        )
        risk_codes.update(codes)
        if not bool(change.get("review_required", False)):
            if change.get("risk_class") == "operational_observation":
                operational_count += 1
            continue
        resource_id = str(change.get("id") or "").strip()
        if not resource_id:
            raise ValueError("external resource review item is missing id")
        changed_fields = sorted(
            {
                str(field).strip()
                for field in change.get("changed_fields", [])
                if str(field).strip()
            }
        )
        items.append(
            {
                "resource_id": resource_id,
                "change": str(change.get("change") or "unknown"),
                "risk_class": "manual_review",
                "risk_codes": codes,
                "changed_fields": changed_fields,
                "previous": _safe_review_snapshot(change.get("previous")),
                "current": _safe_review_snapshot(change.get("current")),
            }
        )

    return {
        **base,
        "status": "attention" if items else "clear",
        "observed_at": observation.get("observed_at"),
        "recorded_at": observation.get("recorded_at"),
        "observation_id": observation.get("observation_id"),
        "change_state": observation.get("change_state"),
        "items": items,
        "summary": {
            "review_required_count": len(items),
            "operational_observation_count": operational_count,
            "risk_codes": sorted(risk_codes),
        },
        "next_action": (
            "按风险码和变更字段完成人工核查；复核本身不会批准或激活资源。"
            if items
            else "当前观测没有需要人工复核的资源变化。"
        ),
    }


def _scene_trial_review_projection(scene_id: str | None = None) -> dict[str, Any]:
    """Project proposal-only trials and their review receipts without promotion."""
    base = {
        "schema": _SCENE_TRIAL_REVIEW_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "source": "omo.external_scene_trial",
        "items": [],
        "summary": {
            "trial_count": 0,
            "unreviewed_count": 0,
            "reviewed_count": 0,
            "review_actions": {},
        },
    }
    if read_external_scene_trials is None or read_external_scene_trial_feedback is None:
        return {**base, "status": "unavailable", "next_action": "检查 OMO 试运行审阅存储后重试。"}
    trials = read_external_scene_trials(_REPO_ROOT / ".omo")
    feedback = read_external_scene_trial_feedback(_REPO_ROOT / ".omo")
    latest_feedback: dict[str, dict[str, Any]] = {}
    for item in feedback:
        trial_id = str(item.get("trial_id") or "")
        if trial_id:
            latest_feedback[trial_id] = item
    items: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    for trial in trials:
        binding = trial.get("scene_binding")
        if not isinstance(binding, Mapping):
            continue
        if scene_id and binding.get("scene_id") != scene_id:
            continue
        review = latest_feedback.get(str(trial.get("trial_id") or ""))
        if review:
            action = str(review.get("review_action") or "")
            action_counts[action] = action_counts.get(action, 0) + 1
        items.append(
            {
                key: trial.get(key)
                for key in (
                    "trial_id",
                    "scene_binding",
                    "consumer_ref",
                    "owner_ref",
                    "approver_ref",
                    "permission_ref",
                    "evidence_refs",
                    "preflight_ref",
                    "catalog_observation_id",
                    "trial_stage",
                    "status",
                    "metric",
                    "sample_plan",
                    "rollback_ref",
                    "feedback_contract",
                    "activation",
                    "provider_invocation",
                    "workflow_run_id",
                    "observed_at",
                    "trial_receipt_id",
                )
                if key in trial
            }
            | {"latest_review": review}
        )
    unreviewed = sum(1 for item in items if not item.get("latest_review"))
    return {
        **base,
        "status": "empty" if not items else ("attention" if unreviewed else "clear"),
        "scene_id": scene_id,
        "items": items,
        "summary": {
            "trial_count": len(items),
            "unreviewed_count": unreviewed,
            "reviewed_count": len(items) - unreviewed,
            "review_actions": action_counts,
        },
        "next_action": (
            "先提交人工评审回执；评审不会创建 WorkflowRun 或激活连接。"
            if unreviewed
            else "可继续观察；只有真实消费者、WorkflowRun、外部回执和结果反馈齐备后才能申请晋升。"
        ),
    }


def _projection_status(projection: Mapping[str, Any]) -> str:
    return "degraded" if projection.get("errors") else "live"


def _resolve_catalog_projection() -> tuple[dict[str, Any], str]:
    try:
        latest = _latest_catalog()
    except (OSError, ValueError, TypeError):
        latest = None
    if latest is not None:
        return latest, "omo.external_resource_observation"
    if collect_external_resources is None:
        raise RuntimeError("external_resource_catalog_unavailable")
    return (
        collect_external_resources(_REPO_ROOT, probe=True),
        "agora.external_resource_discovery",
    )


def _default_trace_id(capability: str, scene_binding: Mapping[str, Any]) -> str:
    material = json.dumps(
        {"capability": capability, "scene_binding": dict(scene_binding)},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return f"cockpit:external-evaluation:{hashlib.sha256(material).hexdigest()[:16]}"


@router.get("")
async def get_external_resources() -> dict[str, Any]:
    """Expose a governed observation, or a safe discovery fallback.

    This route never persists observations and never calls provider business
    methods. A missing OMO observation may trigger only the provider contract's
    explicit read-only health probe while building a fresh projection.
    """
    try:
        projection, source = _resolve_catalog_projection()
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _unavailable_projection(
            type(exc).__name__,
            "检查 Agora 外部能力描述器和只读健康探针后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_catalog",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    if source == "omo.external_resource_observation":
        return {
            "ok": True,
            "status": _projection_status(projection),
            "source": source,
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": _projection_status(projection),
        "source": source,
        "projection": projection,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.get("/review-queue")
async def get_external_resource_review_queue() -> dict[str, Any]:
    """Expose only the latest governed manual-review delta.

    The endpoint intentionally reads OMO only. It does not fall back to live
    discovery, mutate review state, invoke providers, or activate a resource.
    """
    if read_latest_external_resource_observation is None:
        projection = _review_queue_projection(None)
        projection.update(
            {
                "status": "unavailable",
                "error": "external_resource_observation_unavailable",
                "next_action": "检查 OMO 外部资源观测存储后重试。",
            }
        )
        return {
            "ok": False,
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        projection = _review_queue_projection(_latest_observation())
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _review_queue_projection(None)
        projection.update(
            {
                "status": "unavailable",
                "error": type(exc).__name__,
                "next_action": "检查 OMO 外部资源观测格式后重试。",
            }
        )
        return {
            "ok": False,
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "projection": projection,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.get("/scene-trials")
async def get_external_scene_trial_review(
    scene_id: str | None = Query(None, description="Optional scene filter"),
) -> dict[str, Any]:
    """Expose proposal-only scene trials and their latest review receipt."""
    try:
        projection = _scene_trial_review_projection(scene_id)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = {
            **_scene_trial_review_projection(None),
            "status": "unavailable",
            "error": type(exc).__name__,
            "next_action": "检查 OMO 试运行日志格式后重试。",
        }
        return {
            "ok": False,
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": projection.get("status") != "unavailable",
        "projection": projection,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/scene-trials/review")
async def review_external_scene_trial(request: Request) -> dict[str, Any]:
    """Record a proposal-only review; it never creates a WorkflowRun."""
    if record_external_scene_trial_feedback is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_scene_trial_feedback_unavailable",
            "activation": "forbidden",
            "provider_invocation": False,
            "workflow_run_creation": "forbidden",
        }
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ExternalSceneTrialFeedbackError("review payload must be an object")
        payload = dict(body)
        actor = str(payload.pop("actor_ref", "cockpit-user") or "cockpit-user")
        payload.update(
            {
                "schema": "external-scene-trial-feedback/v1",
                "activation": "forbidden",
                "provider_invocation": False,
                "workflow_run_id": None,
                "actor": actor,
                "source_ref": str(
                    payload.get("source_ref") or "cockpit:external-resources:scene-trial-review"
                ),
                "observed_at": str(
                    payload.get("observed_at")
                    or datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
                ),
            }
        )
        result = record_external_scene_trial_feedback(_REPO_ROOT / ".omo", payload)
    except (ExternalSceneTrialFeedbackError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "external_scene_trial_feedback_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "provider_invocation": False,
            "workflow_run_creation": "forbidden",
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_scene_trial_feedback_unavailable",
            "message": f"评审回执持久化不可用: {type(exc).__name__}",
            "activation": "forbidden",
            "provider_invocation": False,
            "workflow_run_creation": "forbidden",
        }
    return {
        "ok": True,
        "status": result["status"],
        "feedback": result["feedback"],
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": "forbidden",
        "persistence": "omo_append_only",
    }


@router.post("/packs/preflight")
async def preflight_external_resource_pack(request: Request) -> dict[str, Any]:
    """Check an extension manifest without loading or invoking its provider."""
    if check_external_resource_pack is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_pack_checker_unavailable",
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
        }
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("pack payload must be an object")
        pack = body.get("pack", body)
        if not isinstance(pack, Mapping):
            raise ValueError("pack must be an object")
        projection = check_external_resource_pack(_REPO_ROOT, pack)
    except ExternalResourcePackError as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "external_resource_pack_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "external_resource_pack_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
        }
    return {
        "ok": True,
        "status": projection["status"],
        "projection": projection,
        "activation": "forbidden",
        "persistence": "none",
        "provider_invocation": False,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/packs/proposals")
async def record_external_resource_pack_proposal_route(request: Request) -> dict[str, Any]:
    """Persist only a fresh, safe pack check as a human review receipt."""
    if check_external_resource_pack is None or record_external_resource_pack_proposal is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_pack_proposal_unavailable",
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
        }
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("proposal payload must be an object")
        pack = body.get("pack")
        if not isinstance(pack, Mapping):
            raise ValueError("pack must be an object")
        proposal_id = str(body.get("proposal_id") or "").strip()
        if not proposal_id:
            raise ValueError("proposal_id is required")
        projection = check_external_resource_pack(_REPO_ROOT, pack)
        if projection.get("status") == "blocked":
            return {
                "ok": False,
                "status": "blocked",
                "error": "external_resource_pack_blocked",
                "projection": projection,
                "activation": "forbidden",
                "persistence": "none",
                "provider_invocation": False,
                "external_side_effects": "disabled",
                "worker_launch": False,
            }
        result = record_external_resource_pack_proposal(
            _REPO_ROOT / ".omo",
            projection,
            proposal_id=proposal_id,
            review_action=str(body.get("review_action") or "submit").strip() or "submit",
            actor=str(body.get("actor_ref") or "cockpit").strip() or "cockpit",
            source_ref=(
                str(body.get("source_ref") or "cockpit:external-resources:pack-proposal").strip()
                or "cockpit:external-resources:pack-proposal"
            ),
            review_ref=str(body.get("review_ref") or "").strip() or None,
        )
    except ExternalResourcePackProposalError as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "external_resource_pack_proposal_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid" if isinstance(exc, (ValueError, TypeError)) else "unavailable",
            "error": "external_resource_pack_proposal_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "provider_invocation": False,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": result["status"],
        "proposal_status": projection["status"],
        "proposal": result["proposal"],
        "activation": "forbidden",
        "persistence": "omo_append_only",
        "provider_invocation": False,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/evaluate")
async def evaluate_external_resource_candidates(request: Request) -> dict[str, Any]:
    """Evaluate candidates; persist only when the caller explicitly requests it."""
    if evaluate_external_resources is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_evaluation_unavailable",
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("evaluation payload must be an object")
        capability = str(body.get("capability") or "").strip()
        scene_binding = body.get("scene_binding")
        if not capability:
            raise ValueError("capability is required")
        if not isinstance(scene_binding, Mapping):
            raise ValueError("scene_binding must be an object")
        trace_id = str(body.get("trace_id") or "").strip() or _default_trace_id(
            capability, scene_binding
        )
        projection, source = _resolve_catalog_projection()
        evaluation = evaluate_external_resources(
            _REPO_ROOT,
            projection,
            capability=capability,
            scene_binding=scene_binding,
            trace_id=trace_id,
        )
        persist_observation = bool(body.get("persist_observation", False))
        observation_result: dict[str, Any] | None = None
        if persist_observation:
            if record_external_resource_evaluation is None:
                raise RuntimeError("external_resource_evaluation_observer_unavailable")
            observation_result = record_external_resource_evaluation(
                _REPO_ROOT / ".omo",
                evaluation,
                workflow_run_id=str(body.get("workflow_run_id") or "").strip() or None,
                actor=str(body.get("actor_ref") or "cockpit").strip() or "cockpit",
                source_ref=str(body.get("source_ref") or "cockpit:external-resources:evaluate").strip()
                or "cockpit:external-resources:evaluate",
                observed_at=str(body.get("observed_at") or "").strip() or None,
                evaluation_id=str(body.get("evaluation_id") or "").strip() or None,
            )
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        status = "invalid" if isinstance(exc, (ValueError, TypeError)) else "unavailable"
        return {
            "ok": False,
            "status": status,
            "error": "external_resource_evaluation_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": evaluation.get("status", "unavailable"),
        "source": source,
        "evaluation": evaluation,
        "observation_status": (
            observation_result["status"] if observation_result else "not_requested"
        ),
        "observation_persisted": observation_result is not None,
        "observation": observation_result["observation"] if observation_result else None,
        "activation": "forbidden",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.get("/evaluations/selection")
async def get_external_resource_selection_evaluation(scene_id: str | None = None) -> dict[str, Any]:
    """Expose event-derived selection labels without changing Mesh state."""
    if build_external_resource_selection_dataset is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_selection_evaluation_unavailable",
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        dataset = build_external_resource_selection_dataset(
            _REPO_ROOT / ".omo", scene_id=scene_id
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_selection_evaluation_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": "live",
        "dataset": dataset,
        "activation": "forbidden",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/evaluations/proposal")
async def propose_external_resource_selection_policy(request: Request) -> dict[str, Any]:
    """Evaluate a candidate policy offline; never apply it to routing."""
    if (
        build_external_resource_selection_dataset is None
        or propose_selection_policy_feedback is None
    ):
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_selection_proposal_unavailable",
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("proposal payload must be an object")
        candidate = body.get("candidate")
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate must be an object")
        proposal_id = str(body.get("proposal_id") or "").strip()
        if not proposal_id:
            raise ValueError("proposal_id is required")
        dataset = build_external_resource_selection_dataset(
            _REPO_ROOT / ".omo", scene_id=body.get("scene_id")
        )
        proposal = propose_selection_policy_feedback(
            dataset, dict(candidate), proposal_id=proposal_id
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "status": "invalid" if isinstance(exc, (ValueError, TypeError)) else "unavailable",
            "error": "external_resource_selection_proposal_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": "proposal_only",
        "proposal": proposal,
        "activation": "forbidden",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }
