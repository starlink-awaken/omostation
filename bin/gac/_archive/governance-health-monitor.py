#!/usr/bin/env python3
"""Governance Health Monitor — daily metrics collector.

Collects governance metrics from existing tools and appends to a JSON history
file for trend analysis. Designed for daily cron execution.

Metrics collected:
  - convergence_errors / convergence_warnings  (from governance-convergence-lint.py)
  - semantic_ok / semantic_blocking            (from governance-semantic-gate.py)
  - legacy_cr_ids_count                        (from governance-convergence-lint.py LEGACY_CR_IDS)

Usage:
  python3 bin/gac/governance-health-monitor.py [--json]
  python3 bin/gac/governance-health-monitor.py --history-file <path>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY_FILE = WORKSPACE / ".omo/state/governance-health-history.json"
MAX_HISTORY_DAYS = 90


def _run_json(script: str, *args: str, timeout: int = 120) -> dict:
    """Run a script and return parsed JSON output."""
    cmd = [sys.executable, str(WORKSPACE / script), *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {}


def collect_metrics() -> dict:
    """Collect governance metrics from existing tools.

    Returns dict with keys:
      - timestamp (ISO 8601)
      - convergence_errors (int)
      - convergence_warnings (int)
      - semantic_ok (bool)
      - semantic_blocking (int)
      - legacy_cr_ids_count (int)
    """
    # Collect convergence lint metrics
    conv_data = _run_json("bin/gac/governance-convergence-lint.py", "--json")
    convergence_errors = len(conv_data.get("errors", []))
    convergence_warnings = len(conv_data.get("warnings", []))

    # Collect semantic gate metrics
    sem_data = _run_json("bin/gac/governance-semantic-gate.py", "--json")
    semantic_ok = sem_data.get("ok", False)
    semantic_blocking = sem_data.get("blocking_failures", 0)

    # Count LEGACY_CR_IDS by importing the module
    legacy_cr_ids_count = _count_legacy_cr_ids()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "convergence_errors": convergence_errors,
        "convergence_warnings": convergence_warnings,
        "semantic_ok": semantic_ok,
        "semantic_blocking": semantic_blocking,
        "legacy_cr_ids_count": legacy_cr_ids_count,
    }


def _count_legacy_cr_ids() -> int:
    """Import LEGACY_CR_IDS from governance-convergence-lint.py and return count."""
    import importlib.util

    script = WORKSPACE / "bin/gac/governance-convergence-lint.py"
    try:
        spec = importlib.util.spec_from_file_location("governance_convergence_lint", script)
        if spec is None or spec.loader is None:
            return 0
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        legacy = getattr(module, "LEGACY_CR_IDS", None)
        if isinstance(legacy, set):
            return len(legacy)
    except Exception:
        pass
    return 0


def append_history(history_file: Path, metrics: dict) -> int:
    """Append metrics to JSON history file, keeping last MAX_HISTORY_DAYS entries.

    The history file stores a JSON array of metric dicts. On append, entries
    older than MAX_HISTORY_DAYS are pruned.

    Returns the new total entry count.
    """
    history: list[dict] = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []

    history.append(metrics)

    # Prune entries older than MAX_HISTORY_DAYS
    cutoff = datetime.now(UTC).isoformat()
    # Keep at most MAX_HISTORY_DAYS entries (simple count-based pruning)
    if len(history) > MAX_HISTORY_DAYS:
        history = history[-MAX_HISTORY_DAYS:]

    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(history)


def main() -> int:
    parser = argparse.ArgumentParser(description="Governance health monitor — daily metrics collector")
    parser.add_argument("--json", action="store_true", help="Output metrics as JSON")
    parser.add_argument(
        "--history-file",
        type=Path,
        default=DEFAULT_HISTORY_FILE,
        help=f"History file path (default: {DEFAULT_HISTORY_FILE})",
    )
    args = parser.parse_args()

    metrics = collect_metrics()
    entry_count = append_history(args.history_file, metrics)

    if args.json:
        print(json.dumps({**metrics, "history_entries": entry_count}, ensure_ascii=False, indent=2))
    else:
        print(f"Governance Health Monitor — {metrics['timestamp']}")
        print(f"  Convergence: {metrics['convergence_errors']} errors, {metrics['convergence_warnings']} warnings")
        print(
            f"  Semantic gate: {'PASS' if metrics['semantic_ok'] else 'FAIL'} ({metrics['semantic_blocking']} blocking)"
        )
        print(f"  Legacy CR IDs: {metrics['legacy_cr_ids_count']}")
        print(f"  History entries: {entry_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
