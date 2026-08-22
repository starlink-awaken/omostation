#!/usr/bin/env python3
"""check-silent-workflows — gate enforcement for P74 (ADR-0130).

Reads the agent-workflow registry + run ledger, runs the P74 silent-detection
report, and exits non-zero when any workflow is silently healthy. Pairs with
`bin/gac/gac-local-gate.py` as a ci_only check (default mode skips it,
strict/CI mode blocks on warn_count > 0).

Why this exists:
  `agent-workflow compliance` already reports p74_solidification, but the
  output is human-readable text. Without an executable gate, a workflow
  that drifts into "silent healthy" (no recent run, no diff_check coverage)
  only surfaces when an operator manually runs compliance. Wiring the check
  into gac-local-gate --strict makes the regression fail CI.

Exit codes:
  0 = no silent workflows (P74 healthy)
  1 = silent workflows detected (gate blocks)
  2 = registry missing or unreadable (config error, NOT a P74 signal)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_PATH = WORKSPACE / ".omo" / "_truth" / "registry" / "agent-workflows"
EVENTS_PATH = WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
RUNS_DIR = WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "runs"


def _load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _load_runs(runs_dir: Path) -> dict[str, dict]:
    runs: dict[str, dict] = {}
    if not runs_dir.is_dir():
        return runs
    for f in runs_dir.rglob("*.yaml"):
        try:
            import yaml

            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and "run_id" in d:
            runs[str(d["run_id"])] = d
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument(
        "--list-silent", action="store_true", help="Print silent workflow IDs"
    )
    args = parser.parse_args()

    # Defer omo import (only available when projects/omo is on PYTHONPATH or
    # the projects/omo .venv is active). The bin/ wrapper is loaded from
    # bin/agent-workflow.py which already adds the path; we mirror that.
    sys.path.insert(0, str(WORKSPACE / "projects/omo/src"))
    try:
        from omo.workflow.core import load_registry  # type: ignore[import-not-found]
        from omo.workflow.diagnostics import (  # type: ignore[import-not-found]
            p74_solidification_report,
        )
    except ImportError as exc:
        print(f"error: omo.workflow not importable: {exc}", file=sys.stderr)
        return 2

    if not REGISTRY_PATH.is_dir() and not REGISTRY_PATH.is_file():
        print(f"error: registry path missing: {REGISTRY_PATH}", file=sys.stderr)
        return 2

    try:
        registry = load_registry(REGISTRY_PATH)
    except Exception as exc:
        print(f"error: failed to load registry: {exc}", file=sys.stderr)
        return 2

    events = _load_events(EVENTS_PATH)
    runs = _load_runs(RUNS_DIR)
    report = p74_solidification_report(registry, events, runs)

    silent = [w for w in report.get("workflows", []) if w.get("silent_health") == "warn"]
    warn_count = report.get("warn_count", len(silent))
    summary = {
        "registry_workflows": len(report.get("workflows", [])),
        "events_loaded": len(events),
        "runs_loaded": len(runs),
        "warn_count": warn_count,
        "silent_workflows": [w["workflow_id"] for w in silent],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.list_silent:
        for wf_id in summary["silent_workflows"]:
            print(wf_id)
    else:
        print(f"registry: {summary['registry_workflows']} workflows")
        print(f"events:   {summary['events_loaded']}")
        print(f"runs:     {summary['runs_loaded']}")
        print(f"warn_count: {warn_count}")
        if silent:
            print("silent workflows:")
            for wf_id in summary["silent_workflows"]:
                print(f"  - {wf_id}")

    return 1 if warn_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())