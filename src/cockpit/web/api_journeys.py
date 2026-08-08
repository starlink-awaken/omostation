"""Cockpit Web API — Journeys Timeline Endpoint.

Read-only projection of delivery journeys as a chronological timeline,
aggregating scene outcomes, decision outcomes, and adjudications.
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

router = APIRouter(prefix="/api/journeys", tags=["journeys"]) if APIRouter else None


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


def _read_adjudications(root: Path) -> list[dict[str, Any]]:
    path = root / ".omo" / "_delivery" / "outcomes" / "adjudications.jsonl"
    return _read_jsonl(path)


if router:

    @router.get("")
    @router.get("/")
    async def get_journeys_timeline(
        scene_id: str | None = Query(None, description="Filter by scene_id"),  # type: ignore[union-attr]
        limit: int = Query(50, ge=1, le=500),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Chronological timeline of delivery journeys from multiple sources."""
        root = _workspace_root()
        entries: list[dict[str, Any]] = []

        scene_outcomes = _read_jsonl(root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl")
        for r in scene_outcomes:
            entries.append(
                {
                    "source": "scene-outcome",
                    "scene_id": r.get("scene_id", ""),
                    "journey_id": r.get("run_id", ""),
                    "status": r.get("adjudication", "pending"),
                    "started_at": r.get("ts", ""),
                    "completed_at": r.get("ts", ""),
                    "actor": r.get("actor", ""),
                    "notes": r.get("notes", ""),
                }
            )

        decision_outcomes = _read_beliefs_outcomes(root)
        for r in decision_outcomes:
            scene = str(r.get("decision_type", "")).replace("scene:", "", 1)
            entries.append(
                {
                    "source": "decision-outcome",
                    "scene_id": scene,
                    "journey_id": r.get("id", ""),
                    "status": r.get("actual_outcome", "unknown"),
                    "started_at": r.get("decision_at", ""),
                    "completed_at": r.get("decision_at", ""),
                    "actor": "",
                    "notes": r.get("delta", ""),
                }
            )

        adjudications = _read_adjudications(root)
        for r in adjudications:
            entries.append(
                {
                    "source": "adjudication",
                    "scene_id": "",
                    "journey_id": r.get("decision_id", r.get("id", "")),
                    "status": r.get("verdict", ""),
                    "started_at": r.get("adjudicated_at", ""),
                    "completed_at": r.get("adjudicated_at", ""),
                    "actor": r.get("adjudicator", ""),
                    "notes": r.get("notes", ""),
                }
            )

        if scene_id:
            entries = [e for e in entries if e["scene_id"] == scene_id]

        entries.sort(key=lambda e: e["started_at"], reverse=True)

        succeeded = sum(
            1 for e in entries if e["status"] in ("accepted", "succeeded") or "accept" in e["status"].lower()
        )
        total = len(entries)

        return {
            "ok": True,
            "total": total,
            "success_rate": round(succeeded / total, 3) if total else 0.0,
            "items": entries[:limit],
        }
