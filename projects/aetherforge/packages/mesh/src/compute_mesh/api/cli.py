"""Mesh CLI — 算力网格命令行入口。

Usage:
    mesh list              List all compute nodes
    mesh status            Node health + load
    mesh topology scan     Network discovery
    mesh health            Run health check on all nodes
    mesh worker list       Worker list (TODO)
    mesh cost              Cost report
    mesh generate <prompt> Generate via best node
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..pool import ComputePool, CostTracker


def _get_pool() -> ComputePool:
    """Create a configured pool singleton (lazy)."""
    # Use module-level cache so the CLI state persists across subcommands
    pool = getattr(_get_pool, "_pool", None)
    if pool is None:
        pool = ComputePool()
        pool.scan()
        _get_pool._pool = pool
    return pool


def cmd_list() -> int:
    """List all nodes in the mesh."""
    pool = _get_pool()
    nodes = pool.registry.get_all()
    if not nodes:
        print("🔮 No compute nodes discovered.")
        return 0

    print(f"🔮 AetherForge Mesh — {len(nodes)} nodes:")
    print(f"{'ID':30s} {'Type':16s} {'Zone':8s} {'Status':8s} {'Load':6s} {'URL'}")
    print("-" * 100)
    for n in sorted(nodes, key=lambda x: (x.network_zone, x.node_id)):
        icon = "🟢" if n.is_online else ("🟡" if n.status.value == "degraded" else "🔴")
        load = f"{n.load_factor:.1f}"
        print(f"{icon} {n.node_id:28s} {n.engine_type.value:16s} {n.network_zone:8s} {n.status.value:8s} {load:6s} {n.base_url}")
    return 0


def cmd_status() -> int:
    """Show mesh health and load summary."""
    pool = _get_pool()
    summary = pool.get_summary()
    report = {
        "total_nodes": summary["total"],
        "online": summary["online"],
        "offline": summary["offline"],
        "zones": summary["zones"],
    }
    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_topology_scan() -> int:
    """Run topology discovery and show results."""
    pool = _get_pool()
    # Force re-scan
    _get_pool._pool = ComputePool()
    new_pool = _get_pool()
    nodes = new_pool.scan()

    print(f"🔍 Topology scan complete — {len(nodes)} nodes discovered:")
    for n in nodes:
        print(f"  {n.node_id:30s} {n.engine_type.value:15s} zone={n.network_zone}")
    return 0


def cmd_health() -> int:
    """Run health checks on all nodes."""
    pool = _get_pool()
    results = pool.health_check_all()
    online = sum(1 for v in results.values() if v)
    print(f"🏥 Health check complete — {online}/{len(results)} online")
    for node_id, is_alive in results.items():
        icon = "🟢" if is_alive else "🔴"
        print(f"  {icon} {node_id}")
    return 0


def cmd_worker_list() -> int:
    """List registered workers."""
    pool = _get_pool()
    from ..worker import WorkerRegistry, TaskDispatcher

    registry = WorkerRegistry()
    dispatcher = TaskDispatcher(pool, registry)
    dispatcher.provision_all(workers_per_node=2)

    workers = registry.get_all()
    if not workers:
        print("👷 No workers registered.")
        return 0

    print(f"👷 AetherForge Workers — {len(workers)} total:")
    stats = registry.get_stats()
    print(f"   Idle: {stats['idle']} | Busy: {stats['busy']} | Error: {stats['error']} | Completed: {stats['total_completed']}")
    print()
    for w in sorted(workers, key=lambda x: x.node_id):
        icon = {"idle": "🟢", "busy": "🟡", "error": "🔴", "draining": "🔵", "terminated": "⚫"}.get(w.status.value, "⚪")
        print(f"  {icon} {w.worker_id:30s} node={w.node_id:20s} status={w.status.value:10s} load={w.current_load:.1f}")
    return 0


def cmd_worker_dispatch(worker_id: str, prompt: str) -> int:
    """Dispatch a generation task to a specific worker."""
    pool = _get_pool()
    from ..worker import WorkerRegistry, TaskDispatcher

    registry = WorkerRegistry()
    dispatcher = TaskDispatcher(pool, registry)

    worker = registry.get(worker_id)
    if not worker:
        print(f"❌ Worker {worker_id} not found.")
        return 1

    result = dispatcher.dispatch(worker.node_id, prompt=prompt)
    if result["success"]:
        print(f"⚡ {worker_id} → {result['model']} ({result['latency_ms']}ms)")
        print(result["content"])
    else:
        print(f"❌ {result['error']}")
        return 1
    return 0


def cmd_cost() -> int:
    """Show cost report."""
    pool = _get_pool()
    tracker = CostTracker(pool.registry)
    report = tracker.get_report()

    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n📁 Log: {report['log_path']}")
    return 0


def cmd_generate(prompt: str) -> int:
    """Generate via the best available compute node."""
    pool = _get_pool()
    best = pool.get_best_node()
    if best is None:
        print("❌ No online compute nodes available.")
        return 1

    print(f"⚡ Routing to best node: {best.node_id} (zone={best.network_zone})")

    # Try the mapped provider first, fallback to gateway auto-detection
    from llm_gateway.detection import create_provider, detect_backends
    from llm_gateway.provider import LLMRequest

    provider_name = best.protocols[0] if best.protocols else ""
    provider = create_provider(provider_name) if provider_name else None

    if not provider or not provider.is_available():
        # Fallback: use whatever gateway can detect
        backends = detect_backends()
        if backends:
            provider = backends[0]
            if best.base_url and hasattr(provider, "base_url"):
                provider.base_url = best.base_url
        else:
            print(f"❌ No available provider for node {best.node_id}.")
            return 1

    from llm_gateway.provider import LLMRequest

    req = LLMRequest(prompt=prompt)
    resp = provider.complete(req)
    print(resp.content)
    if resp.input_tokens:
        print(f"\n[{resp.model}] {resp.input_tokens} in / {resp.output_tokens} out", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mesh", description="AetherForge Mesh CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List compute nodes")
    sub.add_parser("status", help="Health + load summary")
    sub.add_parser("topology-scan", help="Discover nodes via all backends")
    sub.add_parser("health", help="Run health checks")
    sub.add_parser("worker-list", help="List workers")
    wp = sub.add_parser("worker-dispatch", help="Dispatch task to a worker")
    wp.add_argument("worker_id", help="Worker ID")
    wp.add_argument("prompt", help="Prompt text")
    sub.add_parser("cost", help="Cost report")

    gen = sub.add_parser("generate", help="Generate via best node")
    gen.add_argument("prompt", help="Prompt text")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        return cmd_list()
    elif args.cmd == "status":
        return cmd_status()
    elif args.cmd == "topology-scan":
        return cmd_topology_scan()
    elif args.cmd == "health":
        return cmd_health()
    elif args.cmd == "worker-list":
        return cmd_worker_list()
    elif args.cmd == "worker-dispatch":
        return cmd_worker_dispatch(args.worker_id, args.prompt)
    elif args.cmd == "cost":
        return cmd_cost()
    elif args.cmd == "generate":
        return cmd_generate(args.prompt)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
