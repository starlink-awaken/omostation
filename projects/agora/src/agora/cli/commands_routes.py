"""Routing and instance commands: route, routes, instance."""

from __future__ import annotations

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter
from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_route(args):
    """Add a tool route."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        router.add_route(args.tool, args.service)
        out.print_success(f"Route added: '{args.tool}' -> '{args.service}'")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_routes(args):
    """List all routes."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        routes = router.list_routes()
        if args.json:
            out.print_json(routes)
        else:
            if not routes:
                out.print_info("没有配置的路由。使用 'agora route add' 添加路由")
            else:
                # Group by first segment (bos domain)
                groups: dict[str, list[tuple[str, str]]] = {}
                for tool, svc in routes.items():
                    prefix = tool.split("_")[0] if "_" in tool else tool
                    groups.setdefault(prefix, []).append((tool, svc))

                out.print_panel(
                    f"共 {len(routes)} 条路由 · {len(groups)} 个域",
                    title="路由表",
                    style="cyan",
                )
                rows = [[tool, svc] for tool, svc in sorted(routes.items())]
                out.print_table(
                    ["工具", "服务"],
                    rows,
                )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_instance(args):
    """Load-balanced instance operations."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        if args.instance_cmd == "add":
            router._add_instance(args.service, args.mcp, args.health, args.port)
            out.print_success(f"Instance added: {args.service} -> {args.mcp}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
