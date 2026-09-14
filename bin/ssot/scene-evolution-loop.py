#!/usr/bin/env python3
"""Scene Evolution Loop — calibration-driven scene improvement proposals.

Reads calibration results and generates evolution proposals:
  - Promotion proposals (when gates pass)
  - Demotion proposals (when falsifiers trigger)
  - Optimization proposals (when metrics show room for improvement)

Usage:
  python3 bin/ssot/scene-evolution-loop.py check
  python3 bin/ssot/scene-evolution-loop.py proposals [--limit N]
  python3 bin/ssot/scene-evolution-loop.py execute --proposal-id <id>
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
PROPOSALS_DIR = ROOT / ".omo" / "_knowledge" / "evolution-proposals"
CALIBRATION_DB = ROOT / "data" / "scene-metrics.db"


def _load_scene(scene_id: str) -> dict[str, Any] | None:
    import yaml
    for p in SCENES_DIR.glob("*.yaml"):
        try:
            with open(p, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            body = docs[-1] if len(docs) > 1 else docs[0]
            if isinstance(body, dict) and body.get("scene_id") == scene_id:
                return body
        except Exception:
            continue
    return None


def _load_all_scenes() -> list[dict[str, Any]]:
    import yaml
    scenes = []
    if SCENES_DIR.is_dir():
        for p in sorted(SCENES_DIR.glob("*.yaml")):
            try:
                with open(p, encoding="utf-8") as f:
                    docs = list(yaml.safe_load_all(f))
                body = docs[-1] if len(docs) > 1 else docs[0]
                if isinstance(body, dict):
                    scenes.append(body)
            except Exception:
                continue
    return scenes


def _compute_calibration(scene_id: str, window_days: int = 30) -> dict[str, Any]:
    """Load calibration from calibration-engine (or compute placeholder)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "calibration_engine", str(ROOT / "bin" / "ssot" / "calibration-engine.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compute_calibration(scene_id, window_days)


def _check_promotion(scene_id: str, current_lifecycle: str) -> dict[str, Any] | None:
    """Check if scene is eligible for promotion."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "calibration_engine", str(ROOT / "bin" / "ssot" / "calibration-engine.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    next_levels = {"draft": "shadow", "shadow": "assisted", "assisted": "supervised", "supervised": "routine"}
    target = next_levels.get(current_lifecycle)
    if not target:
        return None

    result = mod.check_promotion_gates(scene_id, target)
    if result.get("eligible"):
        return {
            "type": "promotion",
            "scene_id": scene_id,
            "from": current_lifecycle,
            "to": target,
            "calibration": result.get("calibration", {}),
            "reason": f"All promotion gates passed for {current_lifecycle} → {target}",
        }
    return None


def _check_demotion(scene_id: str, current_lifecycle: str) -> dict[str, Any] | None:
    """Check if scene needs demotion."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "calibration_engine", str(ROOT / "bin" / "ssot" / "calibration-engine.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod.check_demotion_triggers(scene_id)
    if result.get("demote"):
        return {
            "type": "demotion",
            "scene_id": scene_id,
            "from": current_lifecycle,
            "to": "auto",  # Determined by falsifier action
            "triggers": result.get("triggers", []),
            "calibration": result.get("calibration", {}),
            "reason": f"Demotion triggers: {result.get('triggers', [])}",
        }
    return None


def _check_optimization(scene_id: str, cal: dict[str, Any]) -> dict[str, Any] | None:
    """Check if scene has optimization opportunities."""
    suggestions = []

    if cal.get("intervention_rate", 0) > 0.3:
        suggestions.append("High intervention rate — consider adjusting confidence thresholds")
    if cal.get("false_positive_rate", 0) > 0.1:
        suggestions.append("High false positive rate — consider refining classification rules")
    if cal.get("avg_duration_ms", 0) > 5000:
        suggestions.append("Slow execution — consider caching or optimization")
    if cal.get("sample_count", 0) < 10:
        suggestions.append("Insufficient samples — needs more execution data")

    if not suggestions:
        return None

    return {
        "type": "optimization",
        "scene_id": scene_id,
        "suggestions": suggestions,
        "calibration": cal,
        "reason": f"{len(suggestions)} optimization opportunities detected",
    }


def check_all() -> list[dict[str, Any]]:
    """Check all scenes for evolution opportunities."""
    proposals = []
    scenes = _load_all_scenes()

    for scene in scenes:
        scene_id = scene.get("scene_id", "")
        lifecycle = scene.get("lifecycle", "draft")
        if not scene_id:
            continue

        cal = _compute_calibration(scene_id)

        # Check promotion
        promo = _check_promotion(scene_id, lifecycle)
        if promo:
            proposals.append(promo)

        # Check demotion
        demo = _check_demotion(scene_id, lifecycle)
        if demo:
            proposals.append(demo)

        # Check optimization
        if cal.get("sample_count", 0) > 0:
            opt = _check_optimization(scene_id, cal)
            if opt:
                proposals.append(opt)

    return proposals


def save_proposals(proposals: list[dict[str, Any]]) -> int:
    """Save proposals to .omo/_knowledge/evolution-proposals/."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for p in proposals:
        pid = f"prop-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        p["proposal_id"] = pid
        p["created_at"] = datetime.now(UTC).isoformat()
        p["status"] = "pending"

        path = PROPOSALS_DIR / f"{pid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        saved += 1
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Check all scenes for evolution opportunities")
    lp = sub.add_parser("proposals", help="List saved proposals")
    lp.add_argument("--limit", type=int, default=10)

    args = parser.parse_args(argv)
    command = args.command or "check"

    if command == "check":
        proposals = check_all()
        print(f"Evolution proposals: {len(proposals)}")
        for p in proposals:
            print(f"  [{p['type']}] {p['scene_id']}: {p['reason'][:80]}")

        if proposals:
            saved = save_proposals(proposals)
            print(f"\nSaved {saved} proposals to {PROPOSALS_DIR.relative_to(ROOT)}")
        return 0

    if command == "proposals":
        if not PROPOSALS_DIR.is_dir():
            print("No proposals found.")
            return 0
        files = sorted(PROPOSALS_DIR.glob("*.json"), reverse=True)[:args.limit]
        for f in files:
            with open(f) as fh:
                p = json.load(fh)
            print(f"  [{p.get('status','?')}] [{p.get('type','?')}] {p.get('scene_id','?')}: {p.get('reason','')[:60]}")
        print(f"\nShowing {len(files)} proposals")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
