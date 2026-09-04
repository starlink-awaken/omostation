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
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
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
LIVENESS_MAX_WORKERS = 64
LIVENESS_BATCH_TIMEOUT_SECONDS = 5.0
LIVENESS_PROBE_TIMEOUT_SECONDS = 0.5

# ── Service Profiles ──
# Define which services belong to each profile
SERVICE_PROFILES: dict[str, set[str]] = {
    "minimal": {
        # Core infrastructure
        "omo.sync_daemon",
        "resident.orchestrator",
        "resident.heartbeat",
        "gac.daemon_watchdog",
        # Essential cron
        "cron.capability_ownership",
        "cron.agent_workflow_status",
        "cron.meta_doctor",
        # Core MCP
        "mcp.agora",
        # Essential CLI
        "cli.cockpit",
        "cli.omo",
    },
    "standard": {
        # Include minimal + standard services
        "omo.sync_daemon",
        "resident.orchestrator",
        "resident.heartbeat",
        "resident.sediment",
        "resident.monitor",
        "gac.daemon_watchdog",
        "cockpit.dashboard",
        # Cron
        "cron.capability_ownership",
        "cron.agent_workflow_status",
        "cron.meta_doctor",
        "cron.governance_evolution",
        "cron.m4_health",
        "cron.debt_refresh",
        # MCP
        "mcp.agora",
        "mcp.kos",
        "mcp.minerva",
        # CLI
        "cli.cockpit",
        "cli.omo",
        "cli.kos",
    },
    "full": None,  # All enabled services
}


def get_profile_services(profile: str, all_services: list[dict]) -> list[dict]:
    """Get services belonging to a profile."""
    if profile == "full" or profile not in SERVICE_PROFILES:
        return [s for s in all_services if s.get("enabled", False)]

    profile_ids = SERVICE_PROFILES[profile]
    if profile_ids is None:
        return [s for s in all_services if s.get("enabled", False)]

    return [s for s in all_services if s.get("id") in profile_ids and s.get("enabled", False)]


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


