#!/usr/bin/env python3
"""Service Catalog API — REST API for service discovery and management.

Provides endpoints:
    GET /api/services         — List all services
    GET /api/services/<id>    — Get service details
    GET /api/health           — Health check all services
    GET /api/health/<id>      — Health check specific service
    POST /api/services/<id>/start  — Start a service
    POST /api/services/<id>/stop   — Stop a service
    GET /api/metrics          — Get service metrics
    GET /api/dependencies     — Get dependency graph

Usage:
    python3 bin/ops/catalog_api.py [--port 8092]
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
PIDS_DIR = WORKSPACE / "runtime" / "pids"
LOGS_DIR = WORKSPACE / "runtime" / "logs"


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


def get_service_by_id(services: list[dict], sid: str) -> dict | None:
    """Find a service by ID."""
    for svc in services:
        if svc.get("id") == sid:
            return svc
    return None


def check_service_health(svc: dict) -> dict[str, Any]:
    """Check health of a service."""
    sid = svc.get("id", "")
    result = {
        "id": sid,
        "enabled": svc.get("enabled", False),
        "status": "unknown",
        "healthy": None,
    }

    if not result["enabled"]:
        result["status"] = "disabled"
        return result

    pid_file = PIDS_DIR / f"{sid}.pid"
    if not pid_file.exists():
        result["status"] = "down"
        result["healthy"] = False
        return result

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        result["status"] = "running"
        result["healthy"] = True
        result["pid"] = pid
    except (ValueError, OSError, ProcessLookupError):
        result["status"] = "down"
        result["healthy"] = False
        pid_file.unlink(missing_ok=True)

    return result


def start_service(svc: dict) -> dict[str, Any]:
    """Start a service."""
    sid = svc.get("id", "")
    result = {"id": sid, "started": False, "actions": []}

    if not svc.get("enabled", False):
        result["actions"].append("Service disabled")
        return result

    # Check if already running
    pid_file = PIDS_DIR / f"{sid}.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            result["actions"].append("Already running")
            result["pid"] = pid
            return result
        except (ValueError, OSError, ProcessLookupError):
            pid_file.unlink(missing_ok=True)

    # Build command
    program = svc.get("program", {})
    entry = program.get("entrypoint", "")
    interpreter = program.get("interpreter", "python3")
    args = program.get("args", [])

    if interpreter == "uv":
        cmd = ["uv", "run", entry] + args
    elif interpreter == "stable-python3":
        cmd = [sys.executable, entry] + args
    elif interpreter.startswith("/"):
        cmd = [interpreter, entry] + args
    else:
        cmd = [interpreter, entry] + args

    try:
        log_file = LOGS_DIR / f"{sid}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as lf:
            proc = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        pid_file.write_text(str(proc.pid))
        result["started"] = True
        result["pid"] = proc.pid
        result["actions"].append(f"Started with PID {proc.pid}")
    except Exception as e:
        result["actions"].append(f"Failed: {e}")

    return result


def stop_service(svc: dict) -> dict[str, Any]:
    """Stop a service."""
    sid = svc.get("id", "")
    result = {"id": sid, "stopped": False, "actions": []}

    pid_file = PIDS_DIR / f"{sid}.pid"
    if not pid_file.exists():
        result["actions"].append("Not running")
        return result

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 15)  # SIGTERM
        result["stopped"] = True
        result["pid"] = pid
        result["actions"].append(f"Sent SIGTERM to PID {pid}")
        pid_file.unlink(missing_ok=True)
    except (ValueError, OSError, ProcessLookupError) as e:
        result["actions"].append(f"Failed: {e}")
        pid_file.unlink(missing_ok=True)

    return result


def get_dependency_graph(services: list[dict]) -> dict[str, Any]:
    """Build dependency graph."""
    nodes = []
    edges = []

    for svc in services:
        sid = svc.get("id", "")
        nodes.append({
            "id": sid,
            "enabled": svc.get("enabled", False),
            "scheduler": svc.get("scheduler", "unknown"),
        })

        for dep in svc.get("depends_on", []):
            edges.append({"source": dep, "target": sid})

    return {"nodes": nodes, "edges": edges}


class CatalogHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the catalog API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/services":
            services = load_services()
            self._json_response([{
                "id": s.get("id"),
                "enabled": s.get("enabled", False),
                "scheduler": s.get("scheduler", "unknown"),
                "depends_on": s.get("depends_on", []),
            } for s in services])

        elif path.startswith("/api/services/"):
            sid = path.split("/")[-1]
            services = load_services()
            svc = get_service_by_id(services, sid)
            if svc:
                self._json_response(svc)
            else:
                self._json_response({"error": "not found"}, status=404)

        elif path == "/api/health":
            services = load_services()
            results = [check_service_health(s) for s in services if s.get("enabled")]
            healthy = sum(1 for r in results if r.get("healthy"))
            total = len(results)
            self._json_response({
                "total": total,
                "healthy": healthy,
                "unhealthy": total - healthy,
                "availability": healthy / total if total > 0 else None,
                "services": results,
            })

        elif path.startswith("/api/health/"):
            sid = path.split("/")[-1]
            services = load_services()
            svc = get_service_by_id(services, sid)
            if svc:
                self._json_response(check_service_health(svc))
            else:
                self._json_response({"error": "not found"}, status=404)

        elif path == "/api/metrics":
            services = load_services()
            metrics = []
            for svc in services:
                if svc.get("enabled"):
                    health = check_service_health(svc)
                    metrics.append({
                        "id": svc.get("id"),
                        "status": health["status"],
                        "healthy": health["healthy"],
                    })
            self._json_response({"services": metrics})

        elif path == "/api/dependencies":
            services = load_services()
            self._json_response(get_dependency_graph(services))

        elif path == "/health":
            self._json_response({"status": "ok"})

        else:
            self._json_response({"error": "not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/services/") and path.endswith("/start"):
            sid = path.split("/")[-2]
            services = load_services()
            svc = get_service_by_id(services, sid)
            if svc:
                result = start_service(svc)
                self._json_response(result)
            else:
                self._json_response({"error": "not found"}, status=404)

        elif path.startswith("/api/services/") and path.endswith("/stop"):
            sid = path.split("/")[-2]
            services = load_services()
            svc = get_service_by_id(services, sid)
            if svc:
                result = stop_service(svc)
                self._json_response(result)
            else:
                self._json_response({"error": "not found"}, status=404)

        else:
            self._json_response({"error": "not found"}, status=404)

    def _json_response(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main() -> int:
    """Run the catalog API server."""
    import argparse

    parser = argparse.ArgumentParser(description="Service Catalog API")
    parser.add_argument("--port", type=int, default=8092, help="Port (default: 8092)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), CatalogHandler)
    print(f"Service Catalog API: http://{args.host}:{args.port}")
    print("Endpoints:")
    print("  GET  /api/services         — List all services")
    print("  GET  /api/services/<id>    — Get service details")
    print("  GET  /api/health           — Health check all services")
    print("  GET  /api/health/<id>      — Health check specific service")
    print("  POST /api/services/<id>/start  — Start a service")
    print("  POST /api/services/<id>/stop   — Stop a service")
    print("  GET  /api/metrics          — Get service metrics")
    print("  GET  /api/dependencies     — Get dependency graph")
    print("Press Ctrl+C to stop")

    def signal_handler(signum, frame):
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
