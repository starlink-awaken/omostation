#!/usr/bin/env python3
"""check-evidence-honest-closure: verify closed agent-workflow runs have evidence.

Scans `.omo/_delivery/agent-workflows/runs/` for YAML files and checks
that each closed run (status: ok or status: closed) has evidence entries.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "runs"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not RUNS_DIR.exists():
        if args.json:
            print(json.dumps({"ok": True, "summary": "no runs directory", "findings": []}))
        else:
            print("check-evidence-honest-closure: PASS (no runs directory)")
        return 0

    run_files = sorted(RUNS_DIR.glob("*.yaml")) + sorted(RUNS_DIR.glob("*.yml"))
    violations = []
    total_evidence = 0
    checked = 0

    for f in run_files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue

        status = data.get("status", "")
        if status not in ("ok", "closed"):
            continue

        checked += 1
        # Check evidence in multiple locations
        evidence = data.get("evidence", []) or []
        closeout = data.get("closeout", {}) or {}
        closeout_evidence = closeout.get("evidence", []) or []
        closeout_paths = closeout.get("evidence_paths", []) or []

        all_evidence = (evidence if isinstance(evidence, list) else []) + \
                       (closeout_evidence if isinstance(closeout_evidence, list) else []) + \
                       (closeout_paths if isinstance(closeout_paths, list) else [])

        if not all_evidence:
            violations.append({"run": f.stem, "path": str(f)})
        else:
            total_evidence += len(all_evidence)

    summary = {
        "runs_checked": checked,
        "violations": len(violations),
        "total_evidence": total_evidence,
    }
    ok = len(violations) == 0

    if args.json:
        print(json.dumps({"ok": ok, "summary": summary, "findings": violations}, indent=2))
    else:
        print(f"check-evidence-honest-closure: {'PASS' if ok else 'FAIL'} ({checked} runs, {len(violations)} violations, {total_evidence} evidence entries)")
        for v in violations:
            print(f"  VIOLATION: {v['run']} has no evidence")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
