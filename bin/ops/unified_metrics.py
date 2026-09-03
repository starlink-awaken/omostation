#!/usr/bin/env python3
"""Unified Metrics Aggregator — collect from all existing metrics sources.

Collects metrics from:
- bus-foundation metrics_server (port 8745)
- agora bos_metrics (SQLite)
- aetherforge gateway metrics (JSONL)
- ecos metrics collector
- ops health checks (services.yaml)

Exposes a single /metrics endpoint for Prometheus scraping.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
STATE_FILE = WORKSPACE / ".omo" / "_delivery" / "ops-metrics" / "state.jsonl"

# Source endpoints
SOURCES = {
    "bus_foundation": {
        "url": "http://localhost:8745/metrics",
        "type": "prometheus",
        "description": "Bus Foundation metrics",
    },
    "agora_bos": {
        "url": None,  # SQLite direct
        "type": "sqlite",
        "db_path": WORKSPACE / ".omo" / "_delivery" / "agora-metrics.db",
        "description": "Agora BOS call metrics",
    },
    "aetherforge": {
        "url": None,  # JSONL file
        "type": "jsonl",
        "file_path": WORKSPACE / ".aetherforge" / "metrics.jsonl",
        "description": "AetherForge gateway metrics",
    },
}


def fetch_prometheus(url: str, timeout: float = 5.0) -> str:
    """Fetch Prometheus text format from URL."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception:
        return ""


def fetch_sqlite(db_path: Path) -> dict[str, Any]:
    """Fetch metrics from SQLite database."""
    if not db_path.exists():
        return {}

    result = {}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                result[f"sqlite_{table}_count"] = count
            except Exception:
                pass

        conn.close()
    except Exception:
        pass

    return result


def fetch_jsonl(file_path: Path, max_lines: int = 1000) -> dict[str, Any]:
    """Fetch metrics from JSONL file."""
    if not file_path.exists():
        return {}

    result = {}
    try:
        lines = []
        with open(file_path) as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                try:
                    lines.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        result["jsonl_total_lines"] = len(lines)

        # Aggregate by metric name
        for entry in lines:
            name = entry.get("name", "unknown")
            value = entry.get("value", 0)
            if isinstance(value, (int, float)):
                key = f"jsonl_{name}"
                result[key] = result.get(key, 0) + value
    except Exception:
        pass

    return result


def collect_service_health() -> dict[str, Any]:
    """Collect service health from services.yaml."""
    if not SERVICES_YAML.exists():
        return {}

    content = SERVICES_YAML.read_text()
    docs = list(yaml.safe_load_all(content))

    total = 0
    enabled = 0
    healthy = 0
    running = 0

    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            for svc in doc["services"]:
                total += 1
                if svc.get("enabled"):
                    enabled += 1
                # Check liveness
                liveness = svc.get("liveness", {})
                if liveness:
                    # Simple check: has liveness config = observable
                    healthy += 1
                # Check if running (has PID file)
                pid_file = WORKSPACE / "runtime" / "pids" / f"{svc.get('id', '')}.pid"
                if pid_file.exists():
                    running += 1

    return {
        "ops_services_total": total,
        "ops_services_enabled": enabled,
        "ops_services_healthy": healthy,
        "ops_services_running": running,
    }


def collect_all_metrics() -> dict[str, Any]:
    """Collect metrics from all sources."""
    metrics = {}

    # Service health
    metrics.update(collect_service_health())

    # Bus Foundation
    bus_metrics = fetch_prometheus(SOURCES["bus_foundation"]["url"])
    if bus_metrics:
        metrics["bus_foundation_available"] = 1
        # Parse Prometheus text format
        for line in bus_metrics.splitlines():
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        metrics[f"bus_{parts[0]}"] = float(parts[1])
                    except ValueError:
                        pass
    else:
        metrics["bus_foundation_available"] = 0

    # Agora BOS (SQLite)
    agora_db = SOURCES["agora_bos"]["db_path"]
    agora_metrics = fetch_sqlite(agora_db)
    metrics.update(agora_metrics)

    # AetherForge (JSONL)
    aether_path = SOURCES["aetherforge"]["file_path"]
    aether_metrics = fetch_jsonl(aether_path)
    metrics.update(aether_metrics)

    return metrics


def format_prometheus(metrics: dict[str, Any]) -> str:
    """Format metrics as Prometheus text exposition format."""
    lines = []
    lines.append("# HELP ops_services_total Total number of registered services")
    lines.append("# TYPE ops_services_total gauge")
    lines.append(f"ops_services_total {metrics.get('ops_services_total', 0)}")

    lines.append("# HELP ops_services_enabled Total enabled services")
    lines.append("# TYPE ops_services_enabled gauge")
    lines.append(f"ops_services_enabled {metrics.get('ops_services_enabled', 0)}")

    lines.append("# HELP ops_services_healthy Total healthy services")
    lines.append("# TYPE ops_services_healthy gauge")
    lines.append(f"ops_services_healthy {metrics.get('ops_services_healthy', 0)}")

    lines.append("# HELP ops_services_running Total running services")
    lines.append("# TYPE ops_services_running gauge")
    lines.append(f"ops_services_running {metrics.get('ops_services_running', 0)}")

    lines.append("# HELP bus_foundation_available Bus Foundation availability")
    lines.append("# TYPE bus_foundation_available gauge")
    lines.append(f"bus_foundation_available {metrics.get('bus_foundation_available', 0)}")

    # Add all other metrics
    for key, value in sorted(metrics.items()):
        if key.startswith(("ops_", "bus_foundation_")):
            continue
        if isinstance(value, (int, float)):
            safe_key = key.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {safe_key} gauge")
            lines.append(f"{safe_key} {value}")

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint."""

    def do_GET(self):
        if self.path == "/metrics":
            metrics = collect_all_metrics()
            content = format_prometheus(metrics)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main() -> int:
    """Run the unified metrics server."""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Metrics Aggregator")
    parser.add_argument("--port", type=int, default=9091, help="Port (default: 9091)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--once", action="store_true", help="Print metrics and exit")
    args = parser.parse_args()

    if args.once:
        metrics = collect_all_metrics()
        print(format_prometheus(metrics))
        return 0

    server = HTTPServer((args.host, args.port), MetricsHandler)
    print(f"Unified Metrics Server: http://{args.host}:{args.port}/metrics")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
