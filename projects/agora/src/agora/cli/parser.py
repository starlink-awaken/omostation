"""CLI argument parser and utility commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agora.persistence import json_load  # type: ignore[import-not-found]


def _load_command_map() -> dict:
    """Load command-prefix -> CLI module mapping from external config."""
    config_path = Path(__file__).with_suffix("").parent / "commands.json"
    return json_load(config_path, default={"prefixes": {}, "fallback": {"module": "eidos.cli", "pass_args": True}})


def run_command(args):
    """Unified entry point -- routes to the right tool automatically."""
    q = args.query.lower()
    words = q.split()
    first_word = words[0] if words else ""
    rest = words[1:]

    cfg = _load_command_map()
    prefixes = cfg.get("prefixes", {})
    mapping = prefixes.get(first_word)

    if mapping:
        cmd = [sys.executable, "-m", mapping["module"]]
        if mapping.get("subcommand"):
            cmd.append(mapping["subcommand"])
        if mapping.get("pass_args") and rest:
            cmd.extend(rest)
        elif mapping.get("default_args") and not rest:
            cmd.extend(mapping["default_args"])
    else:
        fallback = cfg.get("fallback", {})
        cmd = [sys.executable, "-m", fallback.get("module", "eidos.cli")]
        if fallback.get("pass_args", True):
            cmd.extend(words)

    print(f"Agora -> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout[:500])


def run_proxy_launch(args):
    """Proxy-launch subcommand handler."""
    import argparse

    from agora.mcp import mcp_bootstrap as _bootstrap  # type: ignore[import-not-found]

    if args.status:
        status = _bootstrap.get_config_status()
        print(f"Config path: {status['config_path']}")
        print(f"Config exists: {status['config_exists']}")
        print(f"Workspace: {status['workspace'] or '(not found)'}")
        print(f"uv available: {status['uv_available']}")
        print()
        print(f"{'Service':<22} {'Source':<10} {'Avail':<8} {'Installed':<10} Description")
        print("-" * 80)
        for svc in status["services"]:
            exists = "Y" if svc["available"] else "N"
            installed = "Y" if svc["installed"] else "N"
            print(f"{svc['name']:<22} {svc['source']:<10} {exists:<8} {installed:<10} {svc['description']}")
        return

    if args.reload:
        config_path = _bootstrap._get_config_path()
        if config_path.exists():
            config_path.unlink()
        services, _ = _bootstrap.load_or_generate_config()
        enabled = [s["name"] for s in services if s.get("enabled")]
        print(f"Config regenerated at: {config_path}")
        print(f"Enabled services: {', '.join(enabled) if enabled else '(none)'}")
        return

    if args.edit:
        _bootstrap.edit_config()
        return

    # Default: show status
    run_proxy_launch(argparse.Namespace(status=True, reload=False, edit=False))


def build_parser():
    """Build the argument parser."""
    import argparse

    from agora.core.registry import KNOWN_PROTOCOLS  # type: ignore[import-not-found]

    p = argparse.ArgumentParser(
        prog="agora",
        description="Agora -- Service Convergence Hub",
        epilog="""Examples:
  # 注册服务
  agora register my-api --protocol mcp --mcp http://localhost:8000

  # 发现 workspace 中的所有服务
  agora discover --register

  # 列出已注册服务
  agora list

  # 健康检查
  agora health --watch --interval 10

  # 查看服务详情
  agora info my-api --json | jq .

  # MCP 工具仓库
  agora repo list
  agora repo discover mcp-server
  agora repo pipeline mcp-server

  # 流水线
  agora pipeline full --goal "分析代码" --stream

  # 启动 MCP 服务器
  agora mcp

