#!/usr/bin/env python3
"""Daily governance health monitoring and historical tracking."""

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HISTORY_FILE = WORKSPACE / ".omo/state/governance-health-history.json"
CONVERGENCE_LINT = WORKSPACE / "bin/gac/governance-convergence-lint.py"
SEMANTIC_GATE = WORKSPACE / "bin/gac/governance-semantic-gate.py"


def collect_metrics() -> dict:
    metrics: dict = {"timestamp": datetime.now(UTC).isoformat()}

    try:
        r = subprocess.run(
            [sys.executable, str(CONVERGENCE_LINT), "--json"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=60
        )
        d = json.loads(r.stdout)
        metrics["convergence_errors"] = len(d.get("errors", []))
        metrics["convergence_warnings"] = len(d.get("warnings", []))
    except Exception:
        metrics["convergence_errors"] = -1
        metrics["convergence_warnings"] = -1

    try:
        r = subprocess.run(
            [sys.executable, str(SEMANTIC_GATE), "--json"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=120
        )
        d = json.loads(r.stdout)
        metrics["semantic_ok"] = d.get("ok", False)
        metrics["semantic_blocking"] = d.get("blocking_failures", 0)
    except Exception:
        metrics["semantic_ok"] = False
        metrics["semantic_blocking"] = -1

    metrics["legacy_cr_ids_count"] = _count_legacy_cr_ids()

    return metrics


def _count_legacy_cr_ids() -> int:
    try:
        text = CONVERGENCE_LINT.read_text()
        match = re.search(r"LEGACY_CR_IDS\s*=\s*\{([^}]+)\}", text, re.DOTALL)
        if match:
            return len(re.findall(r'"[^"]+"', match.group(1)))
    except Exception:
        pass
    return -1


def append_history(history_file: Path, metrics: dict) -> None:
    history: list[dict] = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except Exception:
            history = []
    history.append(metrics)
    if len(history) > 90:
        history = history[-90:]
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Governance health monitor")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--history-file", type=Path, default=HISTORY_FILE)
    args = parser.parse_args()

    metrics = collect_metrics()
    append_history(args.history_file, metrics)

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Governance health: {json.dumps(metrics, indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
