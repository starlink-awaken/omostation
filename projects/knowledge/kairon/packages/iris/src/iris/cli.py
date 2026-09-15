"""Iris CLI — unified command-line interface for all connectors.

Commands:
  list      — list connectors or platform content
  search    — search platform content
  get       — get item by ID
  status    — connector health/sync status
  sync      — trigger pull sync
  export    — export connector data
  config    — view/set configuration
  init      — initialize connector domains
  adapters  — show SSOT + eidos adapter status
  validate  — validate data as eidos KnowledgeCard
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from iris.base import BaseConnector
    from iris.registry import ConnectorRegistry

from iris import __version__
from iris.config import IrisConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iris",
        description="Connector Hub for Personal Knowledge Platforms",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"iris {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = sub.add_parser("list", help="List connectors or platform content")
    list_p.add_argument("platform", nargs="?", help="Platform name (omit to list all connectors)")
    list_p.add_argument("--limit", type=int, default=20, help="Max items (default: 20)")

    # search
    search_p = sub.add_parser("search", help="Search platform content")
    search_p.add_argument("platform", help="Platform name")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--limit", type=int, default=10)

    # get
    get_p = sub.add_parser("get", help="Get an item by platform and ID")
    get_p.add_argument("platform", help="Platform name")
    get_p.add_argument("id", help="Item ID")

    # status
    sub.add_parser("status", help="Show all connector health/sync status")

    # sync
    sync_p = sub.add_parser("sync", help="Pull latest data from connectors")
    sync_p.add_argument("platforms", nargs="*", help="Platforms to sync (all if omitted)")
    sync_p.add_argument("--dry-run", action="store_true", help="Preview without syncing")
    sync_p.add_argument(
        "--bidirectional",
        "-b",
        action="store_true",
        help="Run Obsidian ↔ WPS Note bidirectional sync",
    )

    # export
    export_p = sub.add_parser("export", help="Export connector content")
    export_p.add_argument("platform", help="Platform name")
    export_p.add_argument("--format", choices=["json", "md"], default="json", help="Output format")
    export_p.add_argument("--output", "-o", help="Output file path (default: stdout)")

    # config
    config_p = sub.add_parser("config", help="View or set configuration")
    config_p.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    config_p.add_argument("key", nargs="?", help="Config key (e.g., obsidian.vault)")
    config_p.add_argument("value", nargs="?", help="Config value")

    # init
    init_p = sub.add_parser("init", help="Initialize connector domains")
    init_p.add_argument("--platform", help="Initialize a specific platform")

    # adapters
    sub.add_parser("adapters", help="Show SSOT + eidos adapter status")

    # validate
    validate_p = sub.add_parser("validate", help="Validate a data file as eidos KnowledgeCard")
    validate_p.add_argument("file", help="JSON file to validate")
    validate_p.add_argument("--type", default="KnowledgeCard", help="Schema type (KnowledgeCard, Fact, OntologyNode)")

    return parser


def _get_registry() -> ConnectorRegistry:
    """Lazy import to avoid circular deps at module level."""
    from iris.registry import ConnectorRegistry

    registry = ConnectorRegistry()
    _register_all_connectors(registry)
    return registry


def _register_all_connectors(registry: ConnectorRegistry) -> None:
    """Register all available connectors."""
    from iris.connectors import register_all

    register_all(registry)


def _get_available_connector(registry: ConnectorRegistry, name: str, use_json: bool) -> BaseConnector | None:
    """Get a connector by name. If not found or unavailable, print status and return None."""
    connector = registry.get(name)
    if not connector:
        _error(f"Unknown platform: {name}", use_json)
    if not connector.is_available():
        s = connector.status()
        s["name"] = connector.name
        s["display_name"] = connector.display_name
        s["available"] = False
        _print([s], use_json)
        return None
    return connector


def cmd_list(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris list`."""
    registry = _get_registry()

    if args.platform:
        connector = _get_available_connector(registry, args.platform, args.json)
        if connector is None:
            return
        items = connector.list_items(limit=args.limit)
        _print(
            [item.to_dict() for item in items],
            args.json,
        )
    else:
        results = []
        for conn in registry.list_all():
            try:
                avail = conn.is_available()
                s = conn.status()
                results.append(
                    {
                        "name": conn.name,
                        "display_name": conn.display_name,
                        "available": avail,
                        **s,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "name": conn.name,
                        "display_name": getattr(conn, "display_name", conn.name),
                        "available": False,
                        "error": str(e),
                    }
                )
        _print(results, args.json)


