"""CLI commands for tool repository management (Phase 2: load/unload + pipeline)."""

import argparse
import asyncio
import json

from agora.cli.output import OutputFormatter
from agora.mcp_registry.lifecycle import LifecycleManager  # type: ignore[import-not-found]
from agora.mcp_registry.orchestrator import Orchestrator  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]


def _build_orchestrator(catalog: ToolCatalog) -> Orchestrator:
    """Build an Orchestrator with a LifecycleManager (no proxy for CLI)."""
    lifecycle = LifecycleManager(catalog, proxy_manager=None)
    return Orchestrator(catalog, lifecycle=lifecycle)


def cmd_repo(args: argparse.Namespace) -> int:
    """Dispatch repo subcommands."""
    catalog = ToolCatalog()
    try:
        if args.repo_cmd == "list":
            return _cmd_repo_list(catalog, args)
        elif args.repo_cmd == "search":
            return _cmd_repo_search(catalog, args)
        elif args.repo_cmd == "status":
            return _cmd_repo_status(catalog, args)
        elif args.repo_cmd == "info":
            return _cmd_repo_info(catalog, args)
        elif args.repo_cmd == "discover":
            return _cmd_repo_discover(catalog, args)
        elif args.repo_cmd == "install":
            return _cmd_repo_install(catalog, args)
        elif args.repo_cmd == "load":
            return _cmd_repo_load(catalog, args)
        elif args.repo_cmd == "unload":
            return _cmd_repo_unload(catalog, args)
        elif args.repo_cmd == "load-all":
            return _cmd_repo_load_all(catalog, args)
        elif args.repo_cmd == "unload-all":
            return _cmd_repo_unload_all(catalog, args)
        elif args.repo_cmd == "pipeline":
            return _cmd_repo_pipeline(catalog, args)
        elif args.repo_cmd == "remove":
            return _cmd_repo_remove(catalog, args)
        elif args.repo_cmd == "run":
            return _cmd_repo_run(catalog, args)
        else:
            print(f"Unknown repo subcommand: {args.repo_cmd}")
            return 1
    finally:
        catalog.close()


