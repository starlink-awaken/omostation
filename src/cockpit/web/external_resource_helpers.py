"""Shared projection helpers for the external resource API."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    from omo.omo_external_evaluation import record_external_resource_evaluation
    from omo.omo_external_pack import (
        ExternalResourcePackProposalError,
        record_external_resource_pack_proposal,
    )
    from omo.omo_external_resources import (
        read_latest_external_resource_observation,
    )
    from omo.omo_external_scene_readiness import (
        build_external_scene_trial_promotion_readiness,
    )
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
except Exception:  # OMO is optional while Cockpit is being bootstrapped.
    read_latest_external_resource_observation = None  # type: ignore[assignment]
    record_external_resource_evaluation = None  # type: ignore[assignment]
    record_external_resource_pack_proposal = None  # type: ignore[assignment]
    read_external_scene_trials = None  # type: ignore[assignment]
    read_external_scene_trial_feedback = None  # type: ignore[assignment]
    record_external_scene_trial_feedback = None  # type: ignore[assignment]
    build_external_scene_trial_promotion_readiness = None  # type: ignore[assignment]
    ExternalSceneTrialFeedbackError = ValueError  # type: ignore[assignment,misc]
    ExternalResourcePackProposalError = ValueError  # type: ignore[assignment,misc]
    build_external_resource_selection_dataset = None  # type: ignore[assignment]
    propose_selection_policy_feedback = None  # type: ignore[assignment]
    _OMO_IMPORT_ERROR: BaseException | None = sys.exc_info()[1]
else:
    _OMO_IMPORT_ERROR = None


_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))


def _load_catalog_module() -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / "external-resource-catalog.py"
    spec = importlib.util.spec_from_file_location("cockpit_external_resource_catalog_projection", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("external resource catalog projection is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _catalog_module = _load_catalog_module()
    collect_external_resources = _catalog_module.collect_external_resources
    build_external_resource_directory_snapshot = _catalog_module.build_external_resource_directory_snapshot
    build_external_resource_connection_plan = _catalog_module.build_external_resource_connection_plan
    build_external_resource_refresh_plan = _catalog_module.build_external_resource_refresh_plan
    observe_external_resources = _catalog_module.observe_external_resources
    evaluate_external_resources = _catalog_module.evaluate_external_resources
except Exception:  # Discovery is allowed to degrade independently.
    collect_external_resources = None  # type: ignore[assignment]
    build_external_resource_directory_snapshot = None  # type: ignore[assignment]
    build_external_resource_connection_plan = None  # type: ignore[assignment]
    build_external_resource_refresh_plan = None  # type: ignore[assignment]
    observe_external_resources = None  # type: ignore[assignment]
    evaluate_external_resources = None  # type: ignore[assignment]
    _CATALOG_IMPORT_ERROR: BaseException | None = sys.exc_info()[1]
else:
    _CATALOG_IMPORT_ERROR = None


def _load_pack_module() -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / "external-resource-pack.py"
    spec = importlib.util.spec_from_file_location("cockpit_external_resource_pack_projection", module_path)
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
except Exception:  # Discovery is allowed to degrade independently.
    check_external_resource_pack = None  # type: ignore[assignment]
    ExternalResourcePackError = ValueError  # type: ignore[assignment,misc]
    _PACK_IMPORT_ERROR: BaseException | None = sys.exc_info()[1]
else:
    _PACK_IMPORT_ERROR = None


_REVIEW_QUEUE_SCHEMA = "external-resource-review-queue/v1"
_SCENE_TRIAL_REVIEW_SCHEMA = "external-scene-trial-review/v1"
_SCENE_TRIAL_READINESS_SCHEMA = "external-scene-trial-promotion-readiness/v1"
_CAPABILITY_DIRECTORY_SCHEMA = "external-resource-directory/v1"
_CONNECTION_PLAN_SCHEMA = "external-resource-connection-plan/v1"
_REFRESH_STATUS_SCHEMA = "external-resource-refresh-status/v1"
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


def _unavailable_directory_projection(error_type: str, next_action: str) -> dict[str, Any]:
    return {
        "schema": _CAPABILITY_DIRECTORY_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "resources": [],
        "capability_index": {},
        "kind_index": {},
        "next_steps": [],
        "summary": {
            "resource_count": 0,
            "capability_count": 0,
            "kind_count": 0,
            "available_count": 0,
            "proposal_only_count": 0,
            "unavailable_count": 0,
            "next_step_counts": {},
        },
        "catalog_errors": [{"entry_point": "cockpit", "status": "unavailable", "error": error_type}],
        "policy": {
            "source": "external-resource-catalog/v1",
            "side_effects": "disabled",
            "next_step_semantics": "human_or_governed_review_only",
        },
        "status": "unavailable",
        "next_action": next_action,
    }


def _unavailable_connection_plan_projection(error_type: str, next_action: str) -> dict[str, Any]:
    return {
        "schema": _CONNECTION_PLAN_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "directory_digest": "",
        "items": [],
        "summary": {
            "resource_count": 0,
            "blocked_count": 0,
            "ready_for_review_count": 0,
            "next_step_counts": {},
        },
        "policy": {
            "source": _CAPABILITY_DIRECTORY_SCHEMA,
            "side_effects": "disabled",
            "semantics": "evidence_collection_and_human_or_governed_review_only",
        },
        "errors": [{"entry_point": "cockpit", "status": "unavailable", "error": error_type}],
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


def _refresh_status_projection(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Expose freshness and the next safe recovery action from OMO state."""
    base: dict[str, Any] = {
        "schema": _REFRESH_STATUS_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "worker_launch": False,
        "source": "omo.external_resource_observation",
    }
    if observation is None:
        return {
            **base,
            "status": "empty",
            "freshness": "unknown",
            "observed_at": None,
            "recorded_at": None,
            "observation_id": None,
            "age_seconds": None,
            "catalog_ttl_seconds": None,
            "change_state": None,
            "review_required": False,
            "risk_codes": [],
            "next_action": "运行一次受治理刷新，建立首个外部资源观测基线。",
        }
    catalog = observation.get("catalog")
    if not isinstance(catalog, Mapping):
        raise ValueError("external resource observation catalog is invalid")
    observed_at = str(observation.get("observed_at") or catalog.get("observed_at") or "")
    ttl = int(catalog.get("catalog_ttl_seconds", 3600) or 3600)
    now = datetime.datetime.now(datetime.UTC)
    try:
        observed_datetime = datetime.datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        age_seconds = max(0, int((now - observed_datetime).total_seconds()))
        freshness = "fresh" if age_seconds <= ttl else "stale"
    except (TypeError, ValueError):
        age_seconds = None
        freshness = "invalid"
    change_summary = observation.get("change_summary")
    if not isinstance(change_summary, Mapping):
        change_summary = {}
    review_required = bool(change_summary.get("review_required", False))
    risk_codes = sorted({str(code).strip() for code in change_summary.get("risk_codes", []) if str(code).strip()})
    next_action = (
        "先完成人工复核，再决定是否进入场景试运行。"
        if review_required
        else "运行受治理刷新，确认外部资源健康和目录新鲜度。"
        if freshness in {"stale", "invalid"}
        else "当前观测仍在新鲜窗口内，可继续进行只读场景评估。"
    )
    return {
        **base,
        "status": "attention" if review_required else "ready",
        "freshness": freshness,
        "observed_at": observed_at or None,
        "recorded_at": observation.get("recorded_at"),
        "observation_id": observation.get("observation_id"),
        "age_seconds": age_seconds,
        "catalog_ttl_seconds": ttl,
        "change_state": observation.get("change_state"),
        "review_required": review_required,
        "risk_codes": risk_codes,
        "next_action": next_action,
    }


