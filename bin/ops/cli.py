#!/usr/bin/env python3
"""omostation ops — Service Gateway CLI.

Unified control plane for all omostation services:
    ops status      Show health status of all services
    ops up          Start services (respects dependency order)
    ops down        Stop services (reverse dependency order)
    ops deploy      Generate deployment artifacts
    ops logs        Aggregate logs from all services
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Run: uv pip install pyyaml", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
PORT_REGISTRY = WORKSPACE / "protocols" / "port-registry.yaml"
LOGS_DIR = WORKSPACE / "runtime" / "logs"
PIDS_DIR = WORKSPACE / "runtime" / "pids"


def load_services() -> list[dict[str, Any]]:
    """Load service manifest from services.yaml SSOT (multi-doc with frontmatter)."""
    if not SERVICES_YAML.exists():
        print(f"ERROR: {SERVICES_YAML} not found", file=sys.stderr)
        sys.exit(1)
    content = SERVICES_YAML.read_text(encoding="utf-8")
    # Multi-document YAML (frontmatter + body)
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def load_port_registry() -> dict[str, Any]:
    """Load port registry for conflict detection."""
    if not PORT_REGISTRY.exists():
        return {"ports": {}, "env_vars": {}}
    content = PORT_REGISTRY.read_text(encoding="utf-8")
    return yaml.safe_load(content) or {"ports": {}, "env_vars": {}}


def get_service_by_id(services: list[dict], sid: str) -> dict[str, Any] | None:
    """Find a service by ID."""
    for svc in services:
        if svc.get("id") == sid:
            return svc
    return None


def check_liveness(svc: dict[str, Any]) -> dict[str, Any]:
    """Check liveness signal for a service."""
    liveness = svc.get("liveness", {})
    signal = liveness.get("signal", "")
    max_stale = liveness.get("max_stale_hours", 24)

    result = {
        "status": "unknown",
        "signal": signal,
        "last_seen": None,
        "stale_hours": None,
    }

    if not signal:
        return result

    # HTTP endpoint check
    if liveness.get("signal") == "http" and liveness.get("endpoint"):
        endpoint = liveness["endpoint"]
        try:
            import urllib.request

            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    result["status"] = "healthy"
                    result["last_seen"] = datetime.now(UTC).isoformat()
                else:
                    result["status"] = "unhealthy"
        except Exception:
            result["status"] = "unreachable"
        return result

    # File-based signal check
    if "::" in signal:
        file_path, attr = signal.split("::", 1)
        fp = WORKSPACE / file_path
        if fp.exists():
            try:
                content = fp.read_text()
                data = yaml.safe_load(content)
                if isinstance(data, dict) and attr in data:
                    ts_str = data[attr]
                    result["last_seen"] = ts_str
                    # Parse timestamp
                    try:
                        if isinstance(ts_str, str):
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            now = datetime.now(UTC)
                            stale = (now - ts).total_seconds() / 3600
                            result["stale_hours"] = round(stale, 1)
                            result["status"] = "healthy" if stale < max_stale else "stale"
                        else:
                            result["status"] = "healthy"
                    except (ValueError, TypeError):
                        result["status"] = "healthy"
                else:
                    result["status"] = "stale"
            except Exception:
                result["status"] = "error"
        else:
            result["status"] = "missing"
    else:
        # Simple file existence check
        fp = WORKSPACE / signal
        if fp.exists():
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=UTC)
            now = datetime.now(UTC)
            stale = (now - mtime).total_seconds() / 3600
            result["last_seen"] = mtime.isoformat()
            result["stale_hours"] = round(stale, 1)
            result["status"] = "healthy" if stale < max_stale else "stale"
        else:
            result["status"] = "missing"

    return result


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of all services."""
    services = load_services()
    if not services:
        print("No services registered.")
        return 0

    output_json = getattr(args, "json", False)

    # Group by type
    groups: dict[str, list[dict]] = {}
    for svc in services:
        svc_type = svc.get("scheduler", "unknown")
        groups.setdefault(svc_type, []).append(svc)

    rows = []
    total = 0
    healthy = 0
    stale = 0
    missing = 0
    disabled = 0

    for svc_type, svcs in sorted(groups.items()):
        for svc in svcs:
            total += 1
            sid = svc.get("id", "?")
            enabled = svc.get("enabled", False)

            if not enabled:
                status = "disabled"
                disabled += 1
                running = False
            else:
                liv = check_liveness(svc)
                status = liv["status"]
                running = _is_running(svc)
                if status == "healthy":
                    healthy += 1
                elif status in ("stale", "missing"):
                    stale += 1
                else:
                    missing += 1

            port = svc.get("ports", [])
            port_str = ",".join(str(p) for p in port) if port else "-"

            rows.append(
                {
                    "id": sid,
                    "type": svc_type,
                    "enabled": enabled,
                    "status": status,
                    "running": running,
                    "port": port_str,
                }
            )

    if output_json:
        print(
            json.dumps(
                {
                    "summary": {
                        "total": total,
                        "healthy": healthy,
                        "stale": stale,
                        "missing": missing,
                        "disabled": disabled,
                    },
                    "services": rows,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        # Rich table output
        try:
            from rich import box
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(
                title=f"omostation ops — Service Status ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
                box=box.ROUNDED,
                show_lines=False,
            )
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Type", style="dim")
            table.add_column("Status", justify="center")
            table.add_column("Running", justify="center")
            table.add_column("Port", justify="center")

            status_styles = {
                "healthy": "[green]● healthy[/]",
                "stale": "[yellow]● stale[/]",
                "missing": "[red]● missing[/]",
                "unreachable": "[red]● unreachable[/]",
                "disabled": "[dim]○ disabled[/]",
                "unknown": "[dim]? unknown[/]",
                "error": "[red]✗ error[/]",
            }

            for row in rows:
                running_str = "[green]✓[/]" if row.get("running") else "[dim]-[/]"
                table.add_row(
                    row["id"],
                    row["type"],
                    status_styles.get(row["status"], row["status"]),
                    running_str,
                    row["port"],
                )

            console.print(table)
            console.print(
                f"\n[bold]Summary:[/] "
                f"[green]{healthy} healthy[/] · "
                f"[yellow]{stale} stale[/] · "
                f"[red]{missing} missing[/] · "
                f"[dim]{disabled} disabled[/] · "
                f"total {total}"
            )
        except ImportError:
            # Fallback to plain text
            print(f"{'ID':<40} {'Type':<12} {'Status':<12} {'Port':<10}")
            print("-" * 74)
            for row in rows:
                print(f"{row['id']:<40} {row['type']:<12} {row['status']:<12} {row['port']:<10}")
            print(
                f"\nSummary: {healthy} healthy · {stale} stale · {missing} missing · {disabled} disabled · total {total}"
            )

    return 0 if missing == 0 and stale == 0 else 1


def _get_cmd(svc: dict) -> list[str]:
    """Build command list from service definition."""
    program = svc.get("program", {})
    entry = program.get("entrypoint", "")
    interpreter = program.get("interpreter", "python3")
    svc_args = program.get("args", [])
    if interpreter == "uv":
        return ["uv", "run", entry] + svc_args
    elif interpreter == "stable-python3":
        return [sys.executable, entry] + svc_args
    elif interpreter.startswith("/"):
        return [interpreter, entry] + svc_args
    else:
        return [interpreter, entry] + svc_args


def _get_pid_file(sid: str) -> Path:
    """Get PID file path for a service."""
    PIDS_DIR.mkdir(parents=True, exist_ok=True)
    return PIDS_DIR / f"{sid}.pid"


def _is_running(svc: dict) -> bool:
    """Check if a service is running via PID file."""
    sid = svc.get("id", "")
    pid_file = _get_pid_file(sid)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        return False


def topological_sort(services: list[dict]) -> list[list[str]]:
    """Topological sort by depends_on (Kahn's algorithm). Returns layers."""
    sid_to_svc = {s["id"]: s for s in services if "id" in s}
    in_degree: dict[str, int] = {s["id"]: 0 for s in services if "id" in s}
    dependents: dict[str, list[str]] = {s["id"]: [] for s in services if "id" in s}

    for svc in services:
        sid = svc.get("id")
        if not sid:
            continue
        for dep in svc.get("depends_on", []):
            if dep in sid_to_svc:
                dependents[dep].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

    layers: list[list[str]] = []
    queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])

    while queue:
        layers.append(queue)
        next_queue: list[str] = []
        for sid in queue:
            for dep in dependents.get(sid, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_queue.append(dep)
        queue = sorted(next_queue)

    return layers


def cmd_up(args: argparse.Namespace) -> int:
    """Start services (respects dependency order via DAG)."""
    import subprocess as sp

    services = load_services()
    target = getattr(args, "service", None)
    dry_run = getattr(args, "dry_run", False)

    if target:
        svc = get_service_by_id(services, target)
        if not svc:
            print(f"ERROR: service '{target}' not found", file=sys.stderr)
            return 1
        if _is_running(svc):
            print(f"Service '{target}' already running")
            return 0
        cmd = _get_cmd(svc)
        if dry_run:
            print(f"[DRY-RUN] {target}: {' '.join(cmd)}")
            return 0
        try:
            log_file = LOGS_DIR / f"{target}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as lf:
                proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True)
            _get_pid_file(target).write_text(str(proc.pid))
            print(f"Started {target} (pid={proc.pid})")
            return 0
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    # Start all enabled services in DAG order
    enabled = [s for s in services if s.get("enabled", False)]
    layers = topological_sort(enabled)
    total = sum(len(l) for l in layers)

    if dry_run:
        print(f"[DRY-RUN] Starting {total} services in {len(layers)} layers:")
        for i, layer in enumerate(layers, 1):
            print(f"  Layer {i}: {', '.join(layer)}")
        return 0

    print(f"Starting {total} services in {len(layers)} layers (DAG order)...\n")
    started = skipped = failed = 0
    for i, layer in enumerate(layers, 1):
        print(f"  Layer {i}:")
        for sid in layer:
            svc = get_service_by_id(enabled, sid)
            if not svc:
                continue
            if _is_running(svc):
                print(f"    [SKIP] {sid} (running)")
                skipped += 1
                continue
            cmd = _get_cmd(svc)
            try:
                log_file = LOGS_DIR / f"{sid}.log"
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a") as lf:
                    proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True)
                _get_pid_file(sid).write_text(str(proc.pid))
                print(f"    [START] {sid} (pid={proc.pid})")
                started += 1
            except Exception as e:
                print(f"    [FAIL] {sid}: {e}")
                failed += 1
        print()
    print(f"Summary: {started} started, {skipped} skipped, {failed} failed")
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    """Stop services (reverse dependency order)."""
    services = load_services()
    target = getattr(args, "service", None)

    if target:
        svc = get_service_by_id(services, target)
        if not svc:
            print(f"ERROR: service '{target}' not found", file=sys.stderr)
            return 1
        pid_file = _get_pid_file(target)
        if not pid_file.exists():
            print(f"Service '{target}' not running")
            return 0
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            pid_file.unlink(missing_ok=True)
            print(f"Stopped {target} (pid={pid})")
        except (ValueError, OSError, ProcessLookupError) as e:
            print(f"Error stopping {target}: {e}")
            pid_file.unlink(missing_ok=True)
        return 0

    # Stop all enabled services in reverse DAG order
    enabled = [s for s in services if s.get("enabled", False)]
    layers = topological_sort(enabled)
    total = sum(len(l) for l in layers)

    print(f"Stopping {total} services in {len(layers)} layers (reverse DAG order)...\n")
    stopped = skipped = failed = 0
    for i, layer in enumerate(reversed(layers), 1):
        print(f"  Layer {len(layers) - i + 1}:")
        for sid in layer:
            svc = get_service_by_id(enabled, sid)
            if not svc:
                continue
            pid_file = _get_pid_file(sid)
            if not pid_file.exists():
                print(f"    [SKIP] {sid} (not running)")
                skipped += 1
                continue
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 15)
                pid_file.unlink(missing_ok=True)
                print(f"    [STOP] {sid} (pid={pid})")
                stopped += 1
            except (ValueError, OSError, ProcessLookupError) as e:
                print(f"    [FAIL] {sid}: {e}")
                pid_file.unlink(missing_ok=True)
                failed += 1
        print()
    print(f"Summary: {stopped} stopped, {skipped} skipped, {failed} failed")
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    """Generate deployment artifacts."""
    services = load_services()
    profile = getattr(args, "profile", "full")

    print(f"Generating deployment artifacts (profile: {profile})...")
    print(f"  Services registered: {len(services)}")
    print(f"  Enabled: {sum(1 for s in services if s.get('enabled'))}")
    print()
    print("Deployment targets:")
    for svc in services:
        if not svc.get("enabled"):
            continue
        sid = svc.get("id", "?")
        scheduler = svc.get("scheduler", "?")
        port = svc.get("ports", [])
        port_str = f" (ports: {port})" if port else ""
        print(f"  - {sid}: {scheduler}{port_str}")

    print()
    print("To deploy to a new machine:")
    print("  1. git clone --recurse-submodules git@github.com:starlink-awaken/omostation.git")
    print("  2. cd omostation")
    print("  3. uv run python -m bin.ops.cli up")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Show aggregated logs."""
    service = getattr(args, "service", None)
    lines = getattr(args, "lines", 50)

    if service:
        # Show logs for specific service
        log_files = list(LOGS_DIR.glob(f"*{service}*.log"))
        if not log_files:
            print(f"No logs found for service '{service}'")
            return 1
        for lf in log_files:
            print(f"\n=== {lf.name} ===")
            try:
                content = lf.read_text()
                log_lines = content.splitlines()[-lines:]
                print("\n".join(log_lines))
            except Exception as e:
                print(f"Error reading {lf}: {e}")
    else:
        # Show all recent logs
        if not LOGS_DIR.exists():
            print(f"Logs directory not found: {LOGS_DIR}")
            return 1
        log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"Available logs ({len(log_files)} files):")
        for lf in log_files[:20]:
            size = lf.stat().st_size
            mtime = datetime.fromtimestamp(lf.stat().st_mtime).strftime("%m-%d %H:%M")
            print(f"  {mtime} {lf.name} ({size:,} bytes)")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ops",
        description="omostation Service Gateway — unified control plane",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── status ──
    status_p = sub.add_parser("status", help="Show service health status")
    status_p.add_argument("--json", action="store_true", help="Output as JSON")
    status_p.set_defaults(func=cmd_status)

    # ── up ──
    up_p = sub.add_parser("up", help="Start services")
    up_p.add_argument("service", nargs="?", help="Specific service to start")
    up_p.add_argument("--dry-run", action="store_true", help="Show what would be started")
    up_p.set_defaults(func=cmd_up)

    # ── down ──
    down_p = sub.add_parser("down", help="Stop services")
    down_p.add_argument("service", nargs="?", help="Specific service to stop")
    down_p.add_argument("--dry-run", action="store_true", help="Show what would be stopped")
    down_p.set_defaults(func=cmd_down)

    # ── deploy ──
    deploy_p = sub.add_parser("deploy", help="Generate deployment info")
    deploy_p.add_argument("--profile", choices=["minimal", "full"], default="full")
    deploy_p.set_defaults(func=cmd_deploy)

    # ── logs ──
    logs_p = sub.add_parser("logs", help="Show service logs")
    logs_p.add_argument("service", nargs="?", help="Filter by service name")
    logs_p.add_argument("-n", "--lines", type=int, default=50, help="Number of lines")
    logs_p.set_defaults(func=cmd_logs)

    # ── deps ──
    deps_p = sub.add_parser("deps", help="Show service dependency graph (DAG)")
    deps_p.add_argument("service", nargs="?", help="Show dependencies for specific service")
    deps_p.set_defaults(func=cmd_deps)

    # ── summary ──
    summary_p = sub.add_parser("summary", help="Show system summary")
    summary_p.set_defaults(func=cmd_summary)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


def cmd_summary(args: argparse.Namespace) -> int:
    """Show system summary."""
    services = load_services()
    if not services:
        print("No services registered.")
        return 0

    # Count by type
    groups: dict[str, list[dict]] = {}
    for svc in services:
        t = svc.get("scheduler", "unknown")
        groups.setdefault(t, []).append(svc)

    enabled = [s for s in services if s.get("enabled", False)]
    running = [s for s in enabled if _is_running(s)]
    has_liveness = sum(1 for s in enabled if s.get("liveness"))
    has_depends = sum(1 for s in enabled if s.get("depends_on"))
    has_ports = sum(1 for s in enabled if s.get("ports"))

    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        table = Table(title="omostation Service Gateway — Summary", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total services", str(len(services)))
        table.add_row("Enabled", str(len(enabled)))
        table.add_row("Running", str(len(running)))
        table.add_row("Health checks", f"{has_liveness}/{len(enabled)} ({has_liveness*100//len(enabled)}%)")
        table.add_row("Dependencies", f"{has_depends}/{len(enabled)} ({has_depends*100//len(enabled)}%)")
        table.add_row("Ports", f"{has_ports}/{len(enabled)} ({has_ports*100//len(enabled)}%)")

        console.print(table)

        # Type breakdown
        type_table = Table(title="Services by Type", box=box.SIMPLE)
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", justify="right")
        for t, svcs in sorted(groups.items(), key=lambda x: -len(x[1])):
            type_table.add_row(t, str(len(svcs)))
        console.print(type_table)

    except ImportError:
        print(f"Total services: {len(services)}")
        print(f"Enabled: {len(enabled)}")
        print(f"Running: {len(running)}")
        print(f"Health checks: {has_liveness}/{len(enabled)} ({has_liveness*100//len(enabled)}%)")
        print(f"Dependencies: {has_depends}/{len(enabled)} ({has_depends*100//len(enabled)}%)")
        print(f"Ports: {has_ports}/{len(enabled)} ({has_ports*100//len(enabled)}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
