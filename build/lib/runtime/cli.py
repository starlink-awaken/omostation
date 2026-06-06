"""Runtime CLI — eCOS Layer 1 infrastructure management.

Usage:
    runtime health               — run health scan (delegates to health-scan.sh)
    runtime matrix list          — list all services
    runtime matrix get <name>    — show service details
    runtime matrix resolve       — expand all env-var paths
    runtime service <name> status — check service status (delegates to service-ctl.sh)
    runtime service <name> start  — start a service
    runtime service <name> stop   — stop a service
    runtime protocol list         — list L0 protocols
    runtime protocol get <name>   — show protocol details
    runtime status                — quick summary: matrix version + count
    runtime version               — show runtime CLI version
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .matrix import (
    RUNTIME_HOME, RUNTIME_MATRIX,
    load_matrix, get_service, resolve_path,
    list_services, ServiceEntry,
)
from .protocol import L0_PROTOCOLS, get_protocol, by_category, validate_protocol_message


# ─── Helpers ────────────────────────────────────────────────────────────────

def _run_script(name: str, *args: str) -> int:
    """Run a shell script from the runtime scripts directory."""
    script = Path(__file__).parent.parent.parent / "scripts" / name
    if not script.exists():
        print(f"❌ Script not found: {script}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env.setdefault("RUNTIME_HOME", str(RUNTIME_HOME))
    r = subprocess.run([str(script), *args], env=env)
    return r.returncode


def _print_table(rows: list[list[str]], headers: list[str]) -> None:
    """Print a aligned table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "  "
    hdr = sep.join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(hdr)
    print("-" * len(hdr))
    for row in rows:
        print(sep.join(c.ljust(w) for c, w in zip(row, col_widths)))


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_health() -> int:
    return _run_script("health-scan.sh")


def cmd_health_json() -> int:
    return _run_script("health-scan.sh", "--json")


def cmd_matrix_list() -> int:
    try:
        services = list_services()
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    rows = []
    for svc in services:
        port = str(svc.port) if svc.port else "—"
        rows.append([svc.name, f"[{svc.type}]", f":{port}", svc.status])
    _print_table(rows, ["SERVICE", "TYPE", "PORT", "STATUS"])
    return 0


def cmd_matrix_get(name: str) -> int:
    svc = get_service(name)
    if not svc:
        print(f"❌ Service not found: {name}", file=sys.stderr)
        return 1
    print(f"Service: {svc.name}")
    print(f"  Type:      {svc.type}")
    print(f"  Status:    {svc.status}")
    if svc.port:
        print(f"  Port:      {svc.port}")
    if svc.launchd_label:
        print(f"  Launchd:   {svc.launchd_label}")
    if svc.health_url:
        print(f"  Health:    {svc.health_url}")
    if svc.docker_container:
        print(f"  Docker:    {svc.docker_container}")
    print(f"  Deploy:    {resolve_path(svc.deploy_path) or '—'}")
    print(f"  Logs:      {resolve_path(svc.log_path) or '—'}")
    if svc.notes:
        print(f"  Notes:     {svc.notes[:120]}...")
    return 0


def cmd_matrix_resolve() -> int:
    try:
        services = list_services()
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    for svc in services:
        resolved = resolve_path(svc.deploy_path)
        if resolved:
            print(f"  {svc.name:25s} → {resolved}")
    return 0


def cmd_service(name: str, action: str) -> int:
    return _run_script("service-ctl.sh", name, action)


def cmd_protocol_list() -> int:
    rows = []
    for p in L0_PROTOCOLS:
        status_icon = {"active": "✅", "draft": "📝", "planned": "🔲", "deprecated": "🗄️"}.get(p.status, "❓")
        rows.append([f"{status_icon} {p.name}", f"v{p.version}", p.category, p.status])
    _print_table(rows, ["PROTOCOL", "VERSION", "CATEGORY", "STATUS"])
    print(f"\nTotal: {len(L0_PROTOCOLS)} protocols")
    return 0


def cmd_protocol_get(name: str) -> int:
    p = get_protocol(name)
    if not p:
        print(f"❌ Protocol not found: {name}", file=sys.stderr)
        return 1
    print(f"Protocol: {p.name} v{p.version}")
    print(f"  Category:  {p.category}")
    print(f"  Status:    {p.status}")
    print(f"  Desc:      {p.description}")
    if p.spec_url:
        print(f"  Spec:      {p.spec_url}")
    if p.port_range:
        print(f"  Ports:     {p.port_range}")
    print(f"  Transport: {', '.join(p.transport)}")
    if p.implementations:
        for impl in p.implementations:
            if impl:
                print(f"  Impl:      {impl}")
    if p.notes:
        print(f"  Notes:     {p.notes}")
    return 0


