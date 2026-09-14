#!/usr/bin/env python3
"""Scene MetaOS Gate — DecisionGate integration for scene lifecycle decisions.

Uses MetaOS's DecisionGate (GREEN/YELLOW/RED) to evaluate scene promotion,
demotion, and execution decisions.

Usage:
  python3 bin/ssot/scene-metasos-gate.py evaluate <scene_id> --action promote|demote|execute
  python3 bin/ssot/scene-metasos-gate.py batch-evaluate
  python3 bin/ssot/scene-metasos-gate.py status
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"


def _load_calibration_engine():
    spec = importlib.util.spec_from_file_location(
        "calibration_engine", str(ROOT / "bin" / "ssot" / "calibration-engine.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


# ── Decision Gate (GREEN/YELLOW/RED) ────────────────────────────────

GATE_RULES = {
    "promote": {
        "green": {"min_calibration": 0.7, "min_samples": 30, "max_fp_rate": 0.10},
        "yellow": {"min_calibration": 0.6, "min_samples": 15, "max_fp_rate": 0.15},
        "red": {"min_calibration": 0.0, "min_samples": 0, "max_fp_rate": 1.0},
    },
    "demote": {
        "green": {"max_calibration": 0.4, "max_samples": 1000},  # Always demote if bad
        "yellow": {"max_calibration": 0.55, "max_samples": 1000},
        "red": {"max_calibration": 1.0, "max_samples": 1000},  # Never demote if good
    },
    "execute": {
        "green": {"min_activation": ["active", "allowed"]},
        "yellow": {"min_activation": ["controlled"]},
        "red": {"min_activation": []},
    },
}


def evaluate_gate(action: str, scene_id: str, cal: dict[str, Any],
                  scene: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a scene decision using traffic-light gate."""
    rules = GATE_RULES.get(action, {})
    if not rules:
        return {"gate": "RED", "reason": f"Unknown action: {action}"}

    if action == "promote":
        green = rules["green"]
        yellow = rules["yellow"]

        score = cal.get("calibration_score", 0)
        samples = cal.get("sample_count", 0)
        fp_rate = cal.get("false_positive_rate", 1.0)

        if score >= green["min_calibration"] and samples >= green["min_samples"] and fp_rate <= green["max_fp_rate"]:
            gate = "GREEN"
            reason = f"calibration={score:.3f} >= {green['min_calibration']}, samples={samples} >= {green['min_samples']}, fp={fp_rate:.3f} <= {green['max_fp_rate']}"
        elif score >= yellow["min_calibration"] and samples >= yellow["min_samples"] and fp_rate <= yellow["max_fp_rate"]:
            gate = "YELLOW"
            reason = f"calibration={score:.3f} meets YELLOW threshold, needs human confirmation"
        else:
            gate = "RED"
            reason = f"calibration={score:.3f} < {yellow['min_calibration']} or samples={samples} < {yellow['min_samples']}"

    elif action == "demote":
        green = rules["green"]
        yellow = rules["yellow"]
        score = cal.get("calibration_score", 1.0)
        fp_rate = cal.get("false_positive_rate", 0.0)

        if score <= green["max_calibration"] or fp_rate > 0.2:
            gate = "GREEN"
            reason = f"calibration={score:.3f} <= {green['max_calibration']} or fp_rate={fp_rate:.3f} > 0.2 — clear demotion signal"
        elif score <= yellow["max_calibration"]:
            gate = "YELLOW"
            reason = f"calibration={score:.3f} <= {yellow['max_calibration']} — needs human confirmation"
        else:
            gate = "RED"
            reason = f"calibration={score:.3f} > {yellow['max_calibration']} — no demotion needed"

    elif action == "execute":
        activation = scene.get("activation", "preview")
        green_acts = rules["green"]["min_activation"]
        yellow_acts = rules["yellow"]["min_activation"]

        if activation in green_acts:
            gate = "GREEN"
            reason = f"activation={activation} allows auto-execute"
        elif activation in yellow_acts:
            gate = "YELLOW"
            reason = f"activation={activation} requires human confirmation"
        else:
            gate = "RED"
            reason = f"activation={activation} blocks execution"

    else:
        gate = "RED"
        reason = f"Unknown action: {action}"

    return {
        "gate": gate,
        "action": action,
        "scene_id": scene_id,
        "reason": reason,
        "calibration": {
            "score": cal.get("calibration_score", 0),
            "samples": cal.get("sample_count", 0),
            "fp_rate": cal.get("false_positive_rate", 0),
        },
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def evaluate(scene_id: str, action: str) -> dict[str, Any]:
    """Evaluate a scene decision."""
    scene = _load_scene(scene_id)
    if not scene:
        return {"gate": "RED", "reason": f"Scene not found: {scene_id}"}

    cal_mod = _load_calibration_engine()
    cal = cal_mod.compute_calibration(scene_id)
    return evaluate_gate(action, scene_id, cal, scene)


def batch_evaluate() -> list[dict[str, Any]]:
    """Evaluate all scenes for promote/demote/execute."""
    import yaml
    cal_mod = _load_calibration_engine()
    results = []

    if not SCENES_DIR.is_dir():
        return results

    for p in sorted(SCENES_DIR.glob("*.yaml")):
        try:
            with open(p, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            scene = docs[-1] if len(docs) > 1 else docs[0]
            if not isinstance(scene, dict):
                continue

            scene_id = scene.get("scene_id", p.stem)
            lifecycle = scene.get("lifecycle", "draft")
            cal = cal_mod.compute_calibration(scene_id)

            # Only check promotion for scenes below routine
            if lifecycle in ("draft", "shadow", "assisted", "supervised"):
                results.append(evaluate_gate("promote", scene_id, cal, scene))

            # Only check demotion for scenes above draft
            if lifecycle in ("shadow", "assisted", "supervised", "routine"):
                results.append(evaluate_gate("demote", scene_id, cal, scene))

        except Exception as e:
            print(f"  WARN: {p.name}: {e}", file=sys.stderr)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    ep = sub.add_parser("evaluate", help="Evaluate a scene decision")
    ep.add_argument("scene_id")
    ep.add_argument("--action", required=True, choices=["promote", "demote", "execute"])

    sub.add_parser("batch-evaluate", help="Evaluate all scenes")
    sub.add_parser("status", help="Show gate summary")

    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "evaluate":
        result = evaluate(args.scene_id, args.action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["gate"] == "GREEN" else (1 if result["gate"] == "YELLOW" else 2)

    if command == "batch-evaluate":
        results = batch_evaluate()
        green = sum(1 for r in results if r["gate"] == "GREEN")
        yellow = sum(1 for r in results if r["gate"] == "YELLOW")
        red = sum(1 for r in results if r["gate"] == "RED")
        print(f"Gate evaluation: {green} GREEN, {yellow} YELLOW, {red} RED")
        for r in results:
            if r["gate"] in ("GREEN", "YELLOW"):
                print(f"  [{r['gate']}] {r['action']}:{r['scene_id']} — {r['reason'][:60]}")
        return 0

    # status
    results = batch_evaluate()
    green = [r for r in results if r["gate"] == "GREEN"]
    yellow = [r for r in results if r["gate"] == "YELLOW"]
    print(f"GREEN (auto): {len(green)}")
    print(f"YELLOW (needs human): {len(yellow)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
