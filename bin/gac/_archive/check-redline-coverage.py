#!/usr/bin/env python3
"""check-redline-coverage: validate the redline registry itself.

Scans `.omo/_truth/registry/redlines.yaml` and enforces:

  - any `enforced_red_lines` entry with `severity: highest` must have
    a non-empty `executor` script that exists on disk.
  - any `acknowledged_gaps` entry with `severity: highest` is
    immediately a problem: the whole point of the registry is
    that no red line of constitutional severity is allowed to live
    in the "gap" column. A warning fires, and the report is tagged
    so the dashboard can surface it.

Output:
  - exit 0 = registry clean
  - exit 1 = some row violates the contract
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REDLINES = WORKSPACE / ".omo" / "_truth" / "registry" / "redlines.yaml"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not REDLINES.is_file():
        if args.json:
            print(json.dumps({"ok": False, "reason": "redlines.yaml not found"}))
        else:
            print("check-redline-coverage: FAIL (redlines.yaml missing)")
        return 1

    data = yaml.safe_load(REDLINES.read_text(encoding="utf-8")) or {}
    enforced = data.get("enforced_red_lines") or []
    gaps = data.get("acknowledged_gaps") or []

    findings: list[dict] = []
    summary = {
        "enforced_total": len(enforced),
        "enforced_highest": 0,
        "gap_total": len(gaps),
        "gap_highest": 0,
    }

    for row in enforced:
        if row.get("severity") != "highest":
            continue
        summary["enforced_highest"] += 1
        executor = (row.get("executor") or "").strip()
        if not executor:
            findings.append({
                "kind": "highest_without_executor",
                "id": row.get("id"),
                "message": "highest-severity red line has no executor script",
            })
            continue
        # executor is a relative path; resolve against the workspace.
        exe_path = WORKSPACE / executor
        if not exe_path.is_file():
            findings.append({
                "kind": "executor_missing",
                "id": row.get("id"),
                "executor": executor,
                "message": f"executor script {executor!r} does not exist",
            })

    for row in gaps:
        if row.get("severity") != "highest":
            continue
        summary["gap_highest"] += 1
        findings.append({
            "kind": "highest_left_unenforced",
            "id": row.get("id"),
            "gap_reason": row.get("gap_reason"),
            "message": "highest-severity line is in the gap column — register an executor",
        })

    ok = not findings
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-redline-coverage: {'PASS' if ok else 'FAIL'}")
        print(
            f"  enforced={summary['enforced_total']} "
            f"(highest={summary['enforced_highest']}) "
            f"gaps={summary['gap_total']} "
            f"(highest={summary['gap_highest']})"
        )
        for f in findings:
            print(f"  - {f.get('id', '?')}: {f.get('kind', '?')}: {f.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
