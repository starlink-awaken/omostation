#!/usr/bin/env python3
"""Run all G-DEL execution-surface measurement harnesses; emit JSON.

Default harness is in-process multi-node simulation (ADR-0225).
Official G-DEL.1/3 meets_gate requires physical_multi_host — sim cannot pass it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# allow running as script from bin/delivery
sys.path.insert(0, str(Path(__file__).resolve().parent))

from caliber import ENV_CLASS_SIM  # noqa: E402
from scheduler import measure_schedule_success_rate  # noqa: E402
from role_collab import measure_collab_completion_rate  # noqa: E402
from state_sync import measure_sync_latency  # noqa: E402
from emergence import measure_emergence_accuracy  # noqa: E402
from role_memory import measure_role_memory_share  # noqa: E402


def main() -> int:
    report = {
        "schema": "g-del-execution-metrics/v3",
        "env_class": ENV_CLASS_SIM,
        "caliber_adr": ["0210", "0225", "0226"],
        "note": (
            "Default measure_all is in-process simulation. "
            "G-DEL.1 is BLOCKED until 4 physical hosts (ADR-0226). "
            "G-DEL.3 official pass requires physical multi-host measure_physical."
        ),
        "g_del_1": measure_schedule_success_rate(n_nodes=4, agents_per_node=3, n_tasks=1000),
        "g_del_2b": measure_collab_completion_rate(n_runs=200),
        "g_del_3": measure_sync_latency(n_nodes=4, n_ops=500),
        "g_del_4": measure_role_memory_share(),
        "g_del_5b": measure_emergence_accuracy(),
    }
    # Force G-DEL.1 sim stamp to reflect BLOCKED (cannot official-pass with 0 hosts)
    g1 = report["g_del_1"]
    g1["gate_status"] = "BLOCKED"
    g1["blocked_reason"] = (
        "sim harness only; reachable_physical_hosts known < 4 (ADR-0226 fail-closed)"
    )
    g1["min_physical_hosts"] = 4

    physical_keys = ("g_del_1", "g_del_3")
    local_keys = ("g_del_2b", "g_del_4", "g_del_5b")
    report["all_sim_harness_pass"] = all(
        report[k].get("meets_sim_harness")
        for k in ("g_del_1", "g_del_2b", "g_del_3", "g_del_4", "g_del_5b")
    )
    report["all_physical_gates_pass"] = all(
        report[k].get("meets_physical_gate") for k in physical_keys
    )
    report["all_local_gates_pass"] = all(report[k].get("meets_gate") for k in local_keys)
    report["all_gates_pass"] = (
        report["all_physical_gates_pass"] and report["all_local_gates_pass"]
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["all_sim_harness_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
