"""Week 4 — 真实输入接入 + 复盘 API 端点."""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from fastapi import APIRouter

from cockpit.compat import WORKSPACE_ROOT

_REPO_ROOT = WORKSPACE_ROOT


def _load(name: str, filename: str):
    path = _REPO_ROOT / "bin" / "ssot" / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _connector = _load("connector_api", "scene-card-connector.py")
    _review = _load("review_api", "scene-card-review.py")
    _available = True
    _error: str | None = None
except Exception as exc:
    _connector = None
    _review = None
    _available = False
    _error = str(exc)


router = APIRouter(prefix="/api/decision-inbox", tags=["decision-inbox-week4"])


def _unavailable() -> dict[str, Any]:
    return {"ok": False, "status": "unavailable", "error": _error or "engine unavailable"}


@router.post("/connector/run")
async def run_connector(body: dict) -> dict[str, Any]:
    if not _available:
        return _unavailable()
    try:
        result = _connector.run_connector(
            _REPO_ROOT,
            source=body.get("source", "manual"),
            scene_id=body.get("scene_id", ""),
            source_path=body.get("source_path", ""),
        )
        return {
            "ok": True,
            "run_id": result.run_id,
            "source": result.source,
            "items_found": result.items_found,
            "items_imported": result.items_imported,
            "errors": result.errors,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/connector/stats")
async def connector_stats() -> dict[str, Any]:
    if not _available:
        return _unavailable()
    try:
        stats = _connector.get_connector_stats(_REPO_ROOT)
        return {"ok": True, "stats": stats}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/review/weekly")
async def weekly_review(weeks: int = 1) -> dict[str, Any]:
    if not _available:
        return _unavailable()
    try:
        report = _review.generate_weekly_review(_REPO_ROOT, weeks=weeks)
        return {"ok": True, "report": report}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/review/pilot")
async def pilot_report() -> dict[str, Any]:
    if not _available:
        return _unavailable()
    try:
        report = _review.generate_pilot_report(_REPO_ROOT)
        return {"ok": True, "report": report}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
