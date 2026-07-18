#!/usr/bin/env python3
"""Run all G-DEL execution-surface measurement harnesses; emit JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# allow running as script from bin/delivery
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scheduler import measure_schedule_success_rate  # noqa: E402
from role_collab import measure_collab_completion_rate  # noqa: E402
from state_sync import measure_sync_latency  # noqa: E402
from emergence import measure_emergence_accuracy  # noqa: E402


def main() -> int:
    report = {
        "schema": "g-del-execution-metrics/v1",
        "g_del_1": measure_schedule_success_rate(n_nodes=4, agents_per_node=3, n_tasks=1000),
        "g_del_2b": measure_collab_completion_rate(n_runs=200),
        "g_del_3": measure_sync_latency(n_nodes=4, n_ops=500),
        "g_del_5b": measure_emergence_accuracy(),
    }
    report["all_gates_pass"] = all(
        report[k].get("meets_gate") for k in ("g_del_1", "g_del_2b", "g_del_3", "g_del_5b")
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
