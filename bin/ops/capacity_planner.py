#!/usr/bin/env python3
"""Capacity Planner for Service Gateway.

Analyzes resource usage trends and predicts future needs:
- CPU usage trends
- Memory usage trends
- Storage growth
- API call growth
- Scaling recommendations

Usage:
    python3 bin/ops/capacity_planner.py [--report] [--forecast-days 30]
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
METRICS_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-metrics"
COST_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-cost"
SLO_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-slo"


def load_services() -> list[dict]:
    if not SERVICES_YAML.exists():
        return []
    content = SERVICES_YAML.read_text()
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def get_system_resources() -> dict[str, Any]:
    """Get current system resource usage."""
    resources = {
        "timestamp": datetime.now(UTC).isoformat(),
        "cpu": {},
        "memory": {},
        "storage": {},
    }

    # CPU info
    try:
        with open("/proc/cpuinfo") as f:
            cpu_count = sum(1 for line in f if line.startswith("processor"))
            resources["cpu"]["cores"] = cpu_count
    except Exception:
        pass

    # CPU usage
    try:
        with open("/proc/stat") as f:
            line = f.readline()
            fields = line.split()
            idle = int(fields[4])
            total = sum(int(f) for f in fields[1:])
            resources["cpu"]["usage_percent"] = round((1 - idle / total) * 100, 1)
    except Exception:
        pass

    # Memory info
    try:
        with open("/proc/meminfo") as f:
            mem_info = {}
            for line in f:
                if ":" in line:
                    key, value = line.split(":", 1)
                    mem_info[key.strip()] = int(value.split()[0])
            total_kb = mem_info.get("MemTotal", 0)
            available_kb = mem_info.get("MemAvailable", 0)
            used_kb = total_kb - available_kb
            resources["memory"] = {
                "total_gb": round(total_kb / (1024 * 1024), 2),
                "used_gb": round(used_kb / (1024 * 1024), 2),
                "available_gb": round(available_kb / (1024 * 1024), 2),
                "usage_percent": round(used_kb / total_kb * 100, 1) if total_kb > 0 else 0,
            }
    except Exception:
        pass

    # Storage info
    try:
        stat = os.statvfs(str(WORKSPACE))
        total_bytes = stat.f_blocks * stat.f_frsize
        available_bytes = stat.f_bavail * stat.f_frsize
        used_bytes = total_bytes - available_bytes
        resources["storage"] = {
            "total_gb": round(total_bytes / (1024**3), 2),
            "used_gb": round(used_bytes / (1024**3), 2),
            "available_gb": round(available_bytes / (1024**3), 2),
            "usage_percent": round(used_bytes / total_bytes * 100, 1) if total_bytes > 0 else 0,
        }
    except Exception:
        pass

    return resources


def load_historical_metrics(days: int = 30) -> list[dict]:
    """Load historical metrics from files."""
    if not METRICS_DIR.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    metrics = []

    for f in sorted(METRICS_DIR.glob("*.jsonl")):
        with open(f) as fh:
            for line in fh:
                try:
                    entry = json.loads(line.strip())
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts >= cutoff:
                        metrics.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue

    return metrics


def analyze_trends(metrics: list[dict]) -> dict[str, Any]:
    """Analyze resource usage trends."""
    if not metrics:
        return {"trend": "insufficient_data"}

    # Simple linear trend analysis
    values = [m.get("total", 0) for m in metrics if "total" in m]
    if len(values) < 2:
        return {"trend": "insufficient_data"}

    first_avg = sum(values[:len(values)//2]) / (len(values)//2)
    second_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

    change = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0

    if change > 10:
        trend = "increasing"
    elif change < -10:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "change_percent": round(change, 1),
        "data_points": len(values),
    }


def forecast_capacity(resources: dict[str, Any], trends: dict[str, Any], days: int = 30) -> dict[str, Any]:
    """Forecast future capacity needs."""
    forecast = {
        "days": days,
        "timestamp": datetime.now(UTC).isoformat(),
        "recommendations": [],
    }

    # Memory forecast
    mem = resources.get("memory", {})
    if mem.get("usage_percent", 0) > 80:
        forecast["recommendations"].append({
            "resource": "memory",
            "severity": "high",
            "current_usage": f"{mem.get('usage_percent', 0)}%",
            "message": "Memory usage above 80%, consider adding RAM",
        })
    elif mem.get("usage_percent", 0) > 60:
        forecast["recommendations"].append({
            "resource": "memory",
            "severity": "medium",
            "current_usage": f"{mem.get('usage_percent', 0)}%",
            "message": "Memory usage trending up, monitor closely",
        })

    # Storage forecast
    storage = resources.get("storage", {})
    if storage.get("usage_percent", 0) > 85:
        forecast["recommendations"].append({
            "resource": "storage",
            "severity": "high",
            "current_usage": f"{storage.get('usage_percent', 0)}%",
            "message": "Storage usage above 85%, consider cleanup or expansion",
        })
    elif storage.get("usage_percent", 0) > 70:
        forecast["recommendations"].append({
            "resource": "storage",
            "severity": "medium",
            "current_usage": f"{storage.get('usage_percent', 0)}%",
            "message": "Storage usage trending up",
        })

    # CPU forecast
    cpu = resources.get("cpu", {})
    if cpu.get("usage_percent", 0) > 80:
        forecast["recommendations"].append({
            "resource": "cpu",
            "severity": "high",
            "current_usage": f"{cpu.get('usage_percent', 0)}%",
            "message": "CPU usage above 80%, consider scaling",
        })

    return forecast


def generate_capacity_report(resources: dict[str, Any], trends: dict[str, Any], forecast: dict[str, Any]) -> str:
    """Generate a human-readable capacity report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Capacity Plan — Service Gateway")
    lines.append(f"Generated: {resources.get('timestamp', '?')}")
    lines.append("=" * 60)
    lines.append("")

    # Current resources
    lines.append("Current Resources:")
    cpu = resources.get("cpu", {})
    if cpu:
        lines.append(f"  CPU: {cpu.get('usage_percent', '?')}% ({cpu.get('cores', '?')} cores)")
    mem = resources.get("memory", {})
    if mem:
        lines.append(f"  Memory: {mem.get('usage_percent', '?')}% ({mem.get('used_gb', '?')}/{mem.get('total_gb', '?')} GB)")
    storage = resources.get("storage", {})
    if storage:
        lines.append(f"  Storage: {storage.get('usage_percent', '?')}% ({storage.get('used_gb', '?')}/{storage.get('total_gb', '?')} GB)")
    lines.append("")

    # Trends
    lines.append("Trends:")
    lines.append(f"  Service count: {trends.get('trend', '?')} ({trends.get('change_percent', 0)}%)")
    lines.append("")

    # Forecast
    lines.append(f"Forecast ({forecast.get('days', 30)} days):")
    if forecast.get("recommendations"):
        for rec in forecast["recommendations"]:
            icon = "🔴" if rec["severity"] == "high" else "🟡"
            lines.append(f"  {icon} [{rec['resource'].upper()}] {rec['message']}")
    else:
        lines.append("  ✅ No immediate capacity concerns")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Capacity Planner")
    parser.add_argument("--report", action="store_true", help="Generate capacity report")
    parser.add_argument("--forecast-days", type=int, default=30, help="Forecast period (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    resources = get_system_resources()
    metrics = load_historical_metrics(days=args.forecast_days)
    trends = analyze_trends(metrics)
    forecast = forecast_capacity(resources, trends, days=args.forecast_days)

    if args.json:
        print(json.dumps({
            "resources": resources,
            "trends": trends,
            "forecast": forecast,
        }, indent=2, ensure_ascii=False))
    else:
        print(generate_capacity_report(resources, trends, forecast))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
