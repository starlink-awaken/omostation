#!/usr/bin/env python3
"""
knowledge-closing-loop.py — Post-fix knowledge capture workflow.

Usage:
  uv run python3 bin/gac/knowledge-closing-loop.py --failure-type <type>
  uv run python3 bin/gac/knowledge-closing-loop.py --json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNBOOK_DIR = REPO_ROOT / "docs" / "operations"


def find_runbook(failure_type: str) -> Path | None:
    mapping = {
        "freshness_expired": "runbook-state-freshness.md",
        "silent_workflow": "runbook-p74-silent-workflow.md",
        "concurrent_write": "runbook-concurrent-write.md",
        "gate_failure": "runbook-gate-failure.md",
        "submodule_drift": "runbook-submodule-drift.md",
        "health_degraded": "runbook-state-freshness.md",
    }
    name = mapping.get(failure_type)
    if name:
        candidate = RUNBOOK_DIR / name
        if candidate.exists():
            return candidate
    return None


def create_draft_runbook(failure_type: str) -> dict:
    timestamp = datetime.now().strftime("%Y-%m-%d")
    runbook_name = f"runbook-{failure_type}.md"
    runbook_path = RUNBOOK_DIR / runbook_name

    if runbook_path.exists():
        return {"action": "update", "runbook": str(runbook_path), "reason": "exists"}

    content = f"""---
title: "{failure_type}"
status: active
type: runbook
owner: governance-team
lifecycle: contract
last-reviewed: "{timestamp}"
---

# Runbook: {failure_type}

## Symptom
- Describe the symptom here

## Diagnostic
```bash
# Add diagnostic commands
```

## Resolution
### Option A: ...
### Option B: ...

## Prevention
- Add prevention steps

## Related
- Add related runbooks
"""

    return {
        "action": "create",
        "runbook": str(runbook_path),
        "content": content,
    }


def check_gate_coverage(failure_type: str) -> dict:
    governance_checks = REPO_ROOT / ".omo" / "_truth" / "registry" "governance-checks.yaml"
    if not governance_checks.exists():
        return {"covered": False, "reason": "governance-checks.yaml not found"}

    text = governance_checks.read_text(errors="ignore")
    if failure_type.lower().replace("_", "-") in text.lower():
        return {"covered": True, "check": failure_type}

    return {"covered": False, "reason": "No gate check found for this failure type"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge closing loop")
    parser.add_argument("--failure-type", required=True, help="Failure type")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    results = []

    # Step 1: Check if runbook exists
    runbook = find_runbook(args.failure_type)
    if runbook:
        results.append({
            "step": "runbook_check",
            "result": "exists",
            "runbook": str(runbook),
            "action": "update with new signal",
        })
    else:
        draft = create_draft_runbook(args.failure_type)
        results.append({
            "step": "runbook_check",
            "result": "missing",
            "action": draft["action"],
            "runbook": draft.get("runbook"),
        })

    # Step 2: Check if gate check exists
    gate = check_gate_coverage(args.failure_type)
    results.append({
        "step": "gate_check",
        "result": "covered" if gate["covered"] else "missing",
        "details": gate,
    })

    # Step 3: Check if recurring pattern
    results.append({
        "step": "recurrence_check",
        "result": "requires_history_analysis",
        "action": "escalate to governance-team if >= 3 occurrences",
    })

    if args.json:
        print(json.dumps({"failure_type": args.failure_type, "steps": results}, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(f"Knowledge Closing Loop: {args.failure_type}")
    print("=" * 50)
    for r in results:
        print(f"[{r['step'].upper()}] {r['result']}")
        for k, v in r.items():
            if k not in ("step", "result"):
                print(f"       {k}: {v}")
    print("=" * 50)


if __name__ == "__main__":
    main()
