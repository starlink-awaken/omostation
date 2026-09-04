#!/usr/bin/env python3
"""Automated Runbook — common incident response procedures.

Automates diagnosis and recovery for common scenarios:
1. Service down → auto-restart
2. High latency → diagnose bottleneck
3. Resource exhaustion → identify top consumers
4. Dependency failure → trace failure chain
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
RUNBOOK_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-runbooks"


def load_services() -> list[dict]:
    """Load service manifest."""
    if not SERVICES_YAML.exists():
        return []
    content = SERVICES_YAML.read_text()
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def check_service_down(svc: dict) -> dict[str, Any]:
    """Check if a service is down and attempt recovery."""
    sid = svc.get("id", "")
    result = {
        "service": sid,
        "status": "unknown",
        "actions": [],
    }

    # Check PID file
    pid_file = WORKSPACE / "runtime" / "pids" / f"{sid}.pid"
    if not pid_file.exists():
        result["status"] = "down"
        result["actions"].append("PID file missing")
    else:
        try:
            pid = int(pid_file.read_text().strip())
            import os
            os.kill(pid, 0)
            result["status"] = "running"
            result["pid"] = pid
        except (ValueError, OSError, ProcessLookupError):
            result["status"] = "down"
            result["actions"].append("Process not running")
            pid_file.unlink(missing_ok=True)

    # Attempt recovery if down
    if result["status"] == "down" and svc.get("enabled", False):
        result["actions"].append("Attempting auto-recovery...")
        cmd = _get_cmd(svc)
        try:
            log_file = WORKSPACE / "runtime" / "logs" / f"{sid}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            pid_file.write_text(str(proc.pid))
            result["recovered"] = True
            result["new_pid"] = proc.pid
            result["actions"].append(f"Started with PID {proc.pid}")
        except Exception as e:
            result["recovered"] = False
            result["actions"].append(f"Recovery failed: {e}")

    return result


def diagnose_high_latency(svc: dict) -> dict[str, Any]:
    """Diagnose high latency issues."""
    sid = svc.get("id", "")
    result = {
        "service": sid,
        "diagnosis": [],
        "recommendations": [],
    }

    # Check process stats
    pid_file = WORKSPACE / "runtime" / "pids" / f"{sid}.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            stat_path = f"/proc/{pid}/stat"
            if Path(stat_path).exists():
                with open(stat_path) as f:
                    stat_data = f.read().split()
                    utime = int(stat_data[13])
                    stime = int(stat_data[14])
                    total_time = utime + stime
                    ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                    cpu_seconds = total_time / ticks
                    result["cpu_seconds"] = cpu_seconds
                    if cpu_seconds > 3600:
                        result["diagnosis"].append("High CPU usage detected")
                        result["recommendations"].append("Consider scaling or optimizing")
        except Exception:
            pass

    # Check log for errors
    log_file = WORKSPACE / "runtime" / "logs" / f"{sid}.log"
    if log_file.exists():
        try:
            # Check last 100 lines for errors
            with open(log_file) as f:
                lines = f.readlines()[-100:]
                error_count = sum(1 for line in lines if "ERROR" in line or "error" in line)
                if error_count > 10:
                    result["diagnosis"].append(f"High error rate: {error_count} errors in last 100 lines")
                    result["recommendations"].append("Check application logs for root cause")
        except Exception:
            pass

    return result


def check_resource_exhaustion() -> dict[str, Any]:
    """Check for resource exhaustion across all services."""
    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "issues": [],
        "top_consumers": [],
    }

    services = load_services()
    consumers = []

    for svc in services:
        sid = svc.get("id", "")
        if not svc.get("enabled", False):
            continue

        pid_file = WORKSPACE / "runtime" / "pids" / f"{sid}.pid"
        if not pid_file.exists():
            continue

        try:
            pid = int(pid_file.read_text().strip())
            stat_path = f"/proc/{pid}/status"
            if Path(stat_path).exists():
                with open(stat_path) as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            mem_kb = int(line.split()[1])
                            consumers.append({
                                "service": sid,
                                "memory_kb": mem_kb,
                                "memory_gb": mem_kb / (1024 * 1024),
                            })
                            if mem_kb > 1024 * 1024:  # > 1GB
                                result["issues"].append(f"{sid}: High memory usage ({mem_kb / 1024:.0f} MB)")
                            break
        except Exception:
            continue

    # Sort by memory usage
    consumers.sort(key=lambda x: x["memory_kb"], reverse=True)
    result["top_consumers"] = consumers[:5]

    return result


def trace_dependency_failure(svc: dict) -> dict[str, Any]:
    """Trace dependency failure chain."""
    sid = svc.get("id", "")
    deps = svc.get("depends_on", [])

    result = {
        "service": sid,
        "dependencies": [],
        "failed": [],
    }

    services = load_services()
    service_map = {s.get("id"): s for s in services}

    for dep_id in deps:
        dep_svc = service_map.get(dep_id)
        if not dep_svc:
            result["dependencies"].append({
                "id": dep_id,
                "status": "not_found",
            })
            continue

        # Check if dependency is running
        pid_file = WORKSPACE / "runtime" / "pids" / f"{dep_id}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                import os
                os.kill(pid, 0)
                result["dependencies"].append({
                    "id": dep_id,
                    "status": "running",
                    "pid": pid,
                })
            except (ValueError, OSError, ProcessLookupError):
                result["dependencies"].append({
                    "id": dep_id,
                    "status": "down",
                })
                result["failed"].append(dep_id)
        else:
            result["dependencies"].append({
                "id": dep_id,
                "status": "not_running",
            })
            result["failed"].append(dep_id)

    return result


def _get_cmd(svc: dict) -> list[str]:
    """Build command list from service definition."""
    program = svc.get("program", {})
    entry = program.get("entrypoint", "")
    interpreter = program.get("interpreter", "python3")
    args = program.get("args", [])

    if interpreter == "uv":
        return ["uv", "run", entry] + args
    elif interpreter == "stable-python3":
        return [sys.executable, entry] + args
    elif interpreter.startswith("/"):
        return [interpreter, entry] + args
    else:
        return [interpreter, entry] + args


def generate_runbook_report(results: list[dict]) -> str:
    """Generate a human-readable runbook report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Automated Runbook Report")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append("=" * 60)
    lines.append("")

    for result in results:
        scenario = result.get("scenario", "?")
        lines.append(f"Scenario: {scenario}")
        lines.append("-" * 40)

        if scenario == "service_down":
            lines.append(f"  Service: {result.get('service', '?')}")
            lines.append(f"  Status: {result.get('status', '?')}")
            if result.get("recovered"):
                lines.append(f"  ✅ Recovered (PID: {result.get('new_pid')})")
            for action in result.get("actions", []):
                lines.append(f"  → {action}")

        elif scenario == "high_latency":
            lines.append(f"  Service: {result.get('service', '?')}")
            for diag in result.get("diagnosis", []):
                lines.append(f"  ⚠️  {diag}")
            for rec in result.get("recommendations", []):
                lines.append(f"  💡 {rec}")

        elif scenario == "resource_exhaustion":
            for issue in result.get("issues", []):
                lines.append(f"  ⚠️  {issue}")
            lines.append("  Top Consumers:")
            for consumer in result.get("top_consumers", []):
                lines.append(f"    {consumer['service']}: {consumer['memory_gb']:.2f} GB")

        elif scenario == "dependency_failure":
            lines.append(f"  Service: {result.get('service', '?')}")
            lines.append(f"  Failed Dependencies: {', '.join(result.get('failed', []))}")
            for dep in result.get("dependencies", []):
                icon = "✅" if dep["status"] == "running" else "❌"
                lines.append(f"    {icon} {dep['id']}: {dep['status']}")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Automated Runbook")
    parser.add_argument("scenario", choices=[
        "service-down", "high-latency", "resource-exhaustion",
        "dependency-failure", "all",
    ], help="Runbook scenario to execute")
    parser.add_argument("--service", help="Specific service to target")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Diagnose only, no recovery")
    args = parser.parse_args()

    services = load_services()
    results = []

    if args.scenario in ("service-down", "all"):
        # Check all enabled services
        target_services = services
        if args.service:
            target_services = [s for s in services if s.get("id") == args.service]

        for svc in target_services:
            if svc.get("enabled", False):
                result = check_service_down(svc)
                result["scenario"] = "service-down"
                results.append(result)

    if args.scenario in ("high-latency", "all"):
        target_services = services
        if args.service:
            target_services = [s for s in services if s.get("id") == args.service]

        for svc in target_services:
            if svc.get("enabled", False):
                result = diagnose_high_latency(svc)
                result["scenario"] = "high-latency"
                results.append(result)

    if args.scenario in ("resource-exhaustion", "all"):
        result = check_resource_exhaustion()
        result["scenario"] = "resource-exhaustion"
        results.append(result)

    if args.scenario in ("dependency-failure", "all"):
        target_services = services
        if args.service:
            target_services = [s for s in services if s.get("id") == args.service]

        for svc in target_services:
            if svc.get("depends_on"):
                result = trace_dependency_failure(svc)
                result["scenario"] = "dependency-failure"
                results.append(result)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(generate_runbook_report(results))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