def _cmd_repo_list(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """List tools in the catalog, optionally filtered by status."""
    status = getattr(args, "status", None)
    tools = catalog.list_tools(status=status)
    out = OutputFormatter(json_mode=args.json)
    if args.json:
        out.print_json(tools)
    else:
        if not tools:
            out.print_info("No tools in catalog.")
            return 0
        rows = [[t["id"], t["name"], t.get("status", "?"), f"{t.get('quality_score', 0):.4f}", str(t.get("stars", 0))]
                for t in tools]
        out.print_table(["ID", "Name", "Status", "Score", "Stars"], rows)
    return 0


def _cmd_repo_search(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Search local catalog by keyword."""
    out = OutputFormatter(json_mode=args.json)
    if not args.query:
        out.print_error("search requires a query string.", suggestion="Usage: agora repo search <query> [--status STATUS] [--json]")
        return 1
    tools = catalog.search_tools(args.query, status=getattr(args, "status", None))
    if args.json:
        out.print_json(tools)
    else:
        if not tools:
            out.print_info(f"No results for '{args.query}'.")
            return 0
        out.print_info(f"Found {len(tools)} tool(s) matching '{args.query}':")
        rows = [[t["id"], t["name"], t.get("status", "?"), f"{t.get('quality_score', 0):.4f}"]
                for t in tools]
        out.print_table(["ID", "Name", "Status", "Score"], rows)
    return 0


def _cmd_repo_status(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Show catalog statistics."""
    counts = catalog.count_by_status()
    total = sum(counts.values())
    out = OutputFormatter(json_mode=args.json)
    if args.json:
        out.print_json({"total": total, "by_status": counts})
    else:
        out.print_info(f"Total tools: {total}")
        for status in ("discovered", "installed", "loaded", "idle"):
            cnt = counts.get(status, 0)
            if cnt > 0:
                out.print_info(f"  {status}: {cnt}")
    return 0


def _cmd_repo_info(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Show detailed info for a specific tool."""
    tool = catalog.get_tool(args.name_or_id)
    if not tool:
        print(f"Tool not found: {args.name_or_id}")
        return 1
    out = OutputFormatter(json_mode=True)
    out.print_json(tool)
    return 0


def _cmd_repo_discover(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Search external sources and save to catalog."""
    orchestrator = Orchestrator(catalog)
    results = asyncio.run(
        orchestrator.discover_and_save(
            query=args.query,
            sources=getattr(args, "sources", None),
        )
    )
    out = OutputFormatter(json_mode=args.json)
    if args.json:
        out.print_json(results)
    else:
        out.print_info(f"Discovered {len(results)} tool(s):")
        for t in results:
            score = t.get("quality_score", 0)
            source = t.get("source", "?")
            desc = (t.get("description") or "")[:60]
            out.print_info(f"  [{score:.4f}] {t['name']:<25} ({source}) — {desc}")
    return 0


def _cmd_repo_install(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Install a discovered tool (Phase 2: status update + lifecycle install)."""
    orchestrator = _build_orchestrator(catalog)
    ok, msg = asyncio.run(orchestrator.install_tool(args.name_or_id))
    out = OutputFormatter()
    if ok:
        out.print_success(msg)
    else:
        out.print_error(msg)
    return 0 if ok else 1


def _cmd_repo_load(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Load a tool via the LifecycleManager (Phase 2: proxy integration)."""
    orchestrator = _build_orchestrator(catalog)
    ok, msg = asyncio.run(orchestrator.load_tool(args.name_or_id))
    out = OutputFormatter()
    if ok:
        out.print_success(msg)
    else:
        out.print_error(msg)
    return 0 if ok else 1


def _cmd_repo_unload(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Unload a tool via the LifecycleManager."""
    orchestrator = _build_orchestrator(catalog)
    ok, msg = asyncio.run(orchestrator.unload_tool(args.name_or_id))
    out = OutputFormatter()
    if ok:
        out.print_success(msg)
    else:
        out.print_error(msg)
    return 0 if ok else 1


def _cmd_repo_load_all(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Load all idle tools."""
    orchestrator = _build_orchestrator(catalog)
    count = asyncio.run(orchestrator.load_all_idle())
    out = OutputFormatter()
    out.print_success(f"Loaded {count} tool(s).")
    return 0


def _cmd_repo_unload_all(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Unload all loaded tools."""
    orchestrator = _build_orchestrator(catalog)
    count = asyncio.run(orchestrator.unload_all_loaded())
    out = OutputFormatter()
    out.print_success(f"Unloaded {count} tool(s).")
    return 0


def _cmd_repo_pipeline(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Full discover → install → load pipeline."""
    orchestrator = _build_orchestrator(catalog)
    result = asyncio.run(
        orchestrator.discover_install_load(
            query=args.query,
            sources=getattr(args, "sources", None),
            auto_load=True,
        )
    )
    out = OutputFormatter(json_mode=args.json)
    if args.json:
        out.print_json(result)
    else:
        out.print_success(f"Discovered: {result['discovered']}, Installed: {result['installed']}, Loaded: {result['loaded']}")
    return 0


def _cmd_repo_remove(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Remove a tool from the catalog."""
    ok = catalog.remove_tool(args.name_or_id)
    if ok:
        print(f"Tool '{args.name_or_id}' removed from catalog.")
        return 0
    print(f"Tool not found: {args.name_or_id}")
    return 1


def _cmd_repo_run(catalog: ToolCatalog, args: argparse.Namespace) -> int:
    """Run a natural language query through the Smart Router."""
    import asyncio

    from agora.mcp_registry.embeddings import EmbeddingStore  # type: ignore[import-not-found]
    from agora.mcp_registry.router import SmartRouter  # type: ignore[import-not-found]

    if not args.query:
        print("Error: run requires a query string.")
        print("Usage: agora repo run <query> [--mode direct|recommend|auto]")
        return 1

    async def _run():
        embeddings = EmbeddingStore(catalog._db_path)
        router = SmartRouter(catalog, embeddings=embeddings)
        try:
            result = await router.route(args.query, mode=getattr(args, "mode", "auto"))
            _print_json(result)
            return 0 if result.get("status") == "ok" else 1
        finally:
            embeddings.close()

    return asyncio.run(_run())
