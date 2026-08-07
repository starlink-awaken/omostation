"""Decision Inbox — Scene Card 决策收件箱 API 端点.

The decision inbox is a P0 business scenario: collect raw intents from
multiple sources, structure them into a decision list, and drive the
lifecycle: pending → task_created → approved/rejected → done.

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-decision-inbox.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from cockpit.compat import WORKSPACE_ROOT

_REPO_ROOT = WORKSPACE_ROOT

# ── Load decision inbox engine ──

_ENGINE_PATH = _REPO_ROOT / "bin" / "ssot" / "scene-card-decision-inbox.py"


def _load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("scene_card_decision_inbox", _ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-decision-inbox.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _engine = _load_engine()
    _engine_available = True
    _engine_error: str | None = None
except Exception as exc:
    _engine = None
    _engine_available = False
    _engine_error = str(exc)


router = APIRouter(prefix="/api/decision-inbox", tags=["decision-inbox"])


def _unavailable(message: str) -> dict[str, Any]:
    return {"ok": False, "status": "unavailable", "error": str(message)}


# ── Scene management ──


@router.post("/scenes")
async def create_inbox_scene(request: Request) -> dict[str, Any]:
    """Create a new decision inbox scene."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        scene = _engine.create_scene(
            _REPO_ROOT,
            name=payload.get("name", "Untitled Scene"),
            description=payload.get("description", ""),
            priority=payload.get("priority", "P1"),
        )
        return {"ok": True, "scene": _engine._dictify(scene)}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "invalid", "error": str(exc)}


@router.get("/scenes")
async def list_inbox_scenes() -> dict[str, Any]:
    """List all decision inbox scenes."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        scenes = _engine.list_scenes(_REPO_ROOT)
        return {"ok": True, "scenes": [_engine._dictify(s) for s in scenes]}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/scenes/{scene_id}")
async def get_inbox_scene(scene_id: str) -> dict[str, Any]:
    """Get a single decision inbox scene."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        scene = _engine.load_scene(_REPO_ROOT, scene_id)
        if scene is None:
            raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
        return {"ok": True, "scene": _engine._dictify(scene)}
    except HTTPException:
        raise
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


# ── Journey management ──


@router.post("/scenes/{scene_id}/journeys")
async def create_inbox_journey(scene_id: str, request: Request) -> dict[str, Any]:
    """Create a new journey in a scene."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        payload = await request.json()
        journey = _engine.create_journey(
            _REPO_ROOT,
            scene_id=scene_id,
            name=payload.get("name", "Untitled Journey"),
        )
        return {"ok": True, "journey": _engine._dictify(journey)}
    except ValueError as exc:
        return {"ok": False, "status": "not_found", "error": str(exc)}
    except (OSError, RuntimeError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


# ── Intent management ──


@router.post("/scenes/{scene_id}/intents")
async def add_inbox_intent(scene_id: str, request: Request) -> dict[str, Any]:
    """Add an intent to a scene's first journey."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        payload = await request.json()
        scene = _engine.load_scene(_REPO_ROOT, scene_id)
        if scene is None:
            raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
        if not scene.journeys:
            raise HTTPException(status_code=400, detail="Scene has no journeys. Create a journey first.")
        journey_id = payload.get("journey_id") or scene.journeys[0].id
        intent = _engine.add_intent(
            _REPO_ROOT,
            scene_id=scene_id,
            journey_id=journey_id,
            source=payload.get("source", "manual"),
            raw_content=payload.get("raw_content", ""),
            priority=payload.get("priority", "P3"),
        )
        return {"ok": True, "intent": _engine._dictify(intent)}
    except HTTPException:
        raise
    except ValueError as exc:
        return {"ok": False, "status": "not_found", "error": str(exc)}
    except (OSError, RuntimeError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/scenes/{scene_id}/intents")
async def list_inbox_intents(
    scene_id: str,
    status: str | None = None,
) -> dict[str, Any]:
    """List intents in a scene, optionally filtered by status."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        intents = _engine.list_intents(_REPO_ROOT, scene_id, status_filter=status)
        return {"ok": True, "intents": [_engine._dictify(i) for i in intents]}
    except ValueError as exc:
        return {"ok": False, "status": "not_found", "error": str(exc)}
    except (OSError, RuntimeError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.patch("/intents/{intent_id}")
async def update_inbox_intent(intent_id: str, request: Request) -> dict[str, Any]:
    """Update an intent's status and optionally assign a task_id."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        payload = await request.json()
        new_status = payload.get("status", "pending")
        intent = _engine.update_intent_status(
            _REPO_ROOT,
            intent_id=intent_id,
            new_status=new_status,
            task_id=payload.get("task_id"),
            actor=payload.get("actor"),
        )
        if intent is None:
            raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")
        return {"ok": True, "intent": _engine._dictify(intent)}
    except HTTPException:
        raise
    except ValueError as exc:
        return {"ok": False, "status": "invalid", "error": str(exc)}
    except (OSError, RuntimeError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


# ── Summary ──


@router.get("/summary")
async def inbox_summary() -> dict[str, Any]:
    """Get a summary of all pending intents across all scenes."""
    if not _engine_available:
        return _unavailable(_engine_error)
    try:
        summary = _engine.get_inbox_summary(_REPO_ROOT)
        return {"ok": True, "summary": summary}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}
