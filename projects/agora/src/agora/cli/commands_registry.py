"""Registry CRUD commands: register, unregister, list, search, info, stats, config, health."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime

from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_register(args):
    """Register a service."""
    from agora.core.service_base import Service, parse_protocol_config, parse_tags  # type: ignore[import-not-found]

    registry = get_registry()

    # Governance gate: require --governance unless --no-governance is explicitly set
    if not getattr(args, "governance", False) and not getattr(args, "no_governance", False):
        print("ERROR: Registration rejected \u2014 no governance attestation.", file=__import__("sys").stderr)
        print("  Use --governance (from agora-register-node) for governed registration.", file=__import__("sys").stderr)
        print("  Use --no-governance for emergency/admin bypass only.", file=__import__("sys").stderr)
        return 1

    if args.name == "eidos" and args.mcp is None:
        from agora.pipelines.eidos_pipeline import EIDOS_PIPELINE_SERVICE  # type: ignore[import-not-found]

        print(f"Registering {EIDOS_PIPELINE_SERVICE['name']}...")
        print(f"Capabilities: {EIDOS_PIPELINE_SERVICE['capabilities']}")
        print("Done")
        return 0

    proto_cfg, err = parse_protocol_config(args.protocol_config)
    if err:
        print(f"Error: --protocol-config is not valid JSON: {err}")
        return
    if args.proto:
        proto_cfg["proto_path"] = args.proto
    if args.rest_method is not None:
        proto_cfg["method"] = args.rest_method
    elif "method" not in proto_cfg:
        proto_cfg["method"] = "GET"
    svc = Service(
        name=args.name,
        protocol=args.protocol,
        protocol_config=proto_cfg,
        mcp_endpoint=args.mcp,
        health_endpoint=args.health,
        port=args.port,
        tags=parse_tags(args.tags),
    )
    svc.has_auth = args.has_auth
    svc.has_push_notifications = args.has_push_notifications
    svc.has_state_transitions = args.has_state_transitions
    if args.provider_info:
        try:
            svc.provider_info = json.loads(args.provider_info)
        except json.JSONDecodeError:
            svc.provider_info = {"raw": args.provider_info}
    if args.documentation_url:
        svc.documentation_url = args.documentation_url
    registry.register(svc)
    print(f"Registered: {args.name} (protocol: {args.protocol})")


def cmd_unregister(args):
    """Unregister a service."""
    registry = get_registry()
    registry.unregister(args.name)
    print(f"Unregistered: {args.name}")


def cmd_list(_args):
    """List all services as JSON."""
    registry = get_registry()
    print(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2))


def cmd_search(args):
    """Search services by keyword."""
    registry = get_registry()
    keyword = args.keyword.lower()
    matches = [
        s
        for s in registry.list_all()
        if keyword in s.name.lower() or keyword in s.description.lower() or any(keyword in t.lower() for t in s.tags)
    ]

    if args.json:
        print(json.dumps([s.__dict__ for s in matches], ensure_ascii=False, indent=2, default=str))
    else:
        print(f"'{args.keyword}' -> {len(matches)} results:\n")
        for s in matches:
            print(f"  {s.name}")
            if s.description:
                print(f"     {s.description}")
            if s.tags:
                print(f"     tags: {', '.join(s.tags)}")
            print(f"     status: {'healthy' if s.is_available else 'offline'}")
            print()
    return 0


def cmd_info(args):
    """Show detailed service info."""
    registry = get_registry()
    svc = registry.get(args.name)
    if not svc:
        print(f"Service '{args.name}' not found. Use 'agora list' to see all services.")
        return 1

    if args.json:
        info = {
            "name": svc.name,
            "description": svc.description,
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
            "tags": svc.tags,
            "is_available": svc.is_available,
            "circuit_state": svc.circuit_state,
            "failure_count": svc.failure_count,
            "last_health_check": svc.last_health_check,
        }
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        status = "healthy" if svc.is_available else "offline"
        circuit = svc.circuit_state
        print(f"  {svc.name}  [{status}]  Circuit: {circuit}")
        print(f"   Description:    {svc.description or 'N/A'}")
        print(f"   MCP Endpoint:   {svc.mcp_endpoint or 'N/A'}")
        print(f"   Health:         {svc.health_endpoint or 'N/A'}")
        print(f"   Port:           {svc.port or 'N/A'}")
        print(f"   Tags:           {', '.join(svc.tags) if svc.tags else 'N/A'}")
        print(f"   Failures:       {svc.failure_count}/3")
        print(f"   Last Check:     {svc.last_health_check or 'never'}")
    return 0


def cmd_stats(_args):
    """Show service statistics."""
    registry = get_registry()
    all_svc = registry.list_all()
    healthy = registry.list_healthy()

    print("Agora Service Statistics\n")
    print(f"   Total services:     {len(all_svc)}")
    print(f"   Healthy:            {len(healthy)}")
    print(f"   Degraded/Offline:   {len(all_svc) - len(healthy)}")
    print(f"   Health check rate:  {len(healthy) / max(len(all_svc), 1) * 100:.1f}%")
    print()

    if all_svc:
        print("   Per-service status:")
        for s in all_svc:
            bar = "#" * 10 if s.is_available else "-" * 10
            print(f"     [{bar}] {s.name:20s} | tags: {', '.join(s.tags) if s.tags else '-'}")
    return 0


def cmd_config(_args):
    """Show config paths and status."""
    registry = get_registry()
    print(f"Services file:   {registry._storage_path}")
    print(f"Registered:      {len(registry.list_all())} services")
    print(f"Healthy:         {len(registry.list_healthy())}")
    print("Events file:     agora-events.json")
    print("Trace file:      trace_log.jsonl")
    print("Dashboard:       http://localhost:7430")
    print("Metrics:         http://localhost:7430/metrics")


def _check_proxy_services() -> dict:
    """Check MCP proxy services from agora-proxy-services.json.

    Returns a dict with available/unavailable service status.
    Does not spawn subprocesses—only checks command availability.
    """
    import os
    from pathlib import Path

    proxy_path = Path(__file__).resolve().parent.parent.parent.parent / "agora-proxy-services.json"
    if not proxy_path.exists():
        return {"error": "agora-proxy-services.json not found", "services": [], "count": 0}

    try:
        with open(proxy_path) as f:
            import json

            services = json.load(f).get("services", [])
    except Exception as e:
        return {"error": str(e), "services": [], "count": 0}

    results = []
    for svc in services:
        cmd = svc.get("command", "")
        svc.get("cwd", "")
        name = svc.get("name", "?")
        desc = svc.get("description", "")[:60]

        # Check if command exists
        cmd_path = cmd if cmd.startswith("/") else shutil.which(cmd) or ""
        if cmd_path and os.path.exists(cmd_path):
            available = True
        elif cmd == "npx":
            available = bool(shutil.which("npx"))
        else:
            available = False

        results.append(
            {
                "name": name,
                "description": desc,
                "available": available,
                "command": cmd,
                "tool_count": int(svc.get("tool_count", 0)),
            }
        )

    available = [s for s in results if s["available"]]
    unavailable = [s for s in results if not s["available"]]
    return {
        "services": results,
        "count": len(results),
        "available_count": len(available),
        "unavailable_count": len(unavailable),
        "available": available,
        "unavailable": unavailable,
    }


def _format_proxy_health(proxy: dict) -> list[str]:
    """Format proxy service status as display lines."""
    if "error" in proxy:
        return [f"  ⚠️  {proxy['error']}"]
    lines = [
        "",
        "  MCP Proxy Services:",
        f"     Available:   {proxy['available_count']}/{proxy['count']}",
    ]
    if proxy.get("unavailable"):
        lines.append(f"     Unavailable: {proxy['unavailable_count']}/{proxy['count']}")
        for s in proxy["unavailable"]:
            lines.append(f"       ❌ {s['name']:20s}  cmd not found: {s['command']}")
    return lines


def _get_system_metrics() -> dict:
    """Collect system health metrics (CPU, memory, disk)."""
    metrics = {}
    try:
        import psutil

        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        metrics["memory"] = {
            "percent": psutil.virtual_memory().percent,
            "available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        }
        metrics["disk"] = {
            "percent": psutil.disk_usage("/").percent,
            "free_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
            "total_gb": round(psutil.disk_usage("/").total / (1024**3), 1),
        }
        metrics["load_avg"] = [round(l, 2) for l in psutil.getloadavg()]  # noqa: E741
    except ImportError:
        metrics["error"] = "psutil not installed — system metrics unavailable"
    except Exception as e:
        metrics["error"] = str(e)
    return metrics


def _format_system_metrics(metrics: dict) -> list[str]:
    """Format system metrics as display lines."""
    if "error" in metrics:
        return [f"  ⚠️  {metrics['error']}"]
    lines = [
        "",
        "  System Health:",
        f"     CPU:       {metrics.get('cpu_percent', '?'):>5.1f}%",
    ]
    mem = metrics.get("memory", {})
    if mem:
        lines.append(
            f"     Memory:    {mem.get('percent', '?'):>5.1f}%  ({mem.get('available_gb', '?')}G / {mem.get('total_gb', '?')}G free)"
        )
    disk = metrics.get("disk", {})
    if disk:
        lines.append(
            f"     Disk:      {disk.get('percent', '?'):>5.1f}%  ({disk.get('free_gb', '?')}G / {disk.get('total_gb', '?')}G free)"
        )
    load = metrics.get("load_avg")
    if load:
        lines.append(f"     Load Avg:  {load[0]:>5.2f}  {load[1]:>5.2f}  {load[2]:>5.2f}")
    return lines


def cmd_health(args):
    """Probe all services health."""
    registry = get_registry()

    async def _check() -> tuple[list[dict], dict, dict]:
        await registry.health_check_all()
        return registry.to_dict(), _get_system_metrics(), _check_proxy_services()

    def _format_health(services: list[dict], sys_metrics: dict, proxy_services: dict, json_output: bool = False) -> str:
        if json_output:
            return json.dumps(
                {
                    "services": services,
                    "count": len(services),
                    "system": sys_metrics,
                },
                indent=2,
                ensure_ascii=False,
            )

        healthy = [s for s in services if s.get("healthy")]
        unhealthy = [s for s in services if not s.get("healthy")]
        lines = [
            "=" * 60,
            "Health Check Report",
            "=" * 60,
            f"Healthy:   {len(healthy)}/{len(services)}",
            f"Unhealthy: {len(unhealthy)}/{len(services)}",
            "",
        ]
        if healthy:
            lines.append("  Healthy services:")
            for s in healthy:
                ep = s.get("endpoint", "") or f"port {s.get('port', '?')}"
                lines.append(f"     {s['name']:20s}  {ep}")
        if unhealthy:
            lines.append("  Unhealthy services:")
            for s in unhealthy:
                ep = s.get("endpoint", "") or f"port {s.get('port', '?')}"
                lines.append(f"     {s['name']:20s}  {ep}")
        lines.append("")
        lines.append("-" * 60)
        lines.extend(_format_system_metrics(sys_metrics))
        lines.extend(_format_proxy_health(proxy_services))
        lines.extend(
            [
                "",
                "=" * 60,
                "Next check: agora health --watch",
            ]
        )
        return "\n".join(lines)

    if args.watch:
        print(f"Health watch started (interval: {args.interval}s). Ctrl+C to stop.\n")
        try:
            while True:
                services, sys_metrics, proxy_services = asyncio.run(_check())
                timestamp = datetime.now().strftime("%H:%M:%S")
                if args.json:
                    print(
                        json.dumps(
                            {
                                "timestamp": timestamp,
                                "services": services,
                                "system": sys_metrics,
                                "proxy_services": proxy_services,
                            },
                            indent=2,
                            default=str,
                            ensure_ascii=False,
                        )
                    )
                else:
                    healthy_count = sum(1 for s in services if s.get("healthy"))
                    print(f"[{timestamp}] Healthy: {healthy_count}/{len(services)}")
                import time as _time

                _time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nHealth watch stopped.")
    else:
        services, sys_metrics, proxy_services = asyncio.run(_check())
        print(_format_health(services, sys_metrics, proxy_services, args.json))