def cmd_protocol_validate(name: str, message_json: str) -> int:
    """Validate a protocol message against the L0 registry."""
    try:
        message = json.loads(message_json)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON: {message_json[:100]}", file=sys.stderr)
        return 1
    ok, msg = validate_protocol_message(name, message)
    if ok:
        print(f"✅ {name} message is valid")
        return 0
    print(f"❌ {name} message invalid: {msg}", file=sys.stderr)
    return 1


def cmd_kei_dashboard() -> int:
    """Show KEI sandbox audit summary."""
    audit_dir = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data"
    audit_file = audit_dir / "kei_audit.jsonl"
    if not audit_file.exists():
        print("⚠️  No KEI audit data found (runtime/data/kei_audit.jsonl)")
        return 0
    try:
        import json
        total = 0
        actions: dict[str, int] = {}
        statuses: dict[str, int] = {}
        for line in audit_file.read_text().strip().split("\n"):
            if not line:
                continue
            record = json.loads(line)
            total += 1
            a = record.get("action", "unknown")
            actions[a] = actions.get(a, 0) + 1
            s = record.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        print(f"KEI Audit Dashboard")
        print(f"{'='*40}")
        print(f"Total records:  {total}")
        print(f"File:           {audit_file}")
        print()
        if actions:
            print("By action:")
            for action, count in sorted(actions.items()):
                print(f"  {action:20s} {count}")
        if statuses:
            print("\nBy status:")
            for status, count in sorted(statuses.items()):
                print(f"  {status:20s} {count}")
    except Exception as e:
        print(f"❌ Error reading audit log: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_dashboard() -> int:
    """eCOS Dashboard — aggregated system overview."""
    # Services from matrix
    try:
        services = list_services()
    except FileNotFoundError:
        services = []
    active_svc = sum(1 for s in services if s.status == "running")
    failed_svc = sum(1 for s in services if s.status in ("stopped", "failed"))

    # Protocols from L0 registry
    proto_active = sum(1 for p in L0_PROTOCOLS if p.status == "active")
    proto_total = len(L0_PROTOCOLS)

    # Debt from .omo
    debt_dir = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))
    debt_items = list(debt_dir.glob("debt/items/*.yaml")) if debt_dir.exists() else []
    debt_total = len(debt_items)
    debt_open = sum(1 for f in debt_items if "lifecycle_state: scheduled" in f.read_text() or "lifecycle_state: open" in f.read_text())

    # Phase from system state
    phase = "28-W3"
    system_state = debt_dir / "state" / "system.yaml"
    if system_state.exists():
        for line in system_state.read_text().split("\n"):
            if line.startswith("current_phase:"):
                phase = line.split(":", 1)[1].strip()
                break

    print(f"+{'-'*56}+")
    print(f"|  eCOS Dashboard{'':>42}|")
    print(f"|  Phase {phase}{'':>37}|")
    print(f"+{'-'*56}+")
    print(f"|  Services:   {len(services):3d} total ({active_svc:2d} running, {failed_svc:2d} failed){'':>8}|")
    print(f"|  Protocols:  {proto_total:3d} total ({proto_active:2d} active){'':>13}|")
    print(f"|  Debts:      {debt_total:3d} total ({debt_open:2d} pending){'':>13}|")
    print(f"+{'-'*56}+")
    return 0


