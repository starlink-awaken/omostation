"""Registry CRUD commands: register, unregister, list, search, info, stats, config, health."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime

from agora.cli.output import OutputFormatter
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
        print(f"Error: --protocol-config is not valid JSON: {err}", file=__import__("sys").stderr)
        return 1
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


def cmd_list(args):
    """List all services in tabular format (--json for JSON output)."""
    registry = get_registry()
    services = registry.list_all()
    out = OutputFormatter(json_mode=getattr(args, 'json', False))

    if not services:
        out.print_info("No services registered.")
        return 0

    rows = [
        [
            s.name,
            s.protocol,
            "[success]healthy[/]" if s.is_available else "[error]offline[/]",
            s.mcp_endpoint or "-",
            str(s.port) if s.port else "-",
            ", ".join(s.tags[:3]) if s.tags else "-",
        ]
        for s in services
    ]
    out.print_table(
        ["Name", "Protocol", "Status", "Endpoint", "Port", "Tags"],
        rows,
        title=f"Registered Services ({len(services)})",
    )
    return 0


def cmd_search(args):
    """Search services by keyword."""
    registry = get_registry()
    keyword = args.keyword.lower()
    matches = [
        s
        for s in registry.list_all()
        if keyword in s.name.lower() or keyword in s.description.lower() or any(keyword in t.lower() for t in s.tags)
    ]
    out = OutputFormatter(json_mode=getattr(args, 'json', False))

    if args.json:
        out.print_json([s.to_dict() for s in matches])
    else:
        if not matches:
            out.print_info(f"No services matching '{args.keyword}'.")
            return 0
        out.print_info(f"'{args.keyword}' -> {len(matches)} results:")
        for s in matches:
            status = "healthy" if s.is_available else "offline"
            out.print_info(f"  {s.name}  [{status}]")
            if s.description:
                out.print_info(f"     {s.description}")
            if s.tags:
                out.print_info(f"     tags: {', '.join(s.tags)}")
            out.print_divider()
    return 0


def cmd_info(args):
    """Show detailed service info."""
    registry = get_registry()
    svc = registry.get(args.name)
    out = OutputFormatter(json_mode=getattr(args, 'json', False))

    if not svc:
        out.print_error(f"Service '{args.name}' not found.", suggestion="Use 'agora list' to see all services.")
        return 1

    info_data = {
        "name": svc.name,
        "description": svc.description or "N/A",
        "status": "healthy" if svc.is_available else "offline",
        "circuit": svc.circuit_state,
        "mcp_endpoint": svc.mcp_endpoint or "N/A",
        "health_endpoint": svc.health_endpoint or "N/A",
        "port": str(svc.port) if svc.port else "N/A",
        "tags": ", ".join(svc.tags) if svc.tags else "N/A",
        "failures": f"{svc.failure_count}/3",
        "last_check": svc.last_health_check or "never",
    }
    out.print_key_value(info_data, f"Service: {svc.name}")
    return 0


def cmd_stats(_args):
    """Show service statistics."""
    registry = get_registry()
    all_svc = registry.list_all()
    healthy = registry.list_healthy()
    total = max(len(all_svc), 1)
    rate = len(healthy) / total

    out = OutputFormatter(json_mode=getattr(_args, 'json', False))

    # Summary panel
    summary = (
        f"  \033[1m总计\033[0m  {len(all_svc)}  |  "
        f"\033[32m健康\033[0m  {len(healthy)}  |  "
        f"\033[31m异常\033[0m  {len(all_svc) - len(healthy)}  |  "
        f"\033[36m健康率\033[0m  {rate * 100:.1f}%"
    )
    out.print_panel(summary, title="服务统计", style="cyan")

    if all_svc:
        rows = []
        for s in all_svc:
            # Color health bar: green >90%, yellow >70%, red <70%
            health_ratio = 1.0 if s.is_available else 0.0
            bar = out.print_health_bar(health_ratio, width=10)
            # Color status
            status = "[green]healthy[/]" if s.is_available else "[red]offline[/]"
            tags = ", ".join(s.tags[:3]) if s.tags else "-"
            rows.append([bar, s.name, status, tags])

        out.print_table(
            ["Health", "Name", "Status", "Tags"],
            rows,
            title="服务详情",
            caption=f"共 {len(all_svc)} 服务"
        )
    return 0


def cmd_config(_args):
    """Show config paths and status."""
    registry = get_registry()
    out = OutputFormatter(json_mode=getattr(_args, 'json', False))
    config_data = {
        "Services file": registry._storage_path,
        "Registered": len(registry.list_all()),
        "Healthy": len(registry.list_healthy()),
        "Events file": "agora-events.json",
        "Trace file": "trace_log.jsonl",
        "Dashboard": os.environ.get("AGORA_DASHBOARD_URL", "http://localhost:7430"),
        "Metrics": os.environ.get("AGORA_METRICS_URL", "http://localhost:7430/metrics"),
    }
    out.print_key_value(config_data, "配置状态")


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


def cmd_health(args):
    """Probe all services health."""
    registry = get_registry()
    out = OutputFormatter(json_mode=getattr(args, 'json', False))

    async def _check() -> tuple[list[dict], dict, dict]:
        await registry.health_check_all()
        return registry.to_dict(), _get_system_metrics(), _check_proxy_services()

    def _print_health(services: list[dict], sys_metrics: dict, proxy_services: dict) -> None:
        healthy = [s for s in services if s.get("healthy")]
        unhealthy = [s for s in services if not s.get("healthy")]

        out.print_header("Health Check Report")
        stats = {
            "Healthy": f"{len(healthy)}/{len(services)}",
            "Unhealthy": f"{len(unhealthy)}/{len(services)}",
        }
        out.print_key_value(stats, "总览")

        if healthy:
            rows = [[s["name"], s.get("endpoint", "") or f"port {s.get('port', '?')}"] for s in healthy]
            out.print_table(["Name", "Endpoint"], rows, title="Healthy Services")

        if unhealthy:
            rows = [[s["name"], s.get("endpoint", "") or f"port {s.get('port', '?')}"] for s in unhealthy]
            out.print_table(["Name", "Endpoint"], rows, title="Unhealthy Services")

        # System metrics
        if "error" not in sys_metrics:
            mem = sys_metrics.get("memory", {})
            disk = sys_metrics.get("disk", {})
            load = sys_metrics.get("load_avg", [])
            sys_data = {
                "CPU": f"{sys_metrics.get('cpu_percent', '?'):.1f}%" if 'cpu_percent' in sys_metrics else "?",
                "Memory": f"{mem.get('percent', '?')}% ({mem.get('available_gb', '?')}G / {mem.get('total_gb', '?')}G free)" if mem else "?",
                "Disk": f"{disk.get('percent', '?')}% ({disk.get('free_gb', '?')}G / {disk.get('total_gb', '?')}G free)" if disk else "?",
                "Load Avg": f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}" if load else "?",
            }
            out.print_key_value(sys_data, "System Health")
        elif not out.json_mode:
            out.print_warning(sys_metrics.get("error", "System metrics unavailable"))

        # Proxy services
        if "error" in proxy_services:
            out.print_warning(proxy_services["error"])
        else:
            proxy_data = {
                "Available": f"{proxy_services['available_count']}/{proxy_services['count']}",
            }
            if proxy_services.get("unavailable"):
                proxy_data["Unavailable"] = f"{proxy_services['unavailable_count']}/{proxy_services['count']}"
            out.print_key_value(proxy_data, "MCP Proxy Services")
            if proxy_services.get("unavailable"):
                rows = [[s["name"], s["command"]] for s in proxy_services["unavailable"]]
                out.print_table(["Service", "Missing Command"], rows, title="Unavailable Proxies")

        out.print_info("Next check: agora health --watch")

    if args.watch:
        out.print_info(f"Health watch started (interval: {args.interval}s). Ctrl+C to stop.")
        try:
            while True:
                services, sys_metrics, proxy_services = asyncio.run(_check())
                timestamp = datetime.now().strftime("%H:%M:%S")
                if args.json:
                    out.print_json({
                        "timestamp": timestamp,
                        "services": services,
                        "system": sys_metrics,
                        "proxy_services": proxy_services,
                    })
                else:
                    healthy_count = sum(1 for s in services if s.get("healthy"))
                    out.print_info(f"[{timestamp}] Healthy: {healthy_count}/{len(services)}")
                import time as _time

                _time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nHealth watch stopped.")
    else:
        services, sys_metrics, proxy_services = asyncio.run(_check())
        _print_health(services, sys_metrics, proxy_services)