def _safe_review_snapshot(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("review snapshot must be an object")
    return {field: value[field] for field in _REVIEW_SNAPSHOT_FIELDS if field in value}


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
        codes = sorted({str(code).strip() for code in change.get("risk_codes", []) if str(code).strip()})
        risk_codes.update(codes)
        if not bool(change.get("review_required", False)):
            if change.get("risk_class") == "operational_observation":
                operational_count += 1
            continue
        resource_id = str(change.get("id") or "").strip()
        if not resource_id:
            raise ValueError("external resource review item is missing id")
        changed_fields = sorted(
            {str(field).strip() for field in change.get("changed_fields", []) if str(field).strip()}
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


__all__ = [
    "_REPO_ROOT",
    "_OMO_SRC",
    "_load_catalog_module",
    "_load_pack_module",
    "check_external_resource_pack",
    "ExternalResourcePackError",
    "_PACK_IMPORT_ERROR",
    "_REVIEW_QUEUE_SCHEMA",
    "_SCENE_TRIAL_REVIEW_SCHEMA",
    "_SCENE_TRIAL_READINESS_SCHEMA",
    "_CAPABILITY_DIRECTORY_SCHEMA",
    "_CONNECTION_PLAN_SCHEMA",
    "_REFRESH_STATUS_SCHEMA",
    "_REVIEW_SNAPSHOT_FIELDS",
    "_unavailable_projection",
    "_unavailable_directory_projection",
    "_unavailable_connection_plan_projection",
    "_latest_observation",
    "_latest_catalog",
    "_refresh_status_projection",
    "_safe_review_snapshot",
    "_review_queue_projection",
    "_scene_trial_review_projection",
    "_projection_status",
    "_resolve_catalog_projection",
    "_default_trace_id",
]