def check_liveness(svc: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    """Check liveness signal for a service (HTTP/TCP/Docker/PID/File)."""
    liveness = svc.get("liveness", {})
    signal = liveness.get("signal", "")
    max_stale = liveness.get("max_stale_hours", 24)
    probe_timeout = max(0.001, float(timeout if timeout is not None else 5.0))

    result: dict[str, Any] = {
        "status": "unknown",
        "signal": signal,
        "last_seen": None,
        "stale_hours": None,
    }

    if not signal:
        return result

    # ── HTTP endpoint check ──
    if signal == "http" and liveness.get("endpoint"):
        endpoint = liveness["endpoint"]
        try:
            import urllib.request
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                if resp.status == 200:
                    result["status"] = "healthy"
                    result["last_seen"] = datetime.now(UTC).isoformat()
                else:
                    result["status"] = "unhealthy"
                    result["http_status"] = resp.status
        except Exception as e:
            result["status"] = "unreachable"
            result["error"] = str(e)[:100]
        return result

    # ── TCP port check ──
    if signal == "tcp":
        port = liveness.get("port") or (svc.get("ports", [None])[0] if svc.get("ports") else None)
        if port:
            import socket
            try:
                with socket.create_connection(("127.0.0.1", int(port)), timeout=probe_timeout):
                    result["status"] = "healthy"
                    result["last_seen"] = datetime.now(UTC).isoformat()
            except OSError as e:
                result["status"] = "unreachable"
                result["error"] = str(e)[:100]
        else:
            result["status"] = "no_port"
        return result

    # ── Docker container check ──
    if signal == "docker":
        label = liveness.get("label") or svc.get("label", "")
        if label:
            import subprocess as sp
            try:
                proc = sp.run(
                    ["docker", "ps", "--filter", f"name={label}", "--format", "{{.Status}}"],
                    capture_output=True, text=True, timeout=probe_timeout,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    status_str = proc.stdout.strip().lower()
                    if "up" in status_str:
                        result["status"] = "healthy"
                        result["last_seen"] = datetime.now(UTC).isoformat()
                        result["docker_status"] = status_str
                    else:
                        result["status"] = "unhealthy"
                        result["docker_status"] = status_str
                else:
                    result["status"] = "missing"
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)[:100]
        else:
            result["status"] = "no_label"
        return result

    # ── Process check (PID file) ──
    if signal == "pid":
        pid_file = _get_pid_file(svc.get("id", ""))
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                result["status"] = "healthy"
                result["pid"] = pid
                result["last_seen"] = datetime.now(UTC).isoformat()
            except (ValueError, OSError, ProcessLookupError):
                result["status"] = "stale"
                pid_file.unlink(missing_ok=True)
        else:
            result["status"] = "missing"
        return result

    # ── File-based signal check ──
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


def collect_liveness(
    services: list[dict[str, Any]],
    *,
    total_timeout: float = LIVENESS_BATCH_TIMEOUT_SECONDS,
    probe_timeout: float = LIVENESS_PROBE_TIMEOUT_SECONDS,
    max_workers: int = LIVENESS_MAX_WORKERS,
) -> dict[str, dict[str, Any]]:
    """Collect read-only liveness results within a finite batch budget.

    Results are rebuilt in input order so callers remain deterministic even
    though probes execute concurrently.  A timeout is an explicit degraded
    result, never a healthy result.
    """
    if not services:
        return {}

    ordered_ids = [str(service.get("id", "?")) for service in services]
    results: dict[str, dict[str, Any]] = {}
    worker_count = max(1, min(int(max_workers), len(services)))
    executor = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ops-liveness")
    futures = {
        executor.submit(check_liveness, service, timeout=probe_timeout): str(service.get("id", "?"))
        for service in services
    }
    try:
        try:
            for future in as_completed(futures, timeout=max(0.001, float(total_timeout))):
                service_id = futures[future]
                try:
                    results[service_id] = future.result()
                except Exception as exc:  # defensive observer boundary
                    results[service_id] = {
                        "status": "error",
                        "error": str(exc)[:100],
                    }
        except FuturesTimeoutError:
            pass
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    for service_id in ordered_ids:
        results.setdefault(
            service_id,
            {"status": "timeout", "error": "liveness_budget_exhausted"},
        )
    return {service_id: results[service_id] for service_id in ordered_ids}


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

    enabled_services = [
        svc
        for service_group in groups.values()
        for svc in service_group
        if svc.get("enabled", False)
    ]
    liveness_by_id = collect_liveness(enabled_services)

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
                liv = liveness_by_id.get(sid, {"status": "timeout"})
                status = liv["status"]
                running = _is_running(svc)
                if status == "healthy":
                    healthy += 1
                elif status in ("stale", "missing", "timeout"):
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
                "timeout": "[yellow]● timeout[/]",
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
        entry_path = Path(entry)
        if not entry_path.is_absolute():
            entry_path = WORKSPACE / entry_path
        if entry_path.is_dir():
            return ["uv", "run", "--directory", entry] + svc_args
        return ["uv", "run", entry] + svc_args
    elif interpreter == "stable-python3":
        return [sys.executable, entry] + svc_args
    elif interpreter.startswith("/"):
        return [interpreter, entry] + svc_args
    else:
        return [interpreter, entry] + svc_args


def _get_environment(svc: dict) -> dict[str, str] | None:
    """Build a child-only environment from a service declaration."""
    declared = svc.get("environment")
    if not isinstance(declared, dict) or not declared:
        return None
    environment = os.environ.copy()
    environment.update({str(key): str(value) for key, value in declared.items()})
    return environment


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
    profile = getattr(args, "profile", "full")

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
                proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True, env=_get_environment(svc))
            _get_pid_file(target).write_text(str(proc.pid))
            print(f"Started {target} (pid={proc.pid})")
            return 0
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    # Start services in DAG order (filtered by profile)
    enabled = get_profile_services(profile, services)
    layers = topological_sort(enabled)
    total = sum(len(l) for l in layers)
    print(f"Profile: {profile} ({len(enabled)} services)")

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
                    proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True, env=_get_environment(svc))
                _get_pid_file(sid).write_text(str(proc.pid))
                print(f"    [START] {sid} (pid={proc.pid})")
                started += 1
            except Exception as e:
                print(f"    [FAIL] {sid}: {e}")
                failed += 1
        print()
    print(f"Summary: {started} started, {skipped} skipped, {failed} failed")
    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    """Show service dependency graph (DAG)."""
    services = load_services()
    target = getattr(args, "service", None)

    if target:
        svc = get_service_by_id(services, target)
        if not svc:
            print(f"ERROR: service '{target}' not found", file=sys.stderr)
            return 1
        deps = svc.get("depends_on", [])
        print(f"{target} ({svc.get('type', 'unknown')})")
        if deps:
            print(f"  depends on: {', '.join(deps)}")
        else:
            print("  no dependencies")
        # Show reverse deps (who depends on this)
        reverse = [s["id"] for s in services if target in s.get("depends_on", [])]
        if reverse:
            print(f"  depended by: {', '.join(reverse)}")
        return 0

    # Show full DAG
    enabled = [s for s in services if s.get("enabled", False)]
    layers = topological_sort(enabled)
    print(f"Service DAG: {len(enabled)} services in {len(layers)} layers\n")
    for i, layer in enumerate(layers, 1):
        print(f"  Layer {i}:")
        for sid in layer:
            svc = get_service_by_id(enabled, sid)
            if not svc:
                continue
            deps = svc.get("depends_on", [])
            dep_str = f" ← {', '.join(deps)}" if deps else ""
            print(f"    {sid}{dep_str}")
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
    up_p.add_argument("--profile", choices=["minimal", "standard", "full"], default="full",
                      help="Service profile (default: full)")
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

    # ── metrics ──
    metrics_p = sub.add_parser("metrics", help="Export Prometheus metrics")
    metrics_p.add_argument("--port", type=int, default=9090, help="Metrics server port (default: 9090)")
    metrics_p.add_argument("--text", action="store_true", help="Output text format (default: serve HTTP)")
    metrics_p.set_defaults(func=cmd_metrics)

    # ── template ──
    template_p = sub.add_parser("template", help="Service templates")
    template_p.add_argument("template_action", nargs="?", default="list",
                            choices=["list", "apply"],
                            help="Template action (default: list)")
    template_p.add_argument("--name", help="Service name for apply")
    template_p.add_argument("--type", choices=["daemon", "cron", "mcp", "cli", "docker"],
                            default="daemon", help="Service type")
    template_p.add_argument("--entrypoint", help="Entrypoint path")
    template_p.add_argument("--interval", type=int, help="Interval in seconds (daemon)")
    template_p.add_argument("--schedule", help="Cron schedule (cron)")
    template_p.set_defaults(func=cmd_template)

    # ── batch ──
    batch_p = sub.add_parser("batch", help="Batch operations")
    batch_p.add_argument("batch_action", choices=["up", "down", "status"],
                        help="Batch action")
    batch_p.add_argument("services", nargs="+", help="Service IDs")
    batch_p.set_defaults(func=cmd_batch)

    # ── drift ──
    drift_p = sub.add_parser("drift", help="Configuration drift detection")
    drift_p.add_argument("--fix", action="store_true", help="Auto-fix drift where possible")
    drift_p.set_defaults(func=cmd_drift)

    # ── catalog ──
    catalog_p = sub.add_parser("catalog", help="Service catalog (search & filter)")
    catalog_p.add_argument("query", nargs="?", help="Search query")
    catalog_p.add_argument("--type", choices=["launchd", "cron", "manual", "docker", "gha"],
                          help="Filter by scheduler type")
    catalog_p.add_argument("--status", choices=["healthy", "stale", "missing", "disabled"],
                          help="Filter by health status")
    catalog_p.add_argument("--format", choices=["table", "json", "csv"], default="table",
                          help="Output format")
    catalog_p.set_defaults(func=cmd_catalog)

    # ── graph ──
    graph_p = sub.add_parser("graph", help="Visual dependency graph (DOT format)")
    graph_p.add_argument("--format", choices=["dot", "svg", "png"], default="dot",
                         help="Output format (default: dot)")
    graph_p.add_argument("--output", "-o", help="Output file (default: stdout)")
    graph_p.add_argument("--profile", choices=["minimal", "standard", "full"], default="full",
                         help="Service profile")
    graph_p.set_defaults(func=cmd_graph)

    # ── score ──
    score_p = sub.add_parser("score", help="System health score (0-100)")
    score_p.add_argument("--format", choices=["text", "json"], default="text",
                         help="Output format")
    score_p.set_defaults(func=cmd_score)

    # ── history ──
    history_p = sub.add_parser("history", help="Service health history")
    history_p.add_argument("service", nargs="?", help="Specific service to view")
    history_p.add_argument("--days", type=int, default=7, help="Days of history (default: 7)")
    history_p.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    history_p.set_defaults(func=cmd_history)

    # ── discover ──
    discover_p = sub.add_parser("discover", help="Auto-discover running services")
    discover_p.add_argument("--update", action="store_true", help="Update services.yaml with discoveries")
    discover_p.set_defaults(func=cmd_discover)

    # ── validate ──
    validate_p = sub.add_parser("validate", help="Validate service configuration")
    validate_p.add_argument("service", nargs="?", help="Specific service to validate")
    validate_p.set_defaults(func=cmd_validate)

    # ── generate ──
    generate_p = sub.add_parser("generate", help="Generate deployment configs")
    generate_p.add_argument("--format", choices=["docker-compose", "systemd", "launchd"], default="docker-compose")
    generate_p.add_argument("--output", "-o", help="Output file path")
    generate_p.set_defaults(func=cmd_generate)

    # ── recover ──
    recover_p = sub.add_parser("recover", help="Auto-recover failed services")
    recover_p.add_argument("--profile", choices=["minimal", "standard", "full"], default="full",
                           help="Service profile (default: full)")
    recover_p.set_defaults(func=cmd_recover)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