def cmd_taskobject_dispatch(envelope_file: str) -> int:
    """Dispatch a TaskObject envelope."""
    try:
        if envelope_file == "-":
            import sys as _sys
            payload = json.loads(_sys.stdin.read())
        else:
            payload = json.loads(Path(envelope_file).read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Failed to load envelope: {e}", file=sys.stderr)
        return 1

    from .taskobject_adapter import dispatch_taskobject
    result = dispatch_taskobject(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def cmd_status() -> int:
    try:
        services = list_services()
    except FileNotFoundError:
        services = []
    active = sum(1 for s in services if s.status == "running")
    failed = sum(1 for s in services if s.status in ("stopped", "failed"))
    protocol_active = sum(1 for p in L0_PROTOCOLS if p.status == "active")

    print(f"Runtime CLI     v{__version__}")
    print(f"Matrix          v2 — {RUNTIME_MATRIX}")
    print(f"Services:       {len(services)} total ({active} running, {failed} failed)")
    print(f"Protocols:      {len(L0_PROTOCOLS)} total ({protocol_active} active)")
    return 0


# ─── Main ───────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="runtime",
        description="eCOS Runtime Layer — infrastructure management",
    )
    parser.add_argument("--version", action="version", version=f"runtime {__version__}")

    sub = parser.add_subparsers(dest="command")

    # health
    health_p = sub.add_parser("health", help="Run health scan")
    health_p.add_argument("--json", action="store_true", help="JSON output")

    # matrix
    matrix_p = sub.add_parser("matrix", help="Query service registry")
    matrix_sub = matrix_p.add_subparsers(dest="matrix_cmd")
    matrix_sub.add_parser("list", help="List all services")
    g = matrix_sub.add_parser("get", help="Get service details")
    g.add_argument("name")
    matrix_sub.add_parser("resolve", help="Resolve all env-var paths")

    # service
    svc_p = sub.add_parser("service", help="Manage services")
    svc_p.add_argument("name")
    svc_p.add_argument("action", choices=["status", "start", "stop", "restart"])

    # protocol
    proto_p = sub.add_parser("protocol", help="Query L0 protocol registry")
    proto_sub = proto_p.add_subparsers(dest="proto_cmd")
    proto_sub.add_parser("list", help="List all protocols")
    pg = proto_sub.add_parser("get", help="Get protocol details")
    pg.add_argument("name")
    pv = proto_sub.add_parser("validate", help="Validate a protocol message against registry")
    pv.add_argument("name", help="Protocol name (MCP, ACP, A2A...)")
    pv.add_argument("message", help="JSON message to validate")

    # status
    sub.add_parser("status", help="Quick system summary")

    # dashboard
    sub.add_parser("dashboard", help="eCOS Dashboard — aggregated system health overview")

    # taskobject
    to_p = sub.add_parser("taskobject", help="TaskObject v1 envelope dispatch")
    to_sub = to_p.add_subparsers(dest="to_cmd")
    to_dispatch = to_sub.add_parser("dispatch", help="Dispatch a TaskObject envelope")
    to_dispatch.add_argument("envelope_file", help="Path to JSON envelope file (use '-' for stdin)")

    # mcp
    sub.add_parser("mcp", help="Run L3 CLIAdapter (MCP Server over stdio)")

    # kei
    kei_p = sub.add_parser("kei", help="Kernel Extension Interface (Sandbox) management")
    kei_sub = kei_p.add_subparsers(dest="kei_cmd")
    kei_val = kei_sub.add_parser("validate", help="Validate a KEI manifest")
    kei_val.add_argument("path", help="Path to kei.yaml")
    kei_sub.add_parser("dashboard", help="Show KEI audit summary")

    # i0 fabric
    from .cli_i0 import add_i0_subparser, handle_i0_command
    add_i0_subparser(sub)

    args = parser.parse_args(argv)

    if args.command == "health":
        return cmd_health_json() if args.json else cmd_health()
    elif args.command == "matrix":
        if args.matrix_cmd == "list":
            return cmd_matrix_list()
        elif args.matrix_cmd == "get":
            return cmd_matrix_get(args.name)
        elif args.matrix_cmd == "resolve":
            return cmd_matrix_resolve()
        else:
            matrix_p.print_help()
            return 1
    elif args.command == "service":
        return cmd_service(args.name, args.action)
    elif args.command == "protocol":
        if args.proto_cmd == "list":
            return cmd_protocol_list()
        elif args.proto_cmd == "get":
            return cmd_protocol_get(args.name)
        elif args.proto_cmd == "validate":
            return cmd_protocol_validate(args.name, args.message)
        else:
            proto_p.print_help()
            return 1
    elif args.command == "status":
        return cmd_status()
    elif args.command == "dashboard":
        return cmd_dashboard()
    elif args.command == "taskobject":
        if args.to_cmd == "dispatch":
            return cmd_taskobject_dispatch(args.envelope_file)
        else:
            to_p.print_help()
            return 1
    elif args.command == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main()
        return 0
    elif args.command == "kei":
        if args.kei_cmd == "validate":
            from .kei import load_manifest
            try:
                manifest = load_manifest(args.path)
                print(f"✅ KEI Manifest valid: {manifest.name} v{manifest.version}")
                print(f"  Permissions: {manifest.permissions}")
                return 0
            except Exception as e:
                print(f"❌ KEI Validation failed: {e}", file=sys.stderr)
                return 1
        elif args.kei_cmd == "dashboard":
            return cmd_kei_dashboard()
        else:
            kei_p.print_help()
            return 1
    elif args.command == "i0":
        return handle_i0_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
