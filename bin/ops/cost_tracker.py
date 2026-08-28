#!/usr/bin/env python3
"""Cost Tracker for Service Gateway.

Tracks resource usage and cost per service:
- CPU time (from process stats)
- Memory usage (from process stats)
- API call costs (from aetherforge metrics)
- Storage usage (from disk stats)

Cost model: per-service resource attribution.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
COST_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-cost"
METRICS_FILE = WORKSPACE / ".aetherforge" / "metrics.jsonl"

# Cost rates (example - adjust to actual pricing)
COST_RATES = {
    "cpu_hour": 0.05,  # $0.05 per CPU hour
    "memory_gb_hour": 0.01,  # $0.01 per GB hour
    "storage_gb_month": 0.10,  # $0.10 per GB month
    "api_call": 0.001,  # $0.001 per API call
}


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


def get_process_stats(pid: int) -> dict[str, Any]:
    """Get process CPU and memory stats."""
    try:
        # Read /proc/{pid}/stat for CPU time
        stat_path = f"/proc/{pid}/stat"
        if os.path.exists(stat_path):
            with open(stat_path) as f:
                stat_data = f.read().split()
                # utime is field 14, stime is field 15
                utime = int(stat_data[13])
                stime = int(stat_data[14])
                total_time = utime + stime
                # Convert to seconds (clock ticks per second)
                ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                cpu_seconds = total_time / ticks
        else:
            cpu_seconds = 0

        # Read /proc/{pid}/status for memory
        status_path = f"/proc/{pid}/status"
        memory_kb = 0
        if os.path.exists(status_path):
            with open(status_path) as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        memory_kb = int(line.split()[1])
                        break

        return {
            "cpu_seconds": cpu_seconds,
            "memory_kb": memory_kb,
            "memory_gb": memory_kb / (1024 * 1024),
        }
    except Exception:
        return {"cpu_seconds": 0, "memory_kb": 0, "memory_gb": 0}


def get_storage_usage(path: Path) -> float:
    """Get storage usage in GB for a path."""
    try:
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = Path(dirpath) / f
                if fp.exists():
                    total += fp.stat().st_size
        return total / (1024 * 1024 * 1024)  # Convert to GB
    except Exception:
        return 0


def get_api_call_costs() -> dict[str, float]:
    """Get API call costs from aetherforge metrics."""
    if not METRICS_FILE.exists():
        return {}

    costs = {}
    try:
        with open(METRICS_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("name") == "api_calls":
                        model = entry.get("model", "unknown")
                        count = entry.get("value", 0)
                        costs[model] = count * COST_RATES["api_call"]
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return costs


def compute_service_costs(services: list[dict]) -> dict[str, Any]:
    """Compute cost per service."""
    per_service = {}
    total_cpu_cost = 0
    total_memory_cost = 0
    total_storage_cost = 0

    for svc in services:
        sid = svc.get("id", "")
        if not svc.get("enabled", False):
            continue

        # Get process stats
        pid_file = WORKSPACE / "runtime" / "pids" / f"{sid}.pid"
        cpu_seconds = 0
        memory_gb = 0

        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                stats = get_process_stats(pid)
                cpu_seconds = stats["cpu_seconds"]
                memory_gb = stats["memory_gb"]
            except (ValueError, OSError):
                pass

        # Estimate storage (service-specific paths)
        storage_gb = 0
        entrypoint = svc.get("program", {}).get("entrypoint", "")
        if entrypoint:
            svc_path = WORKSPACE / entrypoint.split("/")[0] if "/" in entrypoint else WORKSPACE / entrypoint
            if svc_path.exists():
                storage_gb = get_storage_usage(svc_path) * 0.1  # 10% attribution

        # Compute costs
        cpu_cost = (cpu_seconds / 3600) * COST_RATES["cpu_hour"]
        memory_cost = memory_gb * COST_RATES["memory_gb_hour"]
        storage_cost = storage_gb * COST_RATES["storage_gb_month"] / 730  # Monthly to hourly

        total_cost = cpu_cost + memory_cost + storage_cost

        per_service[sid] = {
            "cpu_seconds": round(cpu_seconds, 1),
            "memory_gb": round(memory_gb, 3),
            "storage_gb": round(storage_gb, 3),
            "cpu_cost": round(cpu_cost, 4),
            "memory_cost": round(memory_cost, 4),
            "storage_cost": round(storage_cost, 4),
            "total_cost": round(total_cost, 4),
        }

        total_cpu_cost += cpu_cost
        total_memory_cost += memory_cost
        total_storage_cost += storage_cost

    # API call costs
    api_costs = get_api_call_costs()
    total_api_cost = sum(api_costs.values())

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "per_service": per_service,
        "api_costs": api_costs,
        "summary": {
            "total_cpu_cost": round(total_cpu_cost, 4),
            "total_memory_cost": round(total_memory_cost, 4),
            "total_storage_cost": round(total_storage_cost, 4),
            "total_api_cost": round(total_api_cost, 4),
            "total_cost": round(total_cpu_cost + total_memory_cost + total_storage_cost + total_api_cost, 4),
        },
    }


def generate_cost_report(costs: dict[str, Any]) -> str:
    """Generate a human-readable cost report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Cost Report — Service Gateway")
    lines.append(f"Generated: {costs.get('timestamp', '?')}")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    summary = costs.get("summary", {})
    lines.append("Summary:")
    lines.append(f"  CPU Cost:     ${summary.get('total_cpu_cost', 0):.4f}")
    lines.append(f"  Memory Cost:  ${summary.get('total_memory_cost', 0):.4f}")
    lines.append(f"  Storage Cost: ${summary.get('total_storage_cost', 0):.4f}")
    lines.append(f"  API Cost:     ${summary.get('total_api_cost', 0):.4f}")
    lines.append(f"  Total:        ${summary.get('total_cost', 0):.4f}")
    lines.append("")

    # Per-service breakdown
    per_service = costs.get("per_service", {})
    if per_service:
        lines.append("Per-Service Costs:")
        for sid, data in sorted(per_service.items(), key=lambda x: x[1].get("total_cost", 0), reverse=True):
            lines.append(f"  {sid}:")
            lines.append(f"    CPU: {data.get('cpu_seconds', 0):.1f}s, Memory: {data.get('memory_gb', 0):.3f}GB")
            lines.append(f"    Cost: ${data.get('total_cost', 0):.4f}")

    # API costs
    api_costs = costs.get("api_costs", {})
    if api_costs:
        lines.append("")
        lines.append("API Call Costs:")
        for model, cost in sorted(api_costs.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {model}: ${cost:.4f}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Cost Tracker")
    parser.add_argument("--report", action="store_true", help="Generate cost report")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--record", action="store_true", help="Record current costs")
    args = parser.parse_args()

    services = load_services()
    costs = compute_service_costs(services)

    if args.record:
        COST_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        record_file = COST_DIR / f"{today}.jsonl"
        with open(record_file, "a") as f:
            f.write(json.dumps(costs, ensure_ascii=False) + "\n")
        print(f"Recorded costs to {record_file}")

    if args.json:
        print(json.dumps(costs, indent=2, ensure_ascii=False))
    else:
        print(generate_cost_report(costs))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