For more: https://github.com/starlink-awaken/agora#readme""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--version", action="store_true", help="Show version")
    sub = p.add_subparsers(dest="command")

    # register
    r = sub.add_parser("register", help="Register a service")
    r.add_argument("name", help="Service name")
    r.add_argument("--protocol", default="mcp", choices=sorted(KNOWN_PROTOCOLS), help="Service protocol (default: mcp)")
    r.add_argument("--protocol-config", default="{}", help="Protocol-specific config as JSON")
    r.add_argument("--mcp", default="", help="MCP endpoint URL (or generic endpoint for non-MCP)")
    r.add_argument("--health", default="", help="Health check URL")
    r.add_argument("--port", type=int, default=0)
    r.add_argument("--tags", default="")
    r.add_argument("--proto", default="", help="gRPC proto file path")
    r.add_argument(
        "--rest-method",
        default=None,
        choices=["GET", "POST", "PUT", "DELETE", "PATCH"],
        help="REST API method (default: GET)",
    )
    r.add_argument("--governance", action="store_true", help=argparse.SUPPRESS)
    r.add_argument("--no-governance", action="store_true", help=argparse.SUPPRESS)
    # A2A metadata for Agent Card
    r.add_argument("--has-auth", action="store_true", help="Service uses authentication")
    r.add_argument("--has-push-notifications", action="store_true", help="Service supports push notifications")
    r.add_argument("--has-state-transitions", action="store_true", help="Service tracks state transitions")
    r.add_argument("--provider-info", default="", help='Provider info JSON (e.g. \'{"organization":"MyOrg"}\')')
    r.add_argument("--documentation-url", default="", help="Documentation URL for the service")

    # unregister
    u = sub.add_parser("unregister", help="Remove a service from registry")
    u.add_argument("name", help="Service name")

    # list
    sub.add_parser("list", help="List all services")

    # discover
    d = sub.add_parser("discover", help="Auto-discover MCP services in workspace")
    d.add_argument("--register", action="store_true", help="Auto-register discovered services")
    d.add_argument("--json", action="store_true", help="JSON output")
    d.add_argument("--watch", action="store_true", help="Watch mode: continuous discovery")
    d.add_argument("--interval", type=int, default=30, help="Watch interval in seconds (default: 30)")
    d.add_argument("--workspace", default="", help="Workspace root path")
    d.add_argument("--probe", action="store_true", help="Enable port probing (async, slow)")

    # instance
    inst = sub.add_parser("instance", help="Instance and peer management")
    inst_sub = inst.add_subparsers(dest="instance_cmd")
    inst_add = inst_sub.add_parser("add", help="Add an instance for load balancing")
    inst_add.add_argument("service", help="Service name")
    inst_add.add_argument("--mcp", required=True, help="MCP endpoint URL")
    inst_add.add_argument("--health", default="", help="Health check URL")
    inst_add.add_argument("--port", type=int, default=0)
    inst_sub.add_parser("list", help="List registered instances")
    inst_register = inst_sub.add_parser("register", help="Register this instance with the peer network")
    inst_register.add_argument("instance_id", help="Unique instance ID")
    inst_register.add_argument("--type", default="mcp-server", help="Instance type (default: mcp-server)")
    inst_register.add_argument("--display-name", default="", help="Human-readable display name")
    inst_register.add_argument("--endpoint", default="", help="MCP endpoint URL")
    inst_register.add_argument("--a2a-endpoint", default="", help="A2A endpoint URL")
    inst_register.add_argument("--owner", default="", help="Owner identifier")
    inst_register.add_argument("--capabilities", default="", help="Comma-separated capabilities")
    inst_peer = inst_sub.add_parser("peer", help="Peer with another instance")
    inst_peer.add_argument("instance_id", help="This instance ID")
    inst_peer.add_argument("peer_id", help="Peer instance ID")

    # tenant
    ten = sub.add_parser("tenant", help="Multi-tenant management")
    ten_sub = ten.add_subparsers(dest="tenant_cmd")
    ten_sub.add_parser("list", help="List all tenants")
    ten_add = ten_sub.add_parser("add", help="Add a tenant")
    ten_add.add_argument("name", help="Tenant name")
    ten_add.add_argument("--services", default="", help="Comma-separated allowed services")
    ten_add.add_argument("--rate-limit", type=int, default=60, help="Requests per minute")
    ten_rm = ten_sub.add_parser("remove", help="Remove a tenant")
    ten_rm.add_argument("name", help="Tenant name")

    # market
    mkt = sub.add_parser("market", help="MCP tool marketplace")
    mkt_sub = mkt.add_subparsers(dest="market_cmd")
    mkt_sub.add_parser("list", help="List available MCP services")
    mkt_search = mkt_sub.add_parser("search", help="Search MCP services")
    mkt_search.add_argument("keyword", help="Search keyword")
    mkt_install = mkt_sub.add_parser("install", help="Install an MCP service")
    mkt_install.add_argument("name", help="Service name or GitHub repo (e.g. filesystem, starlink-awaken/minerva)")
    mkt_pub = mkt_sub.add_parser("publish", help="Publish a service to the market")
    mkt_pub.add_argument("name", help="Service name")
    mkt_pub.add_argument("--repo", default="", help="GitHub repo (e.g. starlink-awaken/my-service)")
    mkt_pub.add_argument("--description", default="", help="Service description")
    mkt_pub.add_argument("--entry", default="server.py", help="Entry point file")
    mkt_pub.add_argument("--type", default="python", help="Service type (python|node)")

    # repo subcommand
    repo = sub.add_parser("repo", help="MCP tool repository management")
    repo_sub = repo.add_subparsers(dest="repo_cmd")

    repo_list = repo_sub.add_parser("list", help="List tools in catalog")
    repo_list.add_argument("--status", choices=["discovered", "installed", "loaded", "idle"], help="Filter by status")
    repo_list.add_argument("--json", action="store_true", help="JSON output")

    repo_search = repo_sub.add_parser("search", help="Search local catalog")
    repo_search.add_argument("query", help="Search keyword")
    repo_search.add_argument("--status", choices=["discovered", "installed", "loaded", "idle"], help="Filter by status")
    repo_search.add_argument("--json", action="store_true", help="JSON output")

    repo_status = repo_sub.add_parser("status", help="Show catalog statistics")
    repo_status.add_argument("--json", action="store_true", help="JSON output")

    repo_info = repo_sub.add_parser("info", help="Show tool details")
    repo_info.add_argument("name_or_id", help="Tool name or ID")

    repo_discover = repo_sub.add_parser("discover", help="Discover tools from external sources")
    repo_discover.add_argument("query", nargs="?", default="mcp-server", help="Search query (default: mcp-server)")
    repo_discover.add_argument("--json", action="store_true", help="JSON output")

    repo_install = repo_sub.add_parser("install", help="Install a tool (status update)")
    repo_install.add_argument("name_or_id", help="Tool name or ID to install")

    repo_load = repo_sub.add_parser("load", help="Load a tool via LifecycleManager (Phase 2)")
    repo_load.add_argument("name_or_id", help="Tool name or ID to load")

    repo_unload = repo_sub.add_parser("unload", help="Unload a tool via LifecycleManager (Phase 2)")
    repo_unload.add_argument("name_or_id", help="Tool name or ID to unload")

    repo_load_all = repo_sub.add_parser("load-all", help="Load all idle tools")
    repo_load_all.add_argument("--json", action="store_true", help="JSON output")

    repo_unload_all = repo_sub.add_parser("unload-all", help="Unload all loaded tools")
    repo_unload_all.add_argument("--json", action="store_true", help="JSON output")

    repo_pipeline = repo_sub.add_parser("pipeline", help="Full discover → install → load pipeline (Phase 2)")
    repo_pipeline.add_argument("query", nargs="?", default="mcp-server", help="Search query (default: mcp-server)")
    repo_pipeline.add_argument("--json", action="store_true", help="JSON output")

    repo_remove = repo_sub.add_parser("remove", help="Remove a tool from catalog")
    repo_remove.add_argument("name_or_id", help="Tool name or ID to remove")

    repo_run = repo_sub.add_parser("run", help="Execute a natural language query via Smart Router")
    repo_run.add_argument("query", help="Natural language query")
    repo_run.add_argument(
        "--mode", choices=["direct", "recommend", "auto"], default="auto", help="Routing mode (default: auto)"
    )

    # search
    s = sub.add_parser("search", help="Search services by keyword")
    s.add_argument("keyword", help="Search keyword")
    s.add_argument("--json", action="store_true", help="JSON output")

    # info
    i = sub.add_parser("info", help="Show service details")
    i.add_argument("name", help="Service name")
    i.add_argument("--json", action="store_true", help="JSON output")

    # stats
    sub.add_parser("stats", help="Show service statistics")

    # health
    h = sub.add_parser("health", help="Probe all services")
    h.add_argument("--watch", action="store_true", help="Continuous health monitoring")
    h.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")
    h.add_argument("--json", action="store_true", help="JSON output")
    h.add_argument("--services", type=str, default="", help="Check specific services (comma-separated)")

    # route
    rt = sub.add_parser("route", help="Add a tool route")
    rt.add_argument("tool", help="Tool name")
    rt.add_argument("service", help="Service name")

    # routes
    sub.add_parser("routes", help="List all routes")

    # mcp
    sub.add_parser("mcp", help="Start MCP server")

    # init
    sub.add_parser("init", help="Guided setup wizard for first-time users")

    # sync
    sync_parser = sub.add_parser("sync", help="Sync workspace services to Agora registry")
    sync_parser.add_argument("--workspace", default="", help="Workspace root path")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")

    # converge (merged from gateway)
    converge_parser = sub.add_parser("converge", help="Converge workspace services (delegates to sync)")
    converge_parser.add_argument("--workspace", default="", help="Workspace root path")
    converge_parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")

    # completion
    sub.add_parser("completion", help="Generate shell completion (bash/zsh)")

    # config
    sub.add_parser("config", help="Show config paths and status")

    # proxy-launch
    proxy_launch = sub.add_parser("proxy-launch", help="Launch downstream MCP services via auto-bootstrap")
    proxy_launch.add_argument("--status", action="store_true", help="Show service status without launching")
    proxy_launch.add_argument("--reload", action="store_true", help="Regenerate config from KNOWN_SERVICES")
    proxy_launch.add_argument("--edit", action="store_true", help="Open config file in editor")
    proxy_launch.set_defaults(func=run_proxy_launch)

    # web
    sub.add_parser("web", help="Start Web Dashboard (port 7430)")

    # pipeline MCP endpoint
    start_parser = sub.add_parser("start-pipeline", help="Start Eidos Pipeline MCP endpoint")
    from agora.pipelines.eidos_pipeline import EIDOS_PIPELINE_SERVICE  # type: ignore[import-not-found]

    start_parser.add_argument(
        "--pipeline", choices=list(EIDOS_PIPELINE_SERVICE["commands"].keys()), default="knowledge-base"
    )
    start_parser.add_argument("--port", type=int, default=8080, help="Port number")
    start_parser.set_defaults(func=start_pipeline_command)

    unified_parser = sub.add_parser("run", help="Unified entry -- auto-route to the right tool")
    unified_parser.add_argument("query", help="Natural language query or CLI command")
    unified_parser.set_defaults(func=run_command)

    # accounting
    acct = sub.add_parser("accounting", help="Resource accounting and quota queries")
    acct_sub = acct.add_subparsers(dest="accounting_cmd")
    acct_top = acct_sub.add_parser("top", help="Show top callers by cost")
    acct_top.add_argument(
        "--period", default="day", choices=["day", "week", "month", "all"], help="Time period (default: day)"
    )
    acct_top.add_argument("--limit", type=int, default=10, help="Number of top callers (default: 10)")
    acct_report = acct_sub.add_parser("report", help="Show summary report")
    acct_report.add_argument(
        "--period", default="week", choices=["day", "week", "month", "all"], help="Time period (default: week)"
    )
    acct_quota = acct_sub.add_parser("quota", help="Show quota for a caller")
    acct_quota.add_argument("--caller", required=True, help="Caller ID to check quota for")
    acct_quota.add_argument("--quota", type=float, default=10.0, help="Daily quota in USD (default: 10.0)")

    # pipeline
    pl = sub.add_parser("pipeline", help="Run a named pipeline")
    pl.add_argument("name", help="Pipeline name")
    pl.add_argument("--goal", default="", help="Goal for matching/derivation")
    pl.add_argument("--context", default="", help="Context keywords")
    pl.add_argument("--project", default=".", help="Project path for derivation")
    pl.add_argument("--json", action="store_true", help="JSON output")
    pl.add_argument("--stream", action="store_true", help="Stream each step as it completes")
    pl.add_argument("--parallel", action="store_true", help="Execute independent steps concurrently")

    # key
    key = sub.add_parser("key", help="API Key management (v2.0)")
    key_sub = key.add_subparsers(dest="key_cmd")
    key_create = key_sub.add_parser("create", help="Create a new API key")
    key_create.add_argument("name", help="Key name")
    key_create.add_argument("--scopes", default="read", help="Comma-separated scopes (read,write,admin)")
    key_create.add_argument("--tenant", default="", help="Tenant name")
    key_create.add_argument("--expires", type=int, default=0, help="Expiry in days (0=never)")
    key_sub.add_parser("list", help="List all API keys")
    key_revoke = key_sub.add_parser("revoke", help="Revoke an API key")
    key_revoke.add_argument("key_id", help="Key ID to revoke")
    key_rotate = key_sub.add_parser("rotate", help="Rotate an API key (revoke old, create new with same attributes)")
    key_rotate.add_argument("key_id", help="Key ID to rotate")
    key_rotate.add_argument("--expires", type=int, default=0, help="New expiry in days (0=keep same)")

    # audit
    audit = sub.add_parser("audit", help="Audit log query (v2.0)")
    audit.add_argument("--action", default="", help="Filter by action")
    audit.add_argument("--actor", default="", help="Filter by actor")
    audit.add_argument("--since", default="", help="ISO timestamp lower bound")
    audit.add_argument("--limit", type=int, default=50, help="Max entries")
    audit.add_argument("--stats", action="store_true", help="Show statistics")

    # transitions
    trans = sub.add_parser("transitions", help="State transition history")
    trans.add_argument("service", nargs="?", default="", help="Service name filter")
    trans.add_argument("--since", default="", help="ISO timestamp lower bound")
    trans.add_argument("--limit", type=int, default=50, help="Max entries")
    trans.add_argument("--json", action="store_true", help="JSON output")

    # a2a
    a2a = sub.add_parser("a2a", help="A2A Task API")
    a2a_sub = a2a.add_subparsers(dest="a2a_cmd")
    a2a_send = a2a_sub.add_parser("send", help="Submit an A2A task")
    a2a_send.add_argument("tool_name", help="Tool name (e.g. minerva.research_now)")
    a2a_send.add_argument("arguments", nargs="?", default="{}", help="JSON arguments")
    a2a_send.add_argument("--session", default="", help="Session identifier")
    a2a_get = a2a_sub.add_parser("get", help="Get an A2A task")
    a2a_get.add_argument("task_id", help="Task ID")
    a2a_cancel = a2a_sub.add_parser("cancel", help="Cancel an A2A task")
    a2a_cancel.add_argument("task_id", help="Task ID")
    a2a_list = a2a_sub.add_parser("list", help="List A2A tasks")
    a2a_list.add_argument("--service", default="", help="Filter by service name")
    a2a_list.add_argument("--status", default="", help="Filter by status (submitted|working|completed|failed|canceled)")
    a2a_list.add_argument("--since", default="", help="ISO timestamp lower bound")
    a2a_list.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # agent-card
    ac = sub.add_parser("agent-card", help="A2A Agent Card operations")
    ac_sub = ac.add_subparsers(dest="agent_card_cmd")
    ac_sub.add_parser("list", help="List all Agent Cards")
    ac_get = ac_sub.add_parser("get", help="Get an Agent Card for a service")
    ac_get.add_argument("name", help="Service name")

    # proto
    proto = sub.add_parser("proto", help="gRPC proto compilation tools")
    proto_sub = proto.add_subparsers(dest="proto_cmd")
    proto_compile = proto_sub.add_parser("compile", help="Compile .proto to pb2_grpc.py")
    proto_compile.add_argument("proto_file", help="Path to .proto file")
    proto_compile.add_argument("--out", default=".", help="Output directory (default: current dir)")

    # pipelines
    sub.add_parser("pipelines", help="List available pipelines")

    # pipeline-define
    pd = sub.add_parser("pipeline-define", help="Define a custom pipeline from JSON file")
    pd.add_argument("file", help="Pipeline definition JSON file")

    # event
    ev = sub.add_parser("event", help="Event bus operations")
    ev_sub = ev.add_subparsers(dest="event_cmd")
    ev_pub = ev_sub.add_parser("publish", help="Publish an event")
    ev_pub.add_argument("type", help="Event type (e.g. index:done)")
    ev_pub.add_argument("--payload", default="{}", help="JSON payload")
    ev_pub.add_argument("--source", default="cli", help="Source service name")
    ev_log = ev_sub.add_parser("log", help="View event log")
    ev_log.add_argument("--limit", type=int, default=50, help="Max events")
    ev_sub_scribe = ev_sub.add_parser("subscribe", help="Subscribe to events")
    ev_sub_scribe.add_argument("pattern", help="Event pattern (e.g. index:*)")
    ev_sub_scribe.add_argument("--callback", default="", help="Callback URL")
    ev_unsub = ev_sub.add_parser("unsubscribe", help="Unsubscribe")
    ev_unsub.add_argument("id", help="Subscription ID")

    # enforce
    enf = sub.add_parser("enforce", help="Authorizer enforce mode (R5)")
    enf_sub = enf.add_subparsers(dest="enforce_cmd")
    enf_sub.add_parser("list", help="Show current enforce tools and sample checks")
    enf_set = enf_sub.add_parser("set", help="Set enforce tools (one or more patterns)")
    enf_set.add_argument("tool", nargs="+", default=[], help="Tool patterns (e.g. collab.* or *)")
    enf_sub.add_parser("clear", help="Disable enforce (all pass-through)")

    # identity
    identity = sub.add_parser("identity", help="Identity certificate operations")
    identity_sub = identity.add_subparsers(dest="identity_cmd")
    identity_sub.add_parser("init", help="Initialize identity CA")
    identity_issue = identity_sub.add_parser("issue", help="Issue a certificate")
    identity_issue.add_argument("subject_id", help="Subject identifier")
    identity_issue.add_argument("--subject-type", default="service", help="Subject type (default: service)")
    identity_issue.add_argument("--tenant", default="", help="Tenant name")
    identity_issue.add_argument("--expires-days", type=int, default=365, help="Validity period in days (default: 365)")
    identity_verify = identity_sub.add_parser("verify", help="Verify a certificate")
    identity_verify.add_argument("subject_id", help="Subject identifier")
    identity_revoke = identity_sub.add_parser("revoke", help="Revoke a certificate")
    identity_revoke.add_argument("subject_id", help="Subject identifier")
    identity_list = identity_sub.add_parser("list", help="List certificates")
    identity_list.add_argument("--tenant", default="", help="Tenant filter")

    # grant
    grant = sub.add_parser("grant", help="Authorization grant operations")
    grant_sub = grant.add_subparsers(dest="grant_cmd")
    grant_create = grant_sub.add_parser("create", help="Create an authorization grant")
    grant_create.add_argument("subject", help="Subject identifier")
    grant_create.add_argument("capability", help="Capability name (e.g. service:invoke)")
    grant_create.add_argument("--scope", default="", help="Scope restriction")
    grant_create.add_argument("--constraints", default="", help="JSON constraints")
    grant_revoke = grant_sub.add_parser("revoke", help="Revoke an authorization grant")
    grant_revoke.add_argument("grant_id", help="Grant ID")
    grant_list = grant_sub.add_parser("list", help="List authorization grants")
    grant_list.add_argument("--subject", default="", help="Filter by subject")
    grant_check = grant_sub.add_parser("check", help="Check authorization")
    grant_check.add_argument("--subject", default="", help="Subject to check")
    grant_check.add_argument("--tool", default="", help="Tool name")
    grant_check.add_argument("--cost", type=float, default=0.0, help="Cost in USD")

    # pallas subcommands (merged from pallas CLI)
    from agora.cli.commands_pallas import add_pallas_subparser  # type: ignore[import-not-found]

    add_pallas_subparser(sub)

    return p


def start_pipeline_command(args):
    """Start a simple HTTP server that serves pipeline results."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from agora.pipelines.eidos_pipeline import EIDOS_PIPELINE_SERVICE

    command = EIDOS_PIPELINE_SERVICE["commands"].get(args.pipeline, "")

    if args.pipeline not in EIDOS_PIPELINE_SERVICE.get("commands", {}):
        print(f"Error: Unknown pipeline '{args.pipeline}'", file=sys.stderr)
        print(f"Available: {list(EIDOS_PIPELINE_SERVICE.get('commands', {}).keys())}", file=sys.stderr)
        sys.exit(1)

    class PipelineHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/tools":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"pipelines": list(EIDOS_PIPELINE_SERVICE["commands"].keys())}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")

    print(f"Eidos Pipeline MCP endpoint starting on port {args.port}")
    print(f"Pipeline: {args.pipeline}")
    print(f"Command: {command}")
    HTTPServer(("", args.port), PipelineHandler).serve_forever()
