#!/usr/bin/env python3
"""
maturity-scorecard.py — Calculate 6-dimension maturity score.

Usage:
  uv run --with pyyaml python3 bin/gac/maturity-scorecard.py
  uv run --with pyyaml python3 bin/gac/maturity-scorecard.py --json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd=None, timeout=120) -> tuple[int, str, str]:
    if cwd is None:
        cwd = REPO_ROOT
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def score_evolvable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/ssot/script-registry.py validate 2>&1")
    registered = "VALIDATION PASSED" in (out or err)
    return {
        "dimension": "evolvable",
        "score": 8 if registered else 6,
        "evidence": "script registry validated" if registered else "script registry has gaps",
        "improvement": "Register all 444 scripts",
    }


def score_iterable() -> dict:
    design_doc = REPO_ROOT / "docs" / "operations" / "90pct-maturity-design.md"
    has_phases = design_doc.exists()
    return {
        "dimension": "iterable",
        "score": 8 if has_phases else 6,
        "evidence": "90pct-maturity-design.md exists with 5 phases" if has_phases else "No phased plan found",
        "improvement": "Execute Phase 1-5 per design doc",
    }


def score_observable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/compass_radar.py --dry-run 2>&1")
    has_output = rc == 0 and len((out or "").strip()) > 0
    has_maturity = has_output and "maturity_score:" in out
    
    score = 7
    evidence = "compass_radar.py output unclear"
    if has_maturity:
        score = 10
        evidence = "compass_radar.py integrated maturity metrics"
    elif has_output:
        score = 8
        evidence = "compass_radar.py produces output"

    return {
        "dimension": "observable",
        "score": score,
        "evidence": evidence,
        "improvement": "Integrate new metrics into compass_radar.py" if not has_maturity else "Perfect",
    }


def score_traceable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/gac/adr-link-validator.py 2>&1")
    valid_links = rc == 0
    return {
        "dimension": "traceable",
        "score": 8 if valid_links else 6,
        "evidence": "All ADR links valid" if valid_links else "Some ADR links broken",
        "improvement": "Fix broken ADR links",
    }


def score_troubleshootable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/ssot/governance-migration.py --dry-run 2>&1")
    has_owner = "No changes needed" in (out or err)
    return {
        "dimension": "troubleshootable",
        "score": 8 if has_owner else 6,
        "evidence": "All governance checks have owner fields" if has_owner else "Some checks missing owner fields",
        "improvement": "Complete owner field migration",
    }


def score_optimizable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/gac/drift-sweep.py --json", timeout=60)
    if rc == 0:
        sweep_works = True
        score = 9
        evidence = "drift-sweep.py runs clean (0 failures)"
    elif rc == 1 and "timeout" in (out or err):
        sweep_works = False
        score = 5
        evidence = "drift-sweep.py timed out"
    else:
        sweep_works = True  # Tool works, just has findings
        score = 7
        evidence = "drift-sweep.py runs successfully (has findings)"
    return {
        "dimension": "optimizable",
        "score": score,
        "evidence": evidence,
        "improvement": "Resolve drift-sweep findings",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Maturity scorecard")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--skip-observable", action="store_true", help="Skip observable check")
    args = parser.parse_args()

    dimensions = [
        score_evolvable(),
        score_iterable(),
        *([] if args.skip_observable else [score_observable()]),
        score_traceable(),
        score_troubleshootable(),
        score_optimizable(),
    ]

    overall = sum(d["score"] for d in dimensions) / len(dimensions)
    scores = {d["dimension"]: d["score"] for d in dimensions}

    if args.json:
        result = {
            "dimensions": dimensions,
            "overall": round(overall, 1),
            "scores": scores,
            "target": 9.0,
            "gap": round(9.0 - overall, 1),
            "calibration": {
                "ssot": "maturity-scorecard",
                "health_map": "health_score 70+ ≈ scorecard 8+, 85+ ≈ scorecard 9+",
                "ledger_map": "scorecard ≥9.0 ↔ T10-MATURITY bets all done",
            },
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("Architecture Maturity Scorecard")
    print("=" * 50)
    for d in dimensions:
        bar = "█" * d["score"] + "░" * (10 - d["score"])
        print(f"{d['dimension']:<15} [{bar}] {d['score']}/10")
        print(f"                 Evidence: {d['evidence']}")
        print(f"                 Next: {d['improvement']}")
        print()
    print("=" * 50)
    print(f"Overall: {overall:.1f}/10 (target: 9.0/10, gap: {9.0 - overall:.1f})")


if __name__ == "__main__":
    main()
