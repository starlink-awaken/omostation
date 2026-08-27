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

from cockpit.web import external_resource_helpers
from cockpit.web.external_resource_helpers import (
    _CAPABILITY_DIRECTORY_SCHEMA,
    _CONNECTION_PLAN_SCHEMA,
    _REFRESH_STATUS_SCHEMA,
    _REVIEW_QUEUE_SCHEMA,
    _REVIEW_SNAPSHOT_FIELDS,
    _SCENE_TRIAL_READINESS_SCHEMA,
    _SCENE_TRIAL_REVIEW_SCHEMA,
    _default_trace_id,
    _latest_catalog,
    _latest_observation,
    _projection_status,
    _refresh_status_projection,
    _resolve_catalog_projection,
    _review_queue_projection,
    _safe_review_snapshot,
    _scene_trial_review_projection,
    _unavailable_connection_plan_projection,
    _unavailable_directory_projection,
    _unavailable_projection,
)

read_latest_external_resource_observation = external_resource_helpers.read_latest_external_resource_observation
record_external_resource_evaluation = external_resource_helpers.record_external_resource_evaluation
record_external_resource_pack_proposal = external_resource_helpers.record_external_resource_pack_proposal
read_external_scene_trials = external_resource_helpers.read_external_scene_trials
read_external_scene_trial_feedback = external_resource_helpers.read_external_scene_trial_feedback
record_external_scene_trial_feedback = external_resource_helpers.record_external_scene_trial_feedback
build_external_scene_trial_promotion_readiness = external_resource_helpers.build_external_scene_trial_promotion_readiness
ExternalSceneTrialFeedbackError = external_resource_helpers.ExternalSceneTrialFeedbackError
ExternalResourcePackError = external_resource_helpers.ExternalResourcePackError
ExternalResourcePackProposalError = external_resource_helpers.ExternalResourcePackProposalError
build_external_resource_selection_dataset = external_resource_helpers.build_external_resource_selection_dataset
propose_selection_policy_feedback = external_resource_helpers.propose_selection_policy_feedback
_OMO_IMPORT_ERROR: BaseException | None = getattr(external_resource_helpers, "_OMO_IMPORT_ERROR", None)

collect_external_resources = external_resource_helpers.collect_external_resources
build_external_resource_directory_snapshot = external_resource_helpers.build_external_resource_directory_snapshot
build_external_resource_connection_plan = external_resource_helpers.build_external_resource_connection_plan
build_external_resource_refresh_plan = external_resource_helpers.build_external_resource_refresh_plan
observe_external_resources = external_resource_helpers.observe_external_resources
evaluate_external_resources = external_resource_helpers.evaluate_external_resources
_CATALOG_IMPORT_ERROR: BaseException | None = getattr(external_resource_helpers, "_CATALOG_IMPORT_ERROR", None)
check_external_resource_pack = external_resource_helpers.check_external_resource_pack
_PACK_IMPORT_ERROR: BaseException | None = getattr(external_resource_helpers, "_PACK_IMPORT_ERROR", None)

_REPO_ROOT = external_resource_helpers._REPO_ROOT


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


router = APIRouter(prefix="/api/external-resources", tags=["external-resources"])


@router.get("/refresh-status")
async def get_external_resource_refresh_status() -> dict[str, Any]:
    """Expose freshness and recovery state without performing discovery."""
    if read_latest_external_resource_observation is None:
        projection = _refresh_status_projection(None)
        projection.update(
            {
                "status": "unavailable",
                "next_action": "检查 OMO 外部资源观测存储后重试。",
            }
        )
        return {"ok": False, "projection": projection, "external_side_effects": "disabled"}
    try:
        projection = _refresh_status_projection(_latest_observation())
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _refresh_status_projection(None)
        projection.update(
            {
                "status": "unavailable",
                "error": type(exc).__name__,
                "next_action": "检查 OMO 外部资源观测格式后重试。",
            }
        )
        return {"ok": False, "projection": projection, "external_side_effects": "disabled"}
    return {"ok": True, "projection": projection, "external_side_effects": "disabled"}


@router.get("/refresh-plan")
async def get_external_resource_refresh_plan() -> dict[str, Any]:
    """Expose the next safe observation cadence without scheduling work."""
    boundary = {
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "worker_launch": False,
        "external_side_effects": "disabled",
    }
    if build_external_resource_refresh_plan is None:
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_refresh_plan",
            "error": "external_resource_refresh_plan_unavailable",
            **boundary,
        }
    try:
        catalog, source = _resolve_catalog_projection()
        projection = build_external_resource_refresh_plan(catalog)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_refresh_plan",
            "error": type(exc).__name__,
            "message": "检查 OMO 外部资源观察或 Agora 只读发现后重试。",
            **boundary,
        }
    summary = projection.get("summary") or {}
    status = "empty" if not summary.get("resource_count") else "attention" if summary.get("due_count") else "ready"
    return {
        "ok": True,
        "status": status,
        "source": source,
        "projection": projection,
        **boundary,
    }


