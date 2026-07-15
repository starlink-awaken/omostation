"""Wave2 dashboard payload for cockpit API (ADR-0191).

Builds c2g.wave2.dashboard.v1 without requiring a live c2g install when
possible; falls back to empty baseline so the UI never hard-crashes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    env = os.environ.get("WORKSPACE_ROOT")
    if env:
        return Path(env)
    # helpers_wave2.py → dashboard → cockpit pkg → src → project → projects → workspace
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".omo").exists() or (parent / "projects" / "c2g").exists():
            return parent
    return here.parents[5]


def _default_data_dir(root: Path) -> Path:
    env = os.environ.get("C2G_OUTCOMES_DIR")
    if env:
        return Path(env)
    return root / "runtime" / "c2g" / "outcomes"


def empty_dashboard(reason: str = "empty") -> dict[str, Any]:
    return {
        "schema": "c2g.wave2.dashboard.v1",
        "adr": "0190",
        "source": "cockpit.helpers_wave2",
        "status": reason,
        "cards": {
            "pitch_count": 0,
            "mean_success": 0.0,
            "trend": "flat",
            "critical": 0,
            "elevated": 0,
            "proposal_count": 0,
            "p0_proposals": 0,
        },
        "backtest": {
            "pitch_count": 0,
            "mean_success_score": 0.0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "top": [],
            "status": "empty",
        },
        "forecast": {
            "n": 0,
            "mean": 0.0,
            "trend": "flat",
            "forecast": [],
            "deps": "stdlib-only",
        },
        "heatmap": {
            "statuses": ["active", "completed", "failed", "other"],
            "buckets": ["low", "mid", "high"],
            "matrix": {
                "active": {"low": 0, "mid": 0, "high": 0},
                "completed": {"low": 0, "mid": 0, "high": 0},
                "failed": {"low": 0, "mid": 0, "high": 0},
                "other": {"low": 0, "mid": 0, "high": 0},
            },
            "grid": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
            "cells": [],
            "totals": {"pitches": 0, "critical": 0, "elevated": 0, "ok": 0},
        },
        "heatmap_markdown": "| status | low | mid | high |\n|---|---|---|---|\n",
        "proposals": [],
        "auto_mutate_rules": False,
    }


def load_wave2_dashboard(
    data_dir: Path | None = None,
    *,
    horizon: int = 3,
) -> dict[str, Any]:
    """Return dashboard v1 payload; never raises to callers."""
    root = _workspace_root()
    ddir = data_dir or _default_data_dir(root)
    try:
        # Prefer in-process c2g when importable (workspace / uv path)
        from c2g.dashboard_export import build_dashboard  # type: ignore

        payload = build_dashboard(ddir, horizon=horizon)
        payload["source"] = "c2g.dashboard_export"
        payload["data_dir"] = str(ddir)
        # Enrich proposals with TaskCenter handoff hints (ADR-0192)
        payload["proposals"] = enrich_proposals_for_handoff(
            payload.get("proposals") or []
        )
        return payload
    except Exception as e:
        # Fallback empty with diagnostic — UI still renders
        payload = empty_dashboard(reason="degraded")
        payload["error"] = f"{type(e).__name__}: {e}"[:240]
        payload["data_dir"] = str(ddir)
        return payload


def enrich_proposals_for_handoff(proposals: list[Any]) -> list[dict[str, Any]]:
    """Attach task_query + handoff targets for cockpit TaskCenter deep-link."""
    out: list[dict[str, Any]] = []
    for raw in proposals:
        if not isinstance(raw, dict):
            continue
        p = dict(raw)
        pid = str(p.get("id") or "")
        title = str(p.get("title") or "")
        # Prefer stable C2G-FB-* id pattern used by governance_feedback apply
        task_query = f"C2G-FB-{pid}" if pid else (title[:48] or "C2G-FB")
        suggested = p.get("suggested_task") if isinstance(p.get("suggested_task"), dict) else {}
        if suggested.get("title"):
            # search TaskCenter by proposed title fragment
            task_query = str(suggested["title"])[:64]
        p["task_query"] = task_query
        p["handoff"] = {
            "tab": "TaskCenter",
            "taskQuery": task_query,
            "proposal_id": pid,
        }
        out.append(p)
    return out


def load_wave2_proposal_plan(
    data_dir: Path | None = None,
    *,
    horizon: int = 3,
) -> dict[str, Any]:
    """Dry-run OMO planned-task actions for current proposals (never mutates)."""
    root = _workspace_root()
    ddir = data_dir or _default_data_dir(root)
    omo_dir = root / ".omo"
    try:
        from c2g.governance_feedback import (  # type: ignore
            apply_proposals_as_tasks,
            build_proposals,
        )
        from c2g.outcome_tracker import OutcomeTracker  # type: ignore

        tracker = OutcomeTracker(ddir)
        proposals = build_proposals(tracker._outcomes, horizon=horizon)
        proposals["proposals"] = enrich_proposals_for_handoff(
            proposals.get("proposals") or []
        )
        actions = apply_proposals_as_tasks(
            proposals, omo_dir, dry_run=True
        )
        return {
            "schema": "c2g.wave2.proposal_plan.v1",
            "adr": "0192",
            "dry_run": True,
            "auto_mutate_rules": False,
            "mutation": False,
            "data_dir": str(ddir),
            "omo_dir": str(omo_dir),
            "proposal_count": proposals.get("proposal_count", 0),
            "proposals": proposals.get("proposals") or [],
            "task_actions": actions,
            "status": "ok",
        }
    except Exception as e:
        return {
            "schema": "c2g.wave2.proposal_plan.v1",
            "adr": "0192",
            "dry_run": True,
            "mutation": False,
            "auto_mutate_rules": False,
            "status": "degraded",
            "error": f"{type(e).__name__}: {e}"[:240],
            "proposals": [],
            "task_actions": [],
        }
