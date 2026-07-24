#!/usr/bin/env python3
"""STRAT-P81 Batch1 C3 — failover drill script (dry-run safe, no real hosts).

Strategy: when a node is marked unhealthy, migrate inflight tasks to healthy
nodes via AgentRegistry + TaskScheduler. Ready for physical hosts once restored.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_registry import AgentRegistry  # noqa: E402
from scheduler import Task, TaskScheduler  # noqa: E402


def run_drill(*, dry_run: bool = True, n_nodes: int = 4) -> dict[str, Any]:
    reg = AgentRegistry()
    for i in range(n_nodes):
        reg.register_node(f"node-{i}")
        reg.register_agent(
            node_id=f"node-{i}",
            role_id="implementer",
            agent_id=f"agent-{i}",
            capacity=2,
        )

    # Mark node-0 dead (false-death / pull-cable simulation)
    for a in reg.list_agents():
        if a.node_id == "node-0":
            reg.mark_unhealthy(a.agent_id)

    sched = TaskScheduler(reg)
    results = []
    for i in range(8):
        r = sched.schedule_one(Task(task_id=f"migrate-{i}", role_id="implementer"))
        results.append(
            {
                "task_id": r.task_id,
                "success": r.success,
                "node_id": r.node_id,
                "agent_id": r.agent_id,
                "error": r.error,
            }
        )

    unhealthy = [a.agent_id for a in reg.list_agents() if not a.healthy]
    healthy_nodes = sorted(
        {a.node_id for a in reg.list_agents(healthy_only=True)}
    )
    migrated_ok = all(x["success"] and x["node_id"] != "node-0" for x in results)

    return {
        "ok": migrated_ok,
        "dry_run": dry_run,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_nodes": n_nodes,
        "unhealthy_agents": unhealthy,
        "healthy_nodes": healthy_nodes,
        "tasks": results,
        "migrated_away_from_dead_node": migrated_ok,
        "env_class": "in-process_simulation",
        "meets_sim_harness": migrated_ok,
        "meets_physical_gate": False,
        "meets_gate": False,
        "note": "Physical pull-cable requires restored hosts; dry-run validates strategy only",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--live", action="store_true", help="reserved; still sim until physical")
    p.add_argument("--n-nodes", type=int, default=4)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    report = run_drill(dry_run=not args.live, n_nodes=args.n_nodes)
    if args.json or True:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