@router.post("/refresh")
async def refresh_external_resources(request: Request) -> dict[str, Any]:
    """Run one governed read-only catalog observation and persist its receipts."""
    boundary = {
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "worker_launch": False,
        "external_side_effects": "disabled",
    }
    if observe_external_resources is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "external_resource_observer_unavailable",
            **boundary,
        }
    try:
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise ValueError("refresh payload must be an object")
        unsupported = set(body) - {"actor_ref", "source_ref", "run_id", "probe"}
        if unsupported:
            raise ValueError(f"refresh payload contains unsupported fields: {sorted(unsupported)}")
        actor = str(body.get("actor_ref") or "cockpit-user").strip() or "cockpit-user"
        source_ref = str(body.get("source_ref") or "cockpit:external-resources:refresh").strip()
        run_id = str(body.get("run_id") or "").strip() or None
        probe = body.get("probe", True)
        if not isinstance(probe, bool):
            raise ValueError("probe must be boolean")
        result = observe_external_resources(
            _REPO_ROOT,
            actor=actor,
            source_ref=source_ref,
            run_id=run_id,
            probe=probe,
        )
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid" if isinstance(exc, (ValueError, TypeError)) else "unavailable",
            "error": "external_resource_refresh_failed",
            "message": str(exc),
            **boundary,
        }
    observation = result.get("observation")
    catalog = result.get("catalog")
    change_summary = observation.get("change_summary", {}) if isinstance(observation, Mapping) else {}
    return {
        "ok": True,
        "status": result.get("status", "recorded"),
        "observation_status": result.get("status", "recorded"),
        "observation_run_status": result.get("observation_run_status", "recorded"),
        "observation": observation,
        "observation_run": result.get("observation_run"),
        "catalog_summary": catalog.get("summary", {}) if isinstance(catalog, Mapping) else {},
        "change_summary": change_summary,
        "persistence": "omo_append_only",
        **boundary,
    }


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


@router.get("/directory")
async def get_external_resource_directory() -> dict[str, Any]:
    """Expose the capability map derived from the same catalog projection."""
    if build_external_resource_directory_snapshot is None:
        projection = _unavailable_directory_projection(
            "external_resource_directory_unavailable",
            "检查根仓 capability directory builder 后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_directory",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        catalog, source = _resolve_catalog_projection()
        projection = build_external_resource_directory_snapshot(catalog)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _unavailable_directory_projection(
            type(exc).__name__,
            "检查 OMO 外部资源观察或 Agora 只读发现后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_directory",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": "available" if projection["summary"]["available_count"] else "attention",
        "source": source,
        "projection": projection,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.get("/connection-plan")
async def get_external_resource_connection_plan() -> dict[str, Any]:
    """Expose evidence gaps for extending external capabilities safely."""
    if build_external_resource_directory_snapshot is None or build_external_resource_connection_plan is None:
        projection = _unavailable_connection_plan_projection(
            "external_resource_connection_plan_unavailable",
            "检查根仓 connection plan builder 后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_connection_plan",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        catalog, source = _resolve_catalog_projection()
        directory = build_external_resource_directory_snapshot(catalog)
        projection = build_external_resource_connection_plan(directory)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _unavailable_connection_plan_projection(
            type(exc).__name__,
            "检查 OMO 外部资源观察或 Agora 只读发现后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_connection_plan",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    summary = projection.get("summary") or {}
    status = (
        "empty" if not summary.get("resource_count") else "attention" if summary.get("blocked_count") else "available"
    )
    return {
        "ok": True,
        "status": status,
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


@router.get("/scene-trials/readiness")
async def get_external_scene_trial_promotion_readiness(
    scene_id: str | None = Query(None, description="Optional scene filter"),
) -> dict[str, Any]:
    """Expose promotion readiness without creating or activating a WorkflowRun."""
    boundary = {
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": "forbidden",
        "admission_mutation": "forbidden",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }
    if build_external_scene_trial_promotion_readiness is None:
        return {
            "ok": False,
            "status": "unavailable",
            "schema": _SCENE_TRIAL_READINESS_SCHEMA,
            "error": "external_scene_trial_readiness_unavailable",
            **boundary,
        }
    try:
        projection = build_external_scene_trial_promotion_readiness(_REPO_ROOT / ".omo", scene_id=scene_id)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "schema": _SCENE_TRIAL_READINESS_SCHEMA,
            "error": type(exc).__name__,
            "next_action": "检查场景试运行、Workflow Mesh 和结果反馈日志后重试。",
            **boundary,
        }
    return {
        "ok": projection.get("status") != "unavailable",
        "projection": projection,
        **boundary,
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
                "source_ref": str(payload.get("source_ref") or "cockpit:external-resources:scene-trial-review"),
                "observed_at": str(
                    payload.get("observed_at") or datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
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
        trace_id = str(body.get("trace_id") or "").strip() or _default_trace_id(capability, scene_binding)
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
        "observation_status": (observation_result["status"] if observation_result else "not_requested"),
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
        dataset = build_external_resource_selection_dataset(_REPO_ROOT / ".omo", scene_id=scene_id)
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
    if build_external_resource_selection_dataset is None or propose_selection_policy_feedback is None:
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
        dataset = build_external_resource_selection_dataset(_REPO_ROOT / ".omo", scene_id=body.get("scene_id"))
        proposal = propose_selection_policy_feedback(dataset, dict(candidate), proposal_id=proposal_id)
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
