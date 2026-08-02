"""Candidate-only Scene Card discovery and review for Cockpit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

_REPO_ROOT = Path(__file__).resolve().parents[5]


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


router = APIRouter(prefix="/api/scene-cards", tags=["scene-cards"])


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
