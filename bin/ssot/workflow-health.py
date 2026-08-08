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
from pathlib import Path

WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


# 内联 paths: [...] 数组形式 (agora/ecos/kairon 等子项目 CI 常用) 与多行块形式
INLINE_PATHS_RE = re.compile(r"^\s+paths:\s*\[([^\]]*)\]", re.MULTILINE)
BLOCK_PATHS_RE = re.compile(r"^\s+paths:\s*$((?:\n\s+- [^\n]+)*)", re.MULTILINE)

# 已知 continue-on-error 为设计语义 (advisory/收集型, 或 checkout 子模块容错) 的 workflow
COE_DESIGN_EXEMPT = {
    "gac-gate.yml",
    "ai-pr-review.yml",
    "ci-python-coverage.yml",
    "quality.yml",
    "config-check.yml",
    "family-hub-ci.yml",
    "integration.yml",
    "kairon-ci.yml",
    "ci-lint.yml",
}

# 已知 manual-intent 的 workflow (仅 dispatch, 按需运行, 非 idle 死工作流)
MANUAL_INTENT_EXEMPT = {"pyright-sweep.yml"}

# gate/enforce 类 PR workflow 全量跑是设计语义 (低成本规则门禁, paths 过滤反而有漏跑风险)
UNPATHED_DESIGN_EXEMPT = {
    "ai-pr-review.yml",
    "gac-gate.yml",
    "constraint-validation.yml",
    "cross-deps-enforce.yml",
    "debt-audit.yml",
    "evidence-smoke-gate.yml",
    "interfaces-enforce.yml",
    "phase-gate-enforce.yml",
    "port-registry-enforce.yml",
    "state-goals-enforce.yml",
    "task-schema-enforce.yml",
    "workspace.yml",
}


def scan_workflows() -> list[dict]:
    results = []
    for f in sorted(WORKFLOW_DIR.glob("*.yml")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        name = f.name

        triggers = set()
        if "workflow_call" in text:
            triggers.add("callable")
        if re.search(r"^\s+schedule:\s*$", text, re.MULTILINE) or "schedule:" in text:
            triggers.add("scheduled")
        if "workflow_dispatch" in text:
            triggers.add("manual")
        has_list = "on: [push, pull_request]" in text or "on: [push,pull_request]" in text
        has_push = bool(re.search(r"^\s+push:\s*$", text, re.MULTILINE))
        has_pp = bool(re.search(r"^\s+pull_request:\s*$", text, re.MULTILINE))
        if has_list:
            triggers.update(["push", "per_pr"])
        else:
            if has_push:
                triggers.add("push")
            if has_pp:
                triggers.add("per_pr")
        path_filtered = bool(re.search(r"^\s+paths:\s*(\[|$)", text, re.MULTILINE))
        coe_count = text.count("continue-on-error: true")
        total_steps = text.count("run:")

        issues = []
        if has_list:
            issues.append("stale-regex: on: [push,pull_request] pattern should have been removed in E-4")
        if (
            name not in UNPATHED_DESIGN_EXEMPT
            and "per_pr" in triggers
            and not path_filtered
            and "callable" not in triggers
        ):
            issues.append("unpathed-pr: PR workflow without paths filter")
        if (
            name not in COE_DESIGN_EXEMPT
            and total_steps > 0
            and coe_count / total_steps > 0.5
        ):
            issues.append(f"high-continue-on-error: {coe_count}/{total_steps} steps ({coe_count/total_steps:.0%})")
        if triggers == {"manual"} and name not in MANUAL_INTENT_EXEMPT:
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
