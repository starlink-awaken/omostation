#!/usr/bin/env python3
"""Service Gateway Web Dashboard — simple web UI for service status.

Usage:
    python3 bin/ops/dashboard.py [--port 8091]

Then open http://localhost:8091 in your browser.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
PORT = 8091


def get_service_status() -> dict:
    """Get service status by running ops CLI."""
    try:
        result = subprocess.run(
            [sys.executable, str(WORKSPACE / "bin" / "ops" / "cli.py"), "status", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {"summary": {}, "services": []}


def get_summary() -> dict:
    """Get system summary."""
    try:
        result = subprocess.run(
            [sys.executable, str(WORKSPACE / "bin" / "ops" / "cli.py"), "summary"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return {"output": result.stdout}
    except Exception:
        pass
    return {"output": "Error fetching summary"}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Gateway Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h1 { font-size: 24px; color: #00d4aa; }
        .header .refresh { background: #00d4aa; color: #1a1a2e; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card { background: #16213e; border-radius: 8px; padding: 15px; text-align: center; }
        .card .value { font-size: 32px; font-weight: bold; color: #00d4aa; }
        .card .label { font-size: 12px; color: #888; margin-top: 5px; }
        .services { background: #16213e; border-radius: 8px; padding: 15px; }
        .services h2 { font-size: 18px; margin-bottom: 15px; color: #00d4aa; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #2a2a4a; }
        th { color: #888; font-weight: normal; font-size: 12px; }
        .status { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .status.healthy { background: #0d3d2a; color: #00d4aa; }
        .status.stale { background: #3d3d0d; color: #d4d400; }
        .status.missing { background: #3d0d0d; color: #d40000; }
        .status.unreachable { background: #3d0d0d; color: #d40000; }
        .status.disabled { background: #2a2a4a; color: #888; }
        .status.running { background: #0d3d2a; color: #00d4aa; }
        .filters { margin-bottom: 15px; }
        .filters button { background: #2a2a4a; color: #eee; border: none; padding: 6px 12px; border-radius: 4px; margin-right: 5px; cursor: pointer; }
        .filters button.active { background: #00d4aa; color: #1a1a2e; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Service Gateway Dashboard</h1>
        <button class="refresh" onclick="location.reload()">Refresh</button>
    </div>
    <div class="summary" id="summary">
        <div class="card"><div class="value" id="total">-</div><div class="label">Total</div></div>
        <div class="card"><div class="value" id="healthy">-</div><div class="label">Healthy</div></div>
        <div class="card"><div class="value" id="stale">-</div><div class="label">Stale</div></div>
        <div class="card"><div class="value" id="missing">-</div><div class="label">Missing</div></div>
        <div class="card"><div class="value" id="disabled">-</div><div class="label">Disabled</div></div>
    </div>
    <div class="services">
        <h2>Services</h2>
        <div class="filters">
            <button class="active" onclick="filter('all')">All</button>
            <button onclick="filter('healthy')">Healthy</button>
            <button onclick="filter('stale')">Stale</button>
            <button onclick="filter('missing')">Missing</button>
            <button onclick="filter('running')">Running</button>
        </div>
        <table>
            <thead>
                <tr><th>ID</th><th>Type</th><th>Status</th><th>Running</th><th>Port</th></tr>
            </thead>
            <tbody id="services-body"></tbody>
        </table>
    </div>
    <script>
        let servicesData = [];

        async function loadStatus() {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            servicesData = data.services || [];

            document.getElementById('total').textContent = data.summary?.total || 0;
            document.getElementById('healthy').textContent = data.summary?.healthy || 0;
            document.getElementById('stale').textContent = data.summary?.stale || 0;
            document.getElementById('missing').textContent = data.summary?.missing || 0;
            document.getElementById('disabled').textContent = data.summary?.disabled || 0;

            renderTable(servicesData);
        }

        function renderTable(services) {
            const tbody = document.getElementById('services-body');
            tbody.innerHTML = services.map(s => `
                <tr>
                    <td>${s.id}</td>
                    <td>${s.type}</td>
                    <td><span class="status ${s.status}">${s.status}</span></td>
                    <td>${s.running ? '✓' : '-'}</td>
                    <td>${s.port || '-'}</td>
                </tr>
            `).join('');
        }

        function filter(status) {
            document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            if (status === 'all') {
                renderTable(servicesData);
            } else if (status === 'running') {
                renderTable(servicesData.filter(s => s.running));
            } else {
                renderTable(servicesData.filter(s => s.status === status));
            }
        }

        loadStatus();
        setInterval(loadStatus, 30000);  // Auto-refresh every 30s
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the dashboard."""

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())

        elif parsed.path == "/api/status":
            status = get_service_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, ensure_ascii=False).encode())

        elif parsed.path == "/api/summary":
            summary = get_summary()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(summary, ensure_ascii=False).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main() -> int:
    """Run the dashboard server."""
    parser = argparse.ArgumentParser(description="Service Gateway Dashboard")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port (default: {PORT})")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), DashboardHandler)
    print(f"Service Gateway Dashboard: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
