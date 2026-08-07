"""Decision Inbox — 摄入管线 API 端点.

The intake pipeline takes raw input from multiple sources, extracts structured
content, enriches with knowledge, and adds to the decision inbox.

Sources: email, file, message, manual, oa, sms
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from fastapi import APIRouter, HTTPException

from cockpit.compat import WORKSPACE_ROOT

_REPO_ROOT = WORKSPACE_ROOT

_ENGINE_PATH = _REPO_ROOT / "bin" / "ssot" / "scene-card-intake-pipeline.py"


def _load_engine():
    spec = importlib.util.spec_from_file_location("scene_card_intake_pipeline", _ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-intake-pipeline.py is unavailable")
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


router = APIRouter(prefix="/api/decision-inbox/intake", tags=["decision-inbox-intake"])


def _unavailable() -> dict[str, Any]:
    return {"ok": False, "status": "unavailable", "error": _engine_error or "engine unavailable"}


@router.post("/preview")
async def preview_intake(body: dict) -> dict[str, Any]:
    """Preview what the intake pipeline would produce without persisting."""
    if not _engine_available:
        return _unavailable()
    try:
        raw_content = body.get("content", "")
        source = body.get("source", "manual")
        filename = body.get("filename", "")
        if not raw_content:
            return {"ok": False, "status": "invalid", "error": "content is required"}
        enriched = _engine.preview_intake(raw_content, source=source, filename=filename)
        return {
            "ok": True,
            "enriched": {
                "title": enriched.title,
                "description": enriched.description[:200],
                "category": enriched.category,
                "priority": enriched.priority,
                "deadline": enriched.deadline,
                "tags": enriched.tags,
                "confidence": enriched.confidence,
                "extraction_method": enriched.extraction_method,
            },
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/{scene_id}")
async def run_intake(scene_id: str, body: dict) -> dict[str, Any]:
    """Run the full intake pipeline: extract → enrich → add to inbox."""
    if not _engine_available:
        return _unavailable()
    try:
        raw_content = body.get("content", "")
        source = body.get("source", "manual")
        filename = body.get("filename", "")
        journey_id = body.get("journey_id")
        if not raw_content:
            return {"ok": False, "status": "invalid", "error": "content is required"}
        result = _engine.intake(
            _REPO_ROOT,
            source=source,
            raw_content=raw_content,
            scene_id=scene_id,
            journey_id=journey_id,
            filename=filename,
            enrich=body.get("enrich", True),
        )
        if not result.ok:
            return {"ok": False, "status": "error", "error": result.error}
        enriched_dict = {
            "title": result.enriched.title if result.enriched else "",
            "priority": result.enriched.priority if result.enriched else "P3",
            "category": result.enriched.category if result.enriched else "",
            "tags": result.enriched.tags if result.enriched else [],
        }
        return {
            "ok": True,
            "intent_id": result.intent_id,
            "scene_id": result.scene_id,
            "journey_id": result.journey_id,
            "enriched": enriched_dict,
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/{scene_id}/batch")
async def run_batch_intake(scene_id: str, body: dict) -> dict[str, Any]:
    """Run batch intake for multiple items."""
    if not _engine_available:
        return _unavailable()
    try:
        items = body.get("items", [])
        if not items:
            return {"ok": False, "status": "invalid", "error": "items is required"}
        results = _engine.batch_intake(
            _REPO_ROOT,
            items=items,
            scene_id=scene_id,
        )
        return {
            "ok": True,
            "results": [
                {
                    "ok": r.ok,
                    "intent_id": r.intent_id,
                    "error": r.error,
                }
                for r in results
            ],
            "total": len(results),
            "succeeded": sum(1 for r in results if r.ok),
            "failed": sum(1 for r in results if not r.ok),
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}
