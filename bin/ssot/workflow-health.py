#!/usr/bin/env python3
"""Workflow health monitor (ADR-0386 G19): scan .github/workflows/ for
structural issues in the CI plane.

Checks:
1. stale-regex: on: [push, pull_request] pattern still present (should
   have been removed in ADR-0379 E-4)
2. unpathed-pr: workflows trigger on PR without paths filter (not
   governance gate, not callable, not scheduled-only) — potentially
   over-triggered
3. high-continue-on-error: >50% continue-on-error steps — indicates
   over-tolerance
4. idle-workflow: only workflow_dispatch trigger (never auto-runs)

Output: --json for healthcheck; human table otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def scan_workflows() -> list[dict]:
    results = []
    for f in sorted(WORKFLOW_DIR.glob("*.yml")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        name = f.name

        triggers = set()
        if "workflow_call" in text:
            triggers.add("callable")
        if re.search(r"^\s+schedule:\s*$", text, re.M) or "schedule:" in text:
            triggers.add("scheduled")
        if "workflow_dispatch" in text:
            triggers.add("manual")
        has_list = "on: [push, pull_request]" in text or "on: [push,pull_request]" in text
        has_push = bool(re.search(r"^\s+push:\s*$", text, re.M))
        has_pp = bool(re.search(r"^\s+pull_request:\s*$", text, re.M))
        if has_list:
            triggers.update(["push", "per_pr"])
        else:
            if has_push:
                triggers.add("push")
            if has_pp:
                triggers.add("per_pr")
        path_filtered = bool(re.search(r"^\s+paths:\s*$", text, re.M))
        coe_count = text.count("continue-on-error: true")
        total_steps = text.count("run:")

        issues = []
        if has_list:
            issues.append("stale-regex: on: [push,pull_request] pattern should have been removed in E-4")
        if "per_pr" in triggers and not path_filtered and "callable" not in triggers:
            issues.append("unpathed-pr: PR workflow without paths filter")
        if total_steps > 0 and coe_count / total_steps > 0.5:
            issues.append(f"high-continue-on-error: {coe_count}/{total_steps} steps ({coe_count/total_steps:.0%})")
        if triggers == {"manual"}:
            issues.append("idle-workflow: only workflow_dispatch, never auto-runs")

        results.append({
            "file": name,
            "triggers": sorted(triggers),
            "path_filtered": path_filtered,
            "continue_on_error": coe_count,
            "total_steps": total_steps,
            "issues": issues,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    results = scan_workflows()
    total_issues = sum(len(r["issues"]) for r in results)
    if args.json:
        print(json.dumps({"workflows": len(results), "total_issues": total_issues, "data": results}, ensure_ascii=False, indent=2))
        return 1 if total_issues > 0 else 0
    print(f"scanned {len(results)} workflows; {total_issues} issues found\n")
    for r in results:
        if r["issues"]:
            print(f"❌ {r['file']}")
            for issue in r["issues"]:
                print(f"   {issue}")
    if not total_issues:
        print("✅ all clean")
    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
