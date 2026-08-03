"""Candidate-only Scene Card discovery and review for Cockpit."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from cockpit.compat import WORKSPACE_ROOT
from fastapi import APIRouter, Request

_REPO_ROOT = WORKSPACE_ROOT
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.omo_ingress_task_lifecycle import create_planned_task
except Exception as exc:
    create_planned_task = None  # type: ignore[assignment]
    _OMO_TASK_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_TASK_IMPORT_ERROR = None


def _load_script(name: str, filename: str) -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / filename
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _candidate_module = _load_script(
        "cockpit_scene_card_candidates", "scene-card-candidates.py"
    )
    collect_candidates = _candidate_module.collect_candidates
except Exception as exc:
    collect_candidates = None  # type: ignore[assignment]
    _CANDIDATE_IMPORT_ERROR: Exception | None = exc
else:
    _CANDIDATE_IMPORT_ERROR = None

try:
    _review_module = _load_script("cockpit_scene_card_review", "scene-card-review.py")
    create_review_receipt = _review_module.create_review_receipt
except Exception as exc:
    create_review_receipt = None  # type: ignore[assignment]
    _REVIEW_IMPORT_ERROR: Exception | None = exc
else:
    _REVIEW_IMPORT_ERROR = None

try:
    _intake_module = _load_script("cockpit_scene_card_intake", "scene-card-intake.py")
    build_intake = _intake_module.build_intake
except Exception as exc:
    build_intake = None  # type: ignore[assignment]
    _INTAKE_IMPORT_ERROR: Exception | None = exc
else:
    _INTAKE_IMPORT_ERROR = None

try:
    _preflight_module = _load_script(
        "cockpit_external_activation_preflight", "external-activation-preflight.py"
    )
    build_preflight = _preflight_module.build_preflight
except Exception as exc:
    build_preflight = None  # type: ignore[assignment]
    _PREFLIGHT_IMPORT_ERROR: Exception | None = exc
else:
    _PREFLIGHT_IMPORT_ERROR = None

try:
    from cockpit.web.api_external_resources import _latest_catalog
except Exception as exc:
    _latest_catalog = None  # type: ignore[assignment]
    _CATALOG_IMPORT_ERROR: Exception | None = exc
else:
    _CATALOG_IMPORT_ERROR = None


router = APIRouter(prefix="/api/scene-cards", tags=["scene-cards"])


def _scene_task_projection(
    *,
    status: str,
    scene: dict[str, Any],
    intake: dict[str, Any],
    next_action: str,
    task_id: str | None = None,
    preflight_status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    safe_scene = {
        key: str(scene.get(key) or "")
        for key in ("scene_id", "journey_id", "outcome_metric")
    }
    projection: dict[str, Any] = {
        "schema": "scene-card-task/v1",
        "mode": "planned_task_handoff",
        "status": status,
        "task_id": task_id,
        "intake_id": str(intake.get("intake_id") or ""),
        "source_digest": str(intake.get("source_digest") or ""),
        "scene_binding": safe_scene,
        "preflight_status": preflight_status,
        "next_action": next_action,
        "activation": "forbidden",
        "side_effects": {
            "provider_called": False,
            "workflow_created": False,
            "worker_launch": False,
            "activation_attempted": False,
        },
    }
    if error:
        projection["error"] = error
    return projection


def _scene_task_id(scene: dict[str, Any], source_digest: str) -> str:
    scene_id = str(scene.get("scene_id") or "unidentified")
    digest = hashlib.sha256(f"{scene_id}:{source_digest}".encode()).hexdigest()[:16]
    return f"cockpit-scene:{scene_id}:{digest}"


def _unavailable_projection(error_type: str, next_action: str) -> dict[str, Any]:
    return {
        "schema": "scene-card-candidate/v1",
        "mode": "candidate_only",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "candidates": [],
        "summary": {
            "candidate_count": 0,
            "activation_eligible_count": 0,
            "requires_business_confirmation_count": 0,
        },
        "status": "unavailable",
        "error_type": error_type,
        "next_action": next_action,
    }


@router.get("")
async def get_scene_card_candidates() -> dict[str, Any]:
    """Return safe candidates without reading raw business content."""
    if collect_candidates is None:
        projection = _unavailable_projection(
            type(_CANDIDATE_IMPORT_ERROR).__name__,
            "检查候选种子和场景契约后重试。",
        )
        return {"ok": False, "status": "unavailable", "projection": projection}
    try:
        projection = collect_candidates(_REPO_ROOT)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _unavailable_projection(
            type(exc).__name__, "检查候选种子和场景契约后重试。"
        )
        return {"ok": False, "status": "unavailable", "projection": projection}
    return {"ok": True, "status": "live", "projection": projection}


@router.post("/intake")
async def intake_scene_card(request: Request) -> dict[str, Any]:
    """Validate a Scene Card without persisting or activating it."""
    if build_intake is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "scene_card_intake_unavailable",
            "message": "Scene Card 输入契约不可用，未产生任何运行态变更。",
            "activation": "forbidden",
        }
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("intake payload must be an object")
        scene_card = payload.get("scene_card", payload)
        if not isinstance(scene_card, dict):
            raise ValueError("scene_card must be an object")
        projection = build_intake(scene_card)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "scene_card_intake_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
        }
    return {
        "ok": True,
        "status": projection["status"],
        "projection": projection,
        "activation": "forbidden",
        "activation_attempted": False,
        "persistence": "none",
    }


def _catalog_missing_projection(
    intake: dict[str, Any], *, status: str = "blocked", error: str | None = None
) -> dict[str, Any]:
    safe_scene = intake.get("scene_card", {})
    scene = {
        "scene_id": str(safe_scene.get("scene_id") or ""),
        "journey_id": str(safe_scene.get("journey_id") or ""),
        "outcome_metric": str(safe_scene.get("outcome_metric") or ""),
    }
    missing = sorted(
        {
            *[str(field) for field in intake.get("missing_fields", [])],
            "catalog_observation",
        }
    )
    projection: dict[str, Any] = {
        "schema": "external-activation-preflight/v1",
        "mode": "read_only_preflight",
        "activation": "forbidden",
        "scene": scene,
        "status": status,
        "next_action": "run_governed_external_resource_observation",
        "missing_fields": missing,
        "scene_card": {
            "missing_fields": [str(field) for field in intake.get("missing_fields", [])],
            "sample_ref_count": len(safe_scene.get("sample_refs", [])),
            "demand_evidence_ref_count": len(safe_scene.get("demand_evidence_refs", [])),
            "activation_evidence_ref_count": len(safe_scene.get("activation_evidence_refs", [])),
            "required_capabilities": [
                str(capability)
                for capability in safe_scene.get("required_capabilities", [])
            ],
        },
        "capability_checks": [],
        "catalog_freshness": {
            "status": "unknown",
            "observed_at": None,
            "age_seconds": None,
            "ttl_seconds": None,
            "reason_codes": ["missing_catalog_observation"],
        },
        "catalog_observed_at": None,
        "policy_digest": None,
        "side_effects": {
            "provider_called": False,
            "omo_written": False,
            "workflow_created": False,
        },
    }
    if error:
        projection["error"] = error
        projection["next_action"] = "检查 OMO 外部资源观测存储后重试。"
    return projection


@router.post("/preflight")
async def preflight_scene_card(request: Request) -> dict[str, Any]:
    """Run a read-only Scene Card preflight against the latest OMO catalog."""
    if build_intake is None or build_preflight is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "scene_card_preflight_unavailable",
            "activation": "forbidden",
            "persistence": "none",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("preflight payload must be an object")
        scene_card = payload.get("scene_card", payload)
        if not isinstance(scene_card, dict):
            raise ValueError("scene_card must be an object")
        intake = build_intake(scene_card)
        if _latest_catalog is None:
            projection = _catalog_missing_projection(
                intake, status="unavailable", error="external_catalog_unavailable"
            )
        else:
            catalog = _latest_catalog()
            if catalog is None:
                projection = _catalog_missing_projection(intake)
            else:
                projection = build_preflight(scene_card, catalog)
                projection["intake_status"] = intake["status"]
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "scene_card_preflight_invalid",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": projection["status"],
        "projection": projection,
        "catalog_source": "omo.external_resource_observation",
        "activation": "forbidden",
        "persistence": "none",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/task")
async def create_scene_card_task(request: Request) -> dict[str, Any]:
    """Create a planned OMO task only after a fresh, read-only preflight passes."""
    if build_intake is None or build_preflight is None or create_planned_task is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "scene_card_task_handoff_unavailable",
            "message": "场景任务承接依赖不可用，未创建任务或工作流。",
            "activation": "forbidden",
            "persistence": "none",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("task handoff payload must be an object")
        scene_card = payload.get("scene_card", payload)
        if not isinstance(scene_card, dict):
            raise ValueError("scene_card must be an object")
        intake = build_intake(scene_card)
        if intake.get("status") != "proposal_only":
            scene = intake.get("scene_card") or {}
            projection = _scene_task_projection(
                status="blocked",
                scene=scene,
                intake=intake,
                next_action="complete_scene_card_and_resubmit",
                preflight_status=None,
            )
            projection["blockers"] = list(intake.get("missing_fields") or [])
            return {
                "ok": True,
                "status": "blocked",
                "projection": projection,
                "activation": "forbidden",
                "persistence": "none",
                "external_side_effects": "disabled",
                "worker_launch": False,
            }
        catalog = _latest_catalog() if _latest_catalog is not None else None
        if catalog is None:
            scene = intake.get("scene_card") or {}
            projection = _scene_task_projection(
                status="blocked",
                scene=scene,
                intake=intake,
                next_action="run_governed_external_resource_observation",
                preflight_status="blocked",
            )
            projection["blockers"] = ["catalog_observation"]
            return {
                "ok": True,
                "status": "blocked",
                "projection": projection,
                "activation": "forbidden",
                "persistence": "none",
                "external_side_effects": "disabled",
                "worker_launch": False,
            }

        preflight = build_preflight(scene_card, catalog)
        scene = preflight.get("scene") or intake.get("scene_card") or {}
        if preflight.get("status") != "ready_for_admission_preview":
            projection = _scene_task_projection(
                status="blocked",
                scene=scene,
                intake=intake,
                next_action=str(preflight.get("next_action") or "resolve_preflight_blockers"),
                preflight_status=str(preflight.get("status") or "unknown"),
            )
            projection["blockers"] = list(preflight.get("missing_fields") or [])
            return {
                "ok": True,
                "status": "blocked",
                "projection": projection,
                "activation": "forbidden",
                "persistence": "none",
                "external_side_effects": "disabled",
                "worker_launch": False,
            }

        source_digest = str(intake.get("source_digest") or "")
        task_id = _scene_task_id(scene, source_digest)
        source_ref = f"cockpit:scene-card:task:{intake.get('intake_id', task_id)}"
        task_path = _REPO_ROOT / ".omo" / "tasks" / "planned" / f"{task_id}.yaml"
        existed = task_path.exists()
        risk_level = str(payload.get("risk_level") or "L1").upper()
        if risk_level not in {"L0", "L1", "L2", "L3"}:
            raise ValueError("risk_level must be L0, L1, L2, or L3")
        safe_scene = {
            key: str(scene.get(key) or "")
            for key in ("scene_id", "journey_id", "outcome_metric")
        }
        task_data = {
            "id": task_id,
            "title": f"Scene Card task: {safe_scene['scene_id']}",
            "description": f"Governed handoff for scene {safe_scene['scene_id']}.",
            "status": "pending",
            "task_type": "governance",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "risk_level": risk_level,
            "allowed_operation_level": risk_level,
            "human_approval_required": risk_level in {"L2", "L3"},
            "source_docs": [f"cockpit:scene-card:{safe_scene['scene_id']}"],
            "entry_gate": ["确认场景绑定与结果指标", "通过外部能力只读预检"],
            "evidence_required": ["workflow_run_evidence", "external_receipt", "outcome_feedback"],
            "deliverables": ["完成场景对应的受治理 Workflow Mesh 请求"],
            "test_plan": ["在任务中心复核场景绑定、能力健康和预算门禁"],
            "priority": "medium",
            "tags": ["cockpit-scene-card", "workflow-mesh-handoff"],
            "metadata": {
                "created_via": "cockpit-scene-card",
                "scene_binding": safe_scene,
                "scene_card_intake_id": str(intake.get("intake_id") or ""),
                "scene_card_source_digest": source_digest,
                "preflight_status": preflight.get("status"),
                "activation": "forbidden",
                "worker_launch": False,
            },
        }
        created = create_planned_task(
            _REPO_ROOT / ".omo",
            task_data=task_data,
            ingress_plane="cockpit-scene-card",
            source_ref=source_ref,
        )
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid" if isinstance(exc, ValueError) else "unavailable",
            "error": "scene_card_task_handoff_failed",
            "message": str(exc),
            "activation": "forbidden",
            "persistence": "none",
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    projection = _scene_task_projection(
        status="deduplicated" if existed else "created",
        scene=scene,
        intake=intake,
        next_action="open_task_center_and_request_workflow",
        task_id=task_id,
        preflight_status=str(preflight.get("status") or ""),
    )
    projection["task_status"] = str(created.get("status") or "pending")
    return {
        "ok": True,
        "status": projection["status"],
        "projection": projection,
        "activation": "forbidden",
        "persistence": "omo_planned_task",
        "external_side_effects": "disabled",
        "worker_launch": False,
    }


@router.post("/review")
async def review_scene_card_candidate(request: Request) -> dict[str, Any]:
    """Create a privacy-safe review receipt; never persist or activate."""
    if collect_candidates is None or create_review_receipt is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "scene_card_review_unavailable",
            "message": "候选或评审契约不可用，未产生任何运行态变更。",
        }
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("review payload must be an object")
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            raise ValueError("candidate_id is required")
        decision = str(payload.get("decision", "pending") or "pending").strip()
        reviewer_ref = str(payload.get("reviewer_ref", "") or "")
        note = str(payload.get("note", "") or "")
        projection = collect_candidates(_REPO_ROOT)
        receipt = create_review_receipt(
            projection,
            candidate_id=candidate_id,
            decision=decision,
            reviewer_ref=reviewer_ref,
            note=note,
        )
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "error": "scene_card_review_invalid",
            "message": str(exc),
            "activation": "forbidden",
        }
    return {
        "ok": True,
        "status": "recorded",
        "receipt": receipt,
        "activation": "forbidden",
        "activation_attempted": False,
        "persistence": "none",
    }
