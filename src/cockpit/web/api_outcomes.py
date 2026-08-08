"""Cockpit Web API — Outcomes & Calibration Endpoints.

Read-only projection of decision outcomes, adjudication history,
and capability calibration data for the /outcomes panel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from fastapi import APIRouter, Query
except ImportError:
    APIRouter = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment-none]

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"]) if APIRouter else None


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _read_calibration_summary(root: Path) -> dict[str, Any]:
    path = root / ".omo" / "_delivery" / "outcomes" / "capability_calibration_summary.yaml"
    if not path.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_beliefs_calibrations(root: Path) -> list[dict[str, Any]]:
    path = root / ".omo" / "state" / "agent-beliefs" / "index.yaml"
    if not path.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        calibrations = data.get("capability_calibrations", [])
        return calibrations if isinstance(calibrations, list) else []
    except Exception:
        return []


def _read_beliefs_outcomes(root: Path) -> list[dict[str, Any]]:
    path = root / ".omo" / "state" / "agent-beliefs" / "index.yaml"
    if not path.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        outcomes = data.get("decision_outcomes", [])
        return outcomes if isinstance(outcomes, list) else []
    except Exception:
        return []


if router:

    @router.get("")
    @router.get("/")
    async def get_outcomes_summary() -> dict[str, Any]:
        """Aggregate outcomes summary: pending count, history count, calibration entries."""
        root = _workspace_root()
        outcomes = _read_jsonl(root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl")
        pending = [r for r in outcomes if r.get("adjudication") == "pending"]
        history = [r for r in outcomes if r.get("adjudication") != "pending"]
        calibration = _read_calibration_summary(root)
        return {
            "ok": True,
            "pending_count": len(pending),
            "history_count": len(history),
            "calibration_scenes": len(calibration),
        }

    @router.get("/pending")
    async def get_outcomes_pending() -> dict[str, Any]:
        """Scene outcomes awaiting human adjudication."""
        root = _workspace_root()
        outcomes = _read_jsonl(root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl")
        pending = [
            {
                "scene_id": r.get("scene_id", ""),
                "run_id": r.get("run_id", ""),
                "submitted_at": r.get("ts", ""),
                "actor": r.get("actor", ""),
                "notes": r.get("notes", ""),
            }
            for r in outcomes
            if r.get("adjudication") == "pending"
        ]
        pending.sort(key=lambda r: r["submitted_at"], reverse=True)
        return {"ok": True, "items": pending}

    @router.get("/history")
    async def get_outcomes_history(
        limit: int = Query(50, ge=1, le=500),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Adjudicated scene outcomes, newest first."""
        root = _workspace_root()
        outcomes = _read_jsonl(root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl")
        history = [
            {
                "scene_id": r.get("scene_id", ""),
                "run_id": r.get("run_id", ""),
                "adjudication": r.get("adjudication", ""),
                "actor": r.get("actor", ""),
                "adjudicated_at": r.get("ts", ""),
                "notes": r.get("notes", ""),
            }
            for r in outcomes
            if r.get("adjudication") != "pending"
        ]
        history.sort(key=lambda r: r["adjudicated_at"], reverse=True)
        return {"ok": True, "items": history[:limit]}

    @router.get("/calibration")
    async def get_outcomes_calibration() -> dict[str, Any]:
        """Per-scene calibration rollups + per-capability measurements."""
        root = _workspace_root()
        summary = _read_calibration_summary(root)
        capabilities = _read_beliefs_calibrations(root)

        scenes = []
        for scene_key, data in sorted(summary.items()):
            if not isinstance(data, dict):
                continue
            scenes.append(
                {
                    "scene_id": scene_key,
                    "accepted": data.get("accepted", 0),
                    "total": data.get("total", 0),
                    "calibration": data.get("calibration", 0.0),
                    "updated_at": data.get("updated_at", ""),
                }
            )

        caps = []
        for c in capabilities:
            if not isinstance(c, dict):
                continue
            caps.append(
                {
                    "id": c.get("id", ""),
                    "capability_ref": c.get("capability_ref", ""),
                    "success_rate": c.get("success_rate", 0.0),
                    "sample_size": c.get("sample_size", 0),
                    "measured_at": c.get("measured_at", ""),
                }
            )

        return {"ok": True, "scenes": scenes, "capabilities": caps}