def cmd_search(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris search <platform> <query>`."""
    registry = _get_registry()
    connector = _get_available_connector(registry, args.platform, args.json)
    if connector is None:
        return
    items = connector.search(args.query, limit=args.limit)
    _print([item.to_dict() for item in items], args.json)


def cmd_get(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris get <platform> <id>`."""
    registry = _get_registry()
    connector = _get_available_connector(registry, args.platform, args.json)
    if connector is None:
        return
    item = connector.get_item(args.id)
    if item:
        card = item.to_knowledge_card()
        from iris.adapters.eidos import EidosAdapter

        eidos = EidosAdapter()
        if eidos.is_eidos_available():
            validation = eidos.validate_knowledge_card(card)
            if not validation.get("is_valid", True):
                _error("Item failed eidos validation", args.json)
            card["_validation"] = validation
        _print(card, args.json)
    else:
        _print({"error": f"Item {args.id} not found on {args.platform}"}, args.json)


def cmd_status(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris status`."""
    registry = _get_registry()
    results = registry.status_all()
    _print(results, args.json)


def cmd_sync(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris sync`."""
    if args.bidirectional:
        _run_bidirectional_sync(args, config)
        return

    registry = _get_registry()
    platforms = args.platforms or registry.list_names()
    results = []
    for name in platforms:
        connector = registry.get(name)
        if not connector:
            results.append({"connector": name, "success": False, "error": "Unknown"})
            continue
        result = connector.sync(dry_run=args.dry_run)
        results.append(result.to_dict())
    _print(results, args.json)


def _run_bidirectional_sync(args: argparse.Namespace, config: IrisConfig) -> None:
    """Execute bidirectional sync between Obsidian and WPS Note."""
    from iris.connectors.obsidian import ObsidianConnector
    from iris.connectors.wpsnote import WPSNoteConnector
    from iris.sync.engine import SyncEngine

    obsidian = ObsidianConnector(config)
    wpsnote = WPSNoteConnector(config)

    if not obsidian.is_available():
        _error("Obsidian connector is not available", args.json)
    if not wpsnote.is_available():
        _error("WPS Note connector is not available", args.json)

    engine = SyncEngine(obsidian, wpsnote, config=config)
    result = engine.sync_bidirectional(dry_run=args.dry_run)

    if args.json:
        _print(result.to_dict(), args.json)
    else:
        _print_sync_bidirectional(result)


def _print_sync_bidirectional(result: Any) -> None:
    """Print bidirectional sync results in human-readable format."""

    d = result.to_dict()
    status = "✅" if d.get("success") else "⚠️"
    print(f"\n  {status} Bidirectional Sync Complete")
    print(f"     Timestamp: {d.get('timestamp', 'unknown')}")
    print(f"     Synced:    {d.get('synced', 0)}")
    print(f"     Created:   {d.get('created', 0)}")
    print(f"     Updated:   {d.get('updated', 0)}")
    print(f"     Deleted:   {d.get('deleted', 0)}")
    print(f"     Conflicts: {d.get('conflicts', 0)}")
    if d.get("errors"):
        print(f"     Errors:    {len(d['errors'])}")
        for err in d["errors"][:5]:
            print(f"       ❌ {err}")
    print()


def cmd_export(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris export`."""
    registry = _get_registry()
    connector = registry.get(args.platform)
    if not connector:
        _error(f"Unknown platform: {args.platform}", args.json)
    output = connector.export(fmt=args.format)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        _print({"exported": args.platform, "format": args.format, "path": args.output}, args.json)
    else:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")


def cmd_config(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris config`."""
    if args.action == "set":
        if not args.key or not args.value:
            _error("Usage: iris config set <key> <value>", args.json)
        config.set(args.key, args.value)
        _print({"set": args.key, "value": args.value}, args.json)
    else:
        _print(config.to_dict(), args.json)


def cmd_init(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris init`."""
    from iris.adapters.ssot import SSOTDomainAdapter

    ssot = SSOTDomainAdapter(config)

    if args.platform:
        ssot.ensure_domain(args.platform)
        _print({"initialized": args.platform, "path": str(ssot.domains_dir / args.platform)}, args.json)
    else:
        registry = _get_registry()
        paths = []
        for conn in registry.list_all():
            path = ssot.ensure_domain(conn.name, conn.display_name)
            paths.append(str(path))
        _print({"initialized": len(paths), "domains": paths}, args.json)


def cmd_adapters(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris adapters`."""
    from iris.adapters.eidos import EidosAdapter
    from iris.adapters.ssot import SSOTDomainAdapter

    ssot = SSOTDomainAdapter(config)
    eidos = EidosAdapter()

    ssot_status = ssot.status()
    domain_data = ssot_status.pop("domain_data", {})
    result = {
        "ssot": ssot_status,
        "eidos": eidos.status(),
        "domains": {},
    }
    for domain_name, data in domain_data.items():
        if data and "entities" in data:
            result["domains"][domain_name] = {
                "entities": len(data.get("entities", [])),
                "facts": len(data.get("facts", [])),
            }
        elif data and "error" not in data:
            result["domains"][domain_name] = {"status": "initialized"}
    _print(result, args.json)


def cmd_validate(args: argparse.Namespace, config: IrisConfig) -> None:
    """Handle `iris validate <file>`."""
    from iris.adapters.eidos import EidosAdapter

    eidos = EidosAdapter()
    try:
        with open(args.file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        _error(f"Cannot load file: {e}", args.json)

    schema_type = args.type.lower()

    if "card" in schema_type or "knowledge" in schema_type:
        result = eidos.validate_knowledge_card(data)
    elif "fact" in schema_type:
        result = eidos.validate_fact(data)
    elif "node" in schema_type or "ontology" in schema_type:
        result = eidos.validate_ontology_node(data)
    else:
        _error(f"Unknown schema type: {args.type}", args.json)

    _print(result, args.json)


def _print(data: Any, use_json: bool) -> None:
    """Print output — JSON or human-readable."""
    if use_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _print_human(data)


def _print_human(data: Any) -> None:
    """Print human-readable output."""
    if isinstance(data, list):
        if not data:
            print("(no results)")
            return
        # Detect if this is a list of connector statuses or items
        if data and isinstance(data[0], dict) and "display_name" in data[0]:
            _print_connectors(data)
        elif data and isinstance(data[0], dict) and "connector" in data[0]:
            _print_sync_results(data)
        else:
            _print_items(data)
    elif isinstance(data, dict):
        _print_detail(data)
    else:
        print(data)


def _print_connectors(items: list[dict]) -> None:
    """Print connector status table."""
    for item in items:
        avail = "✅" if item.get("available", False) else "❌"
        extras = " ".join(f"{k}={v}" for k, v in item.items() if k not in ("name", "display_name", "available"))
        print(f"  {avail} {item['name']:<12} ({item['display_name']}) {extras}")


def _print_sync_results(items: list[dict]) -> None:
    """Print sync result lines."""
    for item in items:
        status = "✅" if item.get("success") else "❌"
        msg = item.get("message", item.get("error", ""))
        print(f"  {status} {item['connector']}: {msg}")


def _print_items(items: list[dict]) -> None:
    """Print a list of note/article/highlight items as a human-friendly table."""
    for i, item in enumerate(items):
        _print_note_item(item)
        if i < len(items) - 1:
            print()


def _print_note_item(item: dict) -> None:
    """Print a single note-like item in human-readable format."""
    title = item.get("title", "(untitled)")
    note_id = item.get("id", "")
    tags = item.get("tags", [])
    content = item.get("content", "")
    notebook = item.get("platform_notebook", "")

    # Title line
    tag_str = ""
    if tags:
        tag_str = "  " + " ".join(f"#{t}" for t in tags[:5])
        if len(tags) > 5:
            tag_str += f" +{len(tags) - 5}"
    print(f"  📄 {title}{tag_str}")

    # Metadata line
    meta_parts = [f"id: {note_id}"]
    if notebook:
        meta_parts.append(f"dir: {notebook}")
    print(f"     {' | '.join(meta_parts)}")

    # Content preview
    if content:
        # Strip frontmatter
        preview = re.sub(r"^---\n.*?\n---\n*", "", content, flags=re.DOTALL)
        # Strip markdown heading markers
        preview = re.sub(r"#{1,6}\s+", "", preview)
        # Take first non-empty line
        preview = preview.strip()
        first_line = preview.split("\n")[0].strip() if preview else ""
        if first_line:
            max_len = 100
            snippet = first_line[:max_len]
            if len(first_line) > max_len:
                snippet += "..."
            print(f"     {snippet}")


def _print_detail(item: dict) -> None:
    """Print a single detail dict (for get/config/validate commands)."""
    if "error" in item:
        print(f"  Error: {item['error']}")
        return
    if "connector" in item:
        _print_sync_results([item])
        return
    for k, v in item.items():
        if k == "raw_data" or k == "_validation":
            continue
        if isinstance(v, str) and len(v) > 80:
            print(f"  {k}: {v[:77]}...")
        elif isinstance(v, list):
            if len(v) > 5:
                print(f"  {k}: [{', '.join(str(x) for x in v[:5])}, +{len(v) - 5} more]")
            else:
                print(f"  {k}: {v}")
        elif isinstance(v, dict):
            if v:
                items = ", ".join(f"{sk}: {sv}" for sk, sv in list(v.items())[:3])
                if len(v) > 3:
                    items += f" +{len(v) - 3} more"
                print(f"  {k}: {{{items}}}")
            else:
                print(f"  {k}: {{}}")
        else:
            print(f"  {k}: {v}")


def _error(msg: str, use_json: bool) -> NoReturn:
    """Print error and exit."""
    if use_json:
        print(json.dumps({"error": msg}, ensure_ascii=False))
    else:
        print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    print("⚠️ Iris 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = build_parser()
    args = parser.parse_args()
    config = IrisConfig()

    commands = {
        "list": cmd_list,
        "search": cmd_search,
        "get": cmd_get,
        "status": cmd_status,
        "sync": cmd_sync,
        "export": cmd_export,
        "config": cmd_config,
        "init": cmd_init,
        "adapters": cmd_adapters,
        "validate": cmd_validate,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