def cmd_discover(args: argparse.Namespace) -> int:
    """Auto-discover running services."""
    import re
    import subprocess as sp

    services = load_services()
    existing_ids = {s["id"] for s in services}

    discovered: list[dict[str, Any]] = []

    # Discover listening ports
    try:
        proc = sp.run(["lsof", "-i", "-P", "-n"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 9 and "LISTEN" in parts[9]:
                    pid = parts[1]
                    port_match = re.search(r":(\d+)", parts[8])
                    if port_match:
                        port = int(port_match.group(1))
                        # Try to get process name
                        ps_proc = sp.run(["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True, timeout=5)
                        name = ps_proc.stdout.strip() if ps_proc.returncode == 0 else "unknown"
                        discovered.append({"type": "port", "port": port, "pid": pid, "name": name})
    except Exception:
        pass

    # Discover running processes matching known patterns
    known_patterns = ["python3", "uv", "node", "docker", "nginx", "postgres"]
    for svc in services:
        sid = svc.get("id", "")
        program = svc.get("program", {})
        entry = program.get("entrypoint", "")
        if entry:
            # Check if process is running
            ps_proc = sp.run(["pgrep", "-f", entry], capture_output=True, text=True, timeout=5)
            if ps_proc.returncode == 0:
                pids = ps_proc.stdout.strip().split("\n")
                discovered.append({"type": "process", "id": sid, "pids": pids, "entry": entry})

    # Print discoveries
    print(f"Discovered {len(discovered)} running services:\n")
    for d in discovered:
        if d["type"] == "port":
            print(f"  [PORT] :{d['port']} (pid={d['pid']}, name={d['name']})")
        elif d["type"] == "process":
            print(f"  [PROC] {d['id']} (pids={', '.join(d['pids'])})")

    # Update services.yaml if requested
    if args.update:
        added = 0
        for d in discovered:
            if d["type"] == "port":
                sid = f"discovered.port.{d['port']}"
                if sid not in existing_ids:
                    services.append({
                        "id": sid,
                        "enabled": False,
                        "scheduler": "manual",
                        "trigger": "on_demand",
                        "ports": [d["port"]],
                        "program": {"interpreter": d["name"], "entrypoint": f":{d['port']}"},
                        "notes": f"Auto-discovered on port {d['port']}",
                    })
                    added += 1
        if added:
            # Write back
            for doc in [services]:
                pass  # services is already the list
            # Find the services doc and update
            content = SERVICES_YAML.read_text()
            docs = list(yaml.safe_load_all(content))
            for doc in docs:
                if isinstance(doc, dict) and "services" in doc:
                    doc["services"] = services
                    break
            output = []
            for doc in docs:
                output.append(yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False))
            SERVICES_YAML.write_text("---\n".join(output))
            print(f"\nAdded {added} discovered services to services.yaml")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate service configuration."""
    services = load_services()
    target = args.service

    to_validate = services
    if target:
        svc = get_service_by_id(services, target)
        if not svc:
            print(f"ERROR: service '{target}' not found", file=sys.stderr)
            return 1
        to_validate = [svc]

    issues: list[str] = []
    for svc in to_validate:
        sid = svc.get("id", "")
        program = svc.get("program", {})
        entry = program.get("entrypoint", "")
        interpreter = program.get("interpreter", "")

        # Check entrypoint exists
        if entry and not entry.startswith("projects/") and not entry.startswith("bin/"):
            if not (WORKSPACE / entry).exists() and not Path(entry).exists():
                issues.append(f"[{sid}] entrypoint not found: {entry}")

        # Check interpreter exists
        if interpreter == "uv":
            import shutil
            if not shutil.which("uv"):
                issues.append(f"[{sid}] interpreter not found: uv")
        elif interpreter and not interpreter.startswith("/") and interpreter != "stable-python3":
            import shutil
            if not shutil.which(interpreter):
                issues.append(f"[{sid}] interpreter not found: {interpreter}")

        # Check ports are not conflicting
        ports = svc.get("ports", [])
        for other in services:
            if other.get("id") == sid:
                continue
            other_ports = other.get("ports", [])
            for p in ports:
                if p in other_ports:
                    issues.append(f"[{sid}] port conflict: {p} also used by {other.get('id')}")

    if issues:
        print(f"Found {len(issues)} configuration issues:\n")
        for issue in issues:
            print(f"  ⚠️  {issue}")
        return 1
    else:
        print(f"Configuration valid ({len(to_validate)} services checked)")
        return 0


def cmd_recover(args: argparse.Namespace) -> int:
    """Auto-recover failed services (restart unhealthy ones)."""
    import subprocess as sp

    services = load_services()
    profile = getattr(args, "profile", "full")
    to_check = get_profile_services(profile, services)

    recovered = 0
    skipped = 0
    failed = 0

    print(f"Checking {len(to_check)} services for recovery...\n")

    for svc in to_check:
        sid = svc.get("id", "")
        liv = check_liveness(svc)

        if liv["status"] in ("healthy", "disabled"):
            skipped += 1
            continue

        # Try to restart
        cmd = _get_cmd(svc)
        try:
            log_file = LOGS_DIR / f"{sid}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as lf:
                        proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True, env=_get_environment(svc))
            _get_pid_file(sid).write_text(str(proc.pid))
            print(f"  [RECOVER] {sid} (pid={proc.pid}, was {liv['status']})")
            recovered += 1
        except Exception as e:
            print(f"  [FAIL] {sid}: {e}")
            failed += 1

    print(f"\nSummary: {recovered} recovered, {skipped} healthy, {failed} failed")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate deployment configs (docker-compose/systemd/launchd)."""
    services = load_services()
    fmt = args.format
    output = args.output

    enabled = [s for s in services if s.get("enabled", False)]

    lines: list[str] = []

    if fmt == "docker-compose":
        lines.append("version: '3.8'")
        lines.append("services:")
        for svc in enabled[:20]:  # Limit to first 20 for readability
            sid = svc.get("id", "").replace(".", "-")
            ports = svc.get("ports", [])
            port_str = "\n".join(f"      - {p}:{p}" for p in ports) if ports else ""
            lines.append(f"  {sid}:")
            lines.append(f"    image: omostation/{sid}:latest")
            if port_str:
                lines.append(f"    ports:{port_str}")
            lines.append("    restart: unless-stopped")
            lines.append("")
    elif fmt == "systemd":
        for svc in enabled[:10]:
            sid = svc.get("id", "").replace(".", "-")
            entry = svc.get("program", {}).get("entrypoint", "")
            lines.append("[Unit]")
            lines.append(f"Description=omostation {sid}")
            lines.append("After=network.target")
            lines.append("")
            lines.append("[Service]")
            lines.append("Type=simple")
            lines.append(f"ExecStart=/usr/bin/env {entry}")
            lines.append(f"WorkingDirectory={WORKSPACE}")
            lines.append("Restart=on-failure")
            lines.append("")
            lines.append("[Install]")
            lines.append("WantedBy=multi-user.target")
            lines.append("")
    elif fmt == "launchd":
        for svc in enabled[:10]:
            sid = svc.get("id", "").replace(".", "_")
            entry = svc.get("program", {}).get("entrypoint", "")
            lines.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
            lines.append("<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">")
            lines.append("<plist version=\"1.0\">")
            lines.append("<dict>")
            lines.append("    <key>Label</key>")
            lines.append(f"    <string>com.omostation.{sid}</string>")
            lines.append("    <key>ProgramArguments</key>")
            lines.append("    <array>")
            lines.append("        <string>/usr/bin/env</string>")
            lines.append(f"        <string>{entry}</string>")
            lines.append("    </array>")
            lines.append("    <key>WorkingDirectory</key>")
            lines.append(f"    <string>{WORKSPACE}</string>")
            lines.append("    <key>RunAtLoad</key>")
            lines.append("    <true/>")
            lines.append("    <key>KeepAlive</key>")
            lines.append("    <true/>")
            lines.append("</dict>")
            lines.append("</plist>")
            lines.append("")

    content = "\n".join(lines)
    if output:
        Path(output).write_text(content)
        print(f"Generated {fmt} config: {output}")
    else:
        print(content)

    return 0


def cmd_template(args: argparse.Namespace) -> int:
    """Service template management."""
    action = args.template_action

    if action == "list":
        templates = {
            "daemon": {
                "scheduler": "launchd",
                "trigger": "interval",
                "program": {"interpreter": "stable-python3", "entrypoint": "bin/examples/<name>.py"},
                "resilience": {"keepalive": "crashed", "throttle_interval": 60},
            },
            "cron": {
                "scheduler": "cron",
                "trigger": "schedule",
                "program": {"interpreter": "stable-python3", "entrypoint": "bin/examples/<name>.py"},
            },
            "mcp": {
                "scheduler": "manual",
                "trigger": "on_demand",
                "transport": "stdio",
                "program": {"interpreter": "uv", "entrypoint": "projects/agora"},
            },
            "cli": {
                "scheduler": "manual",
                "trigger": "on_demand",
                "program": {"interpreter": "uv", "entrypoint": "projects/cockpit"},
            },
            "docker": {
                "scheduler": "docker",
                "trigger": "compose",
                "program": {"interpreter": "docker", "entrypoint": "projects/<name>"},
            },
        }
        print("Available templates:\n")
        for name, tmpl in templates.items():
            print(f"  {name}:")
            for k, v in tmpl.items():
                print(f"    {k}: {v}")
            print()
        return 0

    if action == "apply":
        name = args.name
        if not name:
            print("ERROR: --name required for apply", file=sys.stderr)
            return 1

        svc_type = args.type
        entrypoint = args.entrypoint

        # Build service from template
        svc: dict[str, Any] = {
            "id": name,
            "enabled": True,
            "program": {},
        }

        if svc_type == "daemon":
            svc["scheduler"] = "launchd"
            svc["trigger"] = "interval"
            svc["interval_sec"] = args.interval or 300
            svc["program"]["interpreter"] = "stable-python3"
            svc["program"]["entrypoint"] = entrypoint or f"bin/{name}.py"
            svc["resilience"] = {"keepalive": "crashed", "throttle_interval": 60}
            svc["liveness"] = {"signal": f".omo/_delivery/{name}/", "max_stale_hours": 24}
        elif svc_type == "cron":
            svc["scheduler"] = "cron"
            svc["trigger"] = "schedule"
            svc["schedule"] = args.schedule or "0 9 * * *"
            svc["program"]["interpreter"] = "stable-python3"
            svc["program"]["entrypoint"] = entrypoint or f"bin/{name}.py"
            svc["liveness"] = {"signal": f".omo/_delivery/{name}/", "max_stale_hours": 24}
        elif svc_type == "mcp":
            svc["scheduler"] = "manual"
            svc["trigger"] = "on_demand"
            svc["transport"] = "stdio"
            svc["program"]["interpreter"] = "uv"
            svc["program"]["entrypoint"] = entrypoint or "projects/agora"
        elif svc_type == "cli":
            svc["scheduler"] = "manual"
            svc["trigger"] = "on_demand"
            svc["program"]["interpreter"] = "uv"
            svc["program"]["entrypoint"] = entrypoint or "projects/cockpit"
        elif svc_type == "docker":
            svc["scheduler"] = "docker"
            svc["trigger"] = "compose"
            svc["program"]["interpreter"] = "docker"
            svc["program"]["entrypoint"] = entrypoint or f"projects/{name}"

        # Load existing and append
        services = load_services()
        services.append(svc)

        # Write back
        content = SERVICES_YAML.read_text()
        docs = list(yaml.safe_load_all(content))
        for doc in docs:
            if isinstance(doc, dict) and "services" in doc:
                doc["services"] = services
                break
        output = []
        for doc in docs:
            output.append(yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False))
        SERVICES_YAML.write_text("---\n".join(output))

        print(f"Created service '{name}' from template '{svc_type}'")
        return 0

    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Calculate system health score (0-100)."""
    services = load_services()
    fmt = args.format

    enabled = [s for s in services if s.get("enabled", False)]
    if not enabled:
        print("No enabled services")
        return 0

    # Calculate component scores
    total = len(enabled)
    healthy = 0
    running = 0
    has_liveness = 0
    has_deps = 0
    liveness_by_id = collect_liveness(enabled)

    for svc in enabled:
        liv = liveness_by_id.get(str(svc.get("id", "?")), {"status": "timeout"})
        if liv["status"] == "healthy":
            healthy += 1
        if _is_running(svc):
            running += 1
        if svc.get("liveness"):
            has_liveness += 1
        if svc.get("depends_on"):
            has_deps += 1

    # Health score (40% weight)
    health_score = (healthy / total * 100) if total > 0 else 0

    # Running score (30% weight)
    running_score = (running / total * 100) if total > 0 else 0

    # Observability score (15% weight)
    observability_score = (has_liveness / total * 100) if total > 0 else 0

    # Dependency score (15% weight)
    dependency_score = (has_deps / total * 100) if total > 0 else 0

    # Overall score
    overall = (
        health_score * 0.4
        + running_score * 0.3
        + observability_score * 0.15
        + dependency_score * 0.15
    )

    if fmt == "json":
        result = {
            "overall": round(overall, 1),
            "health": round(health_score, 1),
            "running": round(running_score, 1),
            "observability": round(observability_score, 1),
            "dependency": round(dependency_score, 1),
            "total_services": total,
            "healthy": healthy,
            "running_count": running,
            "with_liveness": has_liveness,
            "with_dependencies": has_deps,
        }
        print(json.dumps(result, indent=2))
    else:
        print("System Health Score")
        print("=" * 40)
        print(f"  Overall:        {round(overall, 1)}/100")
        print(f"  Health:         {round(health_score, 1)}/100 (40%)")
        print(f"  Running:        {round(running_score, 1)}/100 (30%)")
        print(f"  Observability:  {round(observability_score, 1)}/100 (15%)")
        print(f"  Dependency:     {round(dependency_score, 1)}/100 (15%)")
        print()
        print(f"  Total services: {total}")
        print(f"  Healthy:        {healthy}")
        print(f"  Running:       {running}")
        print(f"  With liveness: {has_liveness}")
        print(f"  With deps:     {has_deps}")

        # Grade
        if overall >= 90:
            grade = "A"
        elif overall >= 80:
            grade = "B"
        elif overall >= 70:
            grade = "C"
        elif overall >= 60:
            grade = "D"
        else:
            grade = "F"
        print(f"\n  Grade: {grade}")

    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Generate visual dependency graph in DOT format."""
    services = load_services()
    profile = args.profile
    fmt = args.format
    output = args.output

    # Filter by profile
    enabled = get_profile_services(profile, services)
    liveness_by_id = collect_liveness(enabled)

    # Build DOT graph
    lines: list[str] = []
    lines.append("digraph omostation {")
    lines.append('    rankdir=TB;')
    lines.append('    node [shape=box, style="rounded,filled", fontname="Helvetica"];')
    lines.append('    edge [fontname="Helvetica", fontsize=10];')
    lines.append("")

    # Color by type
    type_colors = {
        "launchd": "#4CAF50",
        "cron": "#2196F3",
        "manual": "#9E9E9E",
        "docker": "#FF9800",
        "gha": "#9C27B0",
    }

    # Add nodes
    lines.append("    // Nodes")
    for svc in enabled:
        sid = svc.get("id", "")
        scheduler = svc.get("scheduler", "unknown")
        color = type_colors.get(scheduler, "#9E9E9E")

        # Check health
        liv = liveness_by_id.get(sid, {"status": "timeout"})
        status = liv["status"]
        if status == "healthy":
            color = type_colors.get(scheduler, "#4CAF50")
        elif status in ("stale", "missing"):
            color = "#F44336"

        # Shorten ID for display
        display_id = sid.replace("bos.", "").replace("cron.", "").replace("cli.", "")
        lines.append(f'    "{sid}" [label="{display_id}", fillcolor="{color}"];')

    lines.append("")

    # Add edges
    lines.append("    // Edges (dependencies)")
    for svc in enabled:
        sid = svc.get("id", "")
        deps = svc.get("depends_on", [])
        for dep in deps:
            # Only include if dep is in our filtered set
            if any(s.get("id") == dep for s in enabled):
                lines.append(f'    "{dep}" -> "{sid}";')

    lines.append("}")

    content = "\n".join(lines)

    if fmt == "dot":
        if output:
            Path(output).write_text(content)
            print(f"DOT graph written to {output}")
        else:
            print(content)
        return 0

    # For SVG/PNG, use graphviz if available
    if fmt in ("svg", "png"):
        try:
            import subprocess as sp

            # Write DOT to temp file
            dot_file = Path("/tmp/omostation_graph.dot")
            dot_file.write_text(content)

            # Run graphviz
            cmd = ["dot", f"-T{fmt}", str(dot_file), "-o", output or f"/tmp/omostation_graph.{fmt}"]
            result = sp.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                out_path = output or f"/tmp/omostation_graph.{fmt}"
                print(f"{fmt.upper()} graph written to {out_path}")
                if not output:
                    # Print to stdout for piping
                    with open(out_path, "rb") as f:
                        import sys
                        sys.stdout.buffer.write(f.read())
            else:
                print(f"Graphviz error: {result.stderr}", file=sys.stderr)
                print("Install graphviz: brew install graphviz", file=sys.stderr)
                return 1
        except FileNotFoundError:
            print("Graphviz not found. Install: brew install graphviz", file=sys.stderr)
            print("Falling back to DOT format:")
            print(content)
            return 1

    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    """Service catalog — search and filter services."""
    services = load_services()
    query = (args.query or "").lower()
    svc_type = args.type
    status_filter = args.status
    fmt = args.format

    # Filter services
    filtered = []
    for svc in services:
        sid = svc.get("id", "")

        # Text search
        if query and query not in sid.lower():
            # Also search in notes
            notes = svc.get("notes", "").lower()
            if query not in notes:
                continue

        # Type filter
        if svc_type and svc.get("scheduler") != svc_type:
            continue

        # Status filter
        if status_filter:
            liv = check_liveness(svc)
            if liv["status"] != status_filter:
                continue

        filtered.append(svc)

    # Output
    if fmt == "json":
        print(json.dumps(filtered, indent=2, ensure_ascii=False))
    elif fmt == "csv":
        print("id,scheduler,enabled,status,ports")
        for svc in filtered:
            sid = svc.get("id", "")
            scheduler = svc.get("scheduler", "")
            enabled = svc.get("enabled", False)
            status = check_liveness(svc).get("status", "")
            ports = ",".join(str(p) for p in svc.get("ports", []))
            print(f"{sid},{scheduler},{enabled},{status},{ports}")
    else:
        # Table format
        print(f"Found {len(filtered)} services:\n")
        if not filtered:
            return 0

        # Group by type
        groups: dict[str, list[dict]] = {}
        for svc in filtered:
            t = svc.get("scheduler", "unknown")
            groups.setdefault(t, []).append(svc)

        for t, svcs in sorted(groups.items()):
            print(f"  {t} ({len(svcs)}):")
            for svc in sorted(svcs, key=lambda s: s.get("id", "")):
                sid = svc.get("id", "")
                status = check_liveness(svc).get("status", "")
                enabled = "✓" if svc.get("enabled") else "○"
                print(f"    {enabled} {sid} [{status}]")
            print()

    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """Show service health history."""
    from datetime import timedelta

    history_dir = WORKSPACE / ".omo" / "_delivery" / "ops-health-history"
    days = args.days
    fmt = args.format

    if args.service:
        # Show history for specific service
        history_file = history_dir / f"{args.service}.jsonl"
        if not history_file.exists():
            print(f"No history found for {args.service}")
            return 1

        entries = []
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with open(history_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts >= cutoff:
                        entries.append(entry)
                except Exception:
                    continue

        if fmt == "json":
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        else:
            print(f"Health history for {args.service} (last {days} days):\n")
            for entry in entries[-20:]:  # Last 20 entries
                ts = entry.get("timestamp", "?")[:19]
                status = entry.get("status", "?")
                print(f"  {ts} {status}")
        return 0

    # Show summary for all services
    if not history_dir.exists():
        print("No health history found")
        return 0

    history_files = list(history_dir.glob("*.jsonl"))
    if fmt == "json":
        result = {}
        for hf in history_files:
            sid = hf.stem
            entries = []
            cutoff = datetime.now(UTC) - timedelta(days=days)
            with open(hf) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = datetime.fromisoformat(entry["timestamp"])
                        if ts >= cutoff:
                            entries.append(entry)
                    except Exception:
                        continue
            result[sid] = entries[-5:]  # Last 5 entries
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Health history summary (last {days} days):\n")
        for hf in sorted(history_files):
            sid = hf.stem
            count = sum(1 for _ in open(hf))
            print(f"  {sid}: {count} entries")
    return 0


def record_health_history(svc_id: str, status: str) -> None:
    """Record a health check result to history."""
    history_dir = WORKSPACE / ".omo" / "_delivery" / "ops-health-history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / f"{svc_id}.jsonl"

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "service": svc_id,
        "status": status,
    }

    with open(history_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_drift(args: argparse.Namespace) -> int:
    """Configuration drift detection — compare manifest vs running state."""
    import re
    import subprocess as sp

    services = load_services()
    fix = getattr(args, "fix", False)

    drift_found = 0
    drift_fixed = 0

    # Get actual running processes
    running_processes: dict[str, list[int]] = {}
    try:
        proc = sp.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 11:
                    pid = int(parts[1])
                    cmd = " ".join(parts[10:])
                    # Match known entrypoints
                    for svc in services:
                        entry = svc.get("program", {}).get("entrypoint", "")
                        if entry and entry in cmd:
                            sid = svc.get("id", "")
                            running_processes.setdefault(sid, []).append(pid)
    except Exception:
        pass

    # Get actual listening ports
    running_ports: dict[int, list[int]] = {}
    try:
        proc = sp.run(["lsof", "-i", "-P", "-n"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 9 and "LISTEN" in parts[9]:
                    pid = int(parts[1])
                    port_match = re.search(r":(\d+)", parts[8])
                    if port_match:
                        port = int(port_match.group(1))
                        running_ports.setdefault(port, []).append(pid)
    except Exception:
        pass

    # Compare manifest vs running
    for svc in services:
        sid = svc.get("id", "")
        if not svc.get("enabled", False):
            continue

        # Check if service should be running but isn't
        pids = running_processes.get(sid, [])
        pid_file = PIDS_DIR / f"{sid}.pid"

        if svc.get("scheduler") == "launchd":
            # Launchd service should have a running process
            if not pids and not pid_file.exists():
                print(f"  [DRIFT] {sid}: manifest enabled but not running")
                drift_found += 1
                if fix:
                    cmd = _get_cmd(svc)
                    try:
                        log_file = LOGS_DIR / f"{sid}.log"
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(log_file, "a") as lf:
                            proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True, env=_get_environment(svc))
                        pid_file.write_text(str(proc.pid))
                        print(f"    [FIXED] Started {sid} (pid={proc.pid})")
                        drift_fixed += 1
                    except Exception as e:
                        print(f"    [FAIL] {e}")

        # Check port conflicts
        manifest_ports = svc.get("ports", [])
        for port in manifest_ports:
            actual_pids = running_ports.get(port, [])
            # Filter out our own processes
            own_pids = set(pids)
            other_pids = [p for p in actual_pids if p not in own_pids]
            if other_pids:
                print(f"  [DRIFT] {sid}: port {port} also used by pids {other_pids}")
                drift_found += 1

    if drift_found == 0:
        print("No configuration drift detected")
        return 0

    print(f"\nTotal: {drift_found} drift(s) detected, {drift_fixed} fixed")
    return 1 if drift_found > drift_fixed else 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Batch operations on multiple services."""
    services = load_services()
    action = args.batch_action
    target_ids = set(args.services)

    # Find target services
    targets = [s for s in services if s.get("id") in target_ids]
    found_ids = {s.get("id") for s in targets}
    missing = target_ids - found_ids

    if missing:
        print(f"WARNING: services not found: {', '.join(missing)}")

    if not targets:
        print("No matching services")
        return 1

    if action == "status":
        for svc in targets:
            sid = svc.get("id", "")
            liv = check_liveness(svc)
            running = _is_running(svc)
            print(f"  {sid}: {liv['status']} (running={running})")
        return 0

    if action == "up":
        import subprocess as sp
        started = 0
        for svc in targets:
            sid = svc.get("id", "")
            if _is_running(svc):
                print(f"  [SKIP] {sid} (running)")
                continue
            cmd = _get_cmd(svc)
            try:
                log_file = LOGS_DIR / f"{sid}.log"
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a") as lf:
                    proc = sp.Popen(cmd, stdout=lf, stderr=sp.STDOUT, start_new_session=True, env=_get_environment(svc))
                _get_pid_file(sid).write_text(str(proc.pid))
                print(f"  [START] {sid} (pid={proc.pid})")
                started += 1
            except Exception as e:
                print(f"  [FAIL] {sid}: {e}")
        print(f"\nStarted {started}/{len(targets)} services")
        return 0

    if action == "down":
        stopped = 0
        for svc in targets:
            sid = svc.get("id", "")
            pid_file = _get_pid_file(sid)
            if not pid_file.exists():
                print(f"  [SKIP] {sid} (not running)")
                continue
            try:
                pid = int(pid_file.read_text().strip())
                import os
                os.kill(pid, 15)
                pid_file.unlink(missing_ok=True)
                print(f"  [STOP] {sid} (pid={pid})")
                stopped += 1
            except (ValueError, OSError, ProcessLookupError) as e:
                print(f"  [FAIL] {sid}: {e}")
                pid_file.unlink(missing_ok=True)
        print(f"\nStopped {stopped}/{len(targets)} services")
        return 0

    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    """Export Prometheus metrics."""
    services = load_services()
    port = args.port
    text_mode = args.text

    enabled = [s for s in services if s.get("enabled", False)]
    running = [s for s in enabled if _is_running(s)]
    healthy = [s for s in enabled if check_liveness(s).get("status") == "healthy"]

    metrics_lines: list[str] = []

    # Help and type comments
    metrics_lines.append("# HELP omostation_services_total Total number of services")
    metrics_lines.append("# TYPE omostation_services_total gauge")
    metrics_lines.append(f"omostation_services_total {len(services)}")

    metrics_lines.append("# HELP omostation_services_enabled Total enabled services")
    metrics_lines.append("# TYPE omostation_services_enabled gauge")
    metrics_lines.append(f"omostation_services_enabled {len(enabled)}")

    metrics_lines.append("# HELP omostation_services_running Total running services")
    metrics_lines.append("# TYPE omostation_services_running gauge")
    metrics_lines.append(f"omostation_services_running {len(running)}")

    metrics_lines.append("# HELP omostation_services_healthy Total healthy services")
    metrics_lines.append("# TYPE omostation_services_healthy gauge")
    metrics_lines.append(f"omostation_services_healthy {len(healthy)}")

    # Per-service metrics
    metrics_lines.append("# HELP omostation_service_running Service running state (1=running, 0=not)")
    metrics_lines.append("# TYPE omostation_service_running gauge")
    for svc in enabled:
        sid = svc.get("id", "").replace(".", "_").replace("-", "_")
        is_running = 1 if _is_running(svc) else 0
        metrics_lines.append(f'omostation{{service="{sid}"}} {is_running}')

    metrics_lines.append("# HELP omostation_service_healthy Service health state (1=healthy, 0=not)")
    metrics_lines.append("# TYPE omostation_service_healthy gauge")
    for svc in enabled:
        sid = svc.get("id", "").replace(".", "_").replace("-", "_")
        is_healthy = 1 if check_liveness(svc).get("status") == "healthy" else 0
        metrics_lines.append(f'omostation_healthy{{service="{sid}"}} {is_healthy}')

    content = "\n".join(metrics_lines) + "\n"

    if text_mode:
        print(content)
        return 0

    # Serve metrics via HTTP
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(content.encode())

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), MetricsHandler)
    print(f"Prometheus metrics: http://127.0.0.1:{port}/metrics")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
    return 0


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
        from rich import box
        from rich.console import Console
        from rich.table import Table

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
