#!/usr/bin/env python3
"""scene-calibration-panorama — T7 calibration fallback chain verifier.

Verifies the reconciled fallback chain (SSOT: .omo/standards/scene-card-lifecycle.yaml):
  A. threshold agreement — SSOT demotion floor/samples == cruiser
     _DEMOTE_CALIBRATION == calibration-engine primary demote floor.
  B. human gate intact — engine daily path performs no auto-apply
     (no _auto_transition / subprocess transition call); SSOT human_gate
     section present; cruiser documents proposal-only demote.
  C. consumption proof — scene_calibration / scene_lifecycle_log row counts
     from scene-metrics.db (informational: empty is reported, not failed).

Usage:
    python3 bin/ssot/scene-calibration-panorama.py [--root PATH] [--json]
Exit 0 when A+B pass; C never fails the run.
"""

from __future__ import annotations

import argparse
import ast
import json
import sqlite3
import sys
from pathlib import Path


def _load_ssot(root: Path) -> dict:
    import yaml

    with open(root / ".omo" / "standards" / "scene-card-lifecycle.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def check_threshold_agreement(root: Path) -> dict:
    """A: one demote rule across SSOT / cruiser / engine."""
    ssot = _load_ssot(root)
    demotion = ssot.get("demotion", {})
    ssot_floor = demotion.get("calibration_floor")
    ssot_min = demotion.get("min_samples")

    cruiser_src = root / "projects" / "omo" / "src" / "omo" / "scene" / "cruiser.py"
    cruiser_floor = None
    for node in ast.walk(_parse_ast(cruiser_src)):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_DEMOTE_CALIBRATION" for t in node.targets
        ):
            if isinstance(node.value, ast.Constant):
                cruiser_floor = node.value.value

    engine_src = root / "bin" / "ssot" / "calibration-engine.py"
    engine_floors: list = []
    engine_sample_floors: list = []
    tree = _parse_ast(engine_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "check_demotion_triggers":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Compare) and len(sub.ops) == 1 and len(sub.comparators) == 1:
                    comp = sub.comparators[0]
                    if isinstance(comp, ast.Constant) and isinstance(comp.value, (int, float)):
                        if isinstance(sub.ops[0], ast.Lt):
                            engine_floors.append(comp.value)
                        elif isinstance(sub.ops[0], (ast.GtE, ast.Gt)):
                            engine_sample_floors.append(comp.value)

    primary_floor = 0.5
    floor_ok = ssot_floor == primary_floor == cruiser_floor and primary_floor in engine_floors
    samples_ok = ssot_min == 10 and 10 in engine_sample_floors
    ok = bool(floor_ok and samples_ok)
    return {
        "name": "threshold-agreement",
        "status": "PASS" if ok else "FAIL",
        "detail": {
            "ssot_floor": ssot_floor,
            "ssot_min_samples": ssot_min,
            "cruiser_demote_calibration": cruiser_floor,
            "engine_lt_floors": sorted(set(engine_floors)),
            "engine_sample_floors": sorted(set(engine_sample_floors)),
            "expected": {"floor": primary_floor, "min_samples": 10},
        },
    }


def check_human_gate(root: Path) -> dict:
    """B: no silent auto-apply anywhere on the demote/promote path."""
    engine_text = (root / "bin" / "ssot" / "calibration-engine.py").read_text(encoding="utf-8")
    no_auto_fn = "_auto_transition" not in engine_text
    no_subprocess_transition = "scene-card-lifecycle.py" not in engine_text
    ssot = _load_ssot(root)
    has_gate = isinstance(ssot.get("human_gate"), dict) and bool(ssot["human_gate"].get("principle"))
    cruiser_text = (root / "projects" / "omo" / "src" / "omo" / "scene" / "cruiser.py").read_text(
        encoding="utf-8"
    )
    cruiser_proposal_only = "永不自动" in cruiser_text or "proposal only" in cruiser_text
    ok = bool(no_auto_fn and no_subprocess_transition and has_gate and cruiser_proposal_only)
    return {
        "name": "human-gate",
        "status": "PASS" if ok else "FAIL",
        "detail": {
            "engine_no_auto_transition_fn": no_auto_fn,
            "engine_no_subprocess_transition": no_subprocess_transition,
            "ssot_human_gate_present": has_gate,
            "cruiser_proposal_only_doc": cruiser_proposal_only,
        },
    }


def check_consumption_proof(root: Path) -> dict:
    """C: store rows as proof the chain is evaluable (informational only)."""
    db_path = root / "data" / "scene-metrics.db"
    if not db_path.is_file():
        return {
            "name": "consumption-proof",
            "status": "EMPTY",
            "detail": {"db": str(db_path), "note": "no executions recorded yet — chain wired, awaiting data"},
        }
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cal_n = (
            conn.execute("SELECT COUNT(*) FROM scene_calibration").fetchone()[0]
            if "scene_calibration" in tables
            else 0
        )
        log_n = (
            conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log").fetchone()[0]
            if "scene_lifecycle_log" in tables
            else 0
        )
        proposal_n = (
            conn.execute(
                "SELECT COUNT(*) FROM scene_lifecycle_log WHERE reason LIKE '%needs_human%'"
                " OR reason LIKE '%propos%'"
            ).fetchone()[0]
            if "scene_lifecycle_log" in tables
            else 0
        )
        conn.close()
    except Exception as exc:
        return {"name": "consumption-proof", "status": "ERROR", "detail": {"error": str(exc)}}
    status = "PRESENT" if (cal_n or log_n) else "EMPTY"
    return {
        "name": "consumption-proof",
        "status": status,
        "detail": {
            "db": str(db_path),
            "scene_calibration_rows": cal_n,
            "scene_lifecycle_log_rows": log_n,
            "human_gate_proposal_rows": proposal_n,
        },
    }


def run_all(root: Path) -> dict:
    checks = [
        check_threshold_agreement(root),
        check_human_gate(root),
        check_consumption_proof(root),
    ]
    hard = [c for c in checks if c["name"] != "consumption-proof"]
    overall = "PASS" if all(c["status"] == "PASS" for c in hard) else "FAIL"
    return {"overall": overall, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = run_all(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Scene Calibration Panorama: {result['overall']}")
        for c in result["checks"]:
            icon = "✅" if c["status"] in ("PASS", "PRESENT") else ("▫️" if c["status"] == "EMPTY" else "❌")
            print(f"  {icon} {c['name']}: {c['status']}")
            for k, v in c.get("detail", {}).items():
                print(f"      {k}={v}")
    return 0 if result["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
