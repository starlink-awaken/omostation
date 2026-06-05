#!/usr/bin/env python3
"""OMO dashboard server — lightweight HTTP dashboard.

Usage:
    omo dashboard --serve :9090
    → Serves single-page HTML at http://localhost:9090
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

OMO_DIR = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))


def _load_json(path: Path) -> dict:
    try:
        import yaml
        data = yaml.safe_load(path.read_text()) or {}
        return data
    except Exception:
        return {}


def _generate_html() -> str:
    """Generate single-page HTML dashboard (no framework, no build step)."""
    system = _load_json(OMO_DIR / "state" / "system.yaml")
    health = _load_json(OMO_DIR / "state" / "system_health.yaml")
    debt = _load_json(OMO_DIR / "debt" / "dashboard" / "current.yaml")
    try:
        kei = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "kei_audit.jsonl"
        kei_lines = len(kei.read_text().strip().split("\n")) if kei.exists() else 0
    except Exception:
        kei_lines = 0

    phase = system.get("current_phase", "?")
    health_score = system.get("health_score", "?")
    services = health.get("services", {}) if isinstance(health, dict) else {}

    debt_total = debt.get("total_items", debt.get("total", 0))
    debt_open = debt.get("open_items", debt.get("open", 0))

    service_rows = ""
    for name, svc in sorted(services.items()):
        if not isinstance(svc, dict):
            continue
        st = svc.get("health_check") or svc.get("runtime", {}).get("status", "") or "?"
        icon = "🟢" if st == "healthy" else "🔴" if st in ("failed", "stopped") else "🟡"
        detail = svc.get("name", name)
        service_rows += f"<tr><td>{icon}</td><td>{detail}</td><td>{st}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta http-equiv="refresh" content="30">
<title>eCOS Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #0d1117; color: #c9d1d9; }}
  h1 {{ color: #58a6ff; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 16px 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .card h3 {{ margin: 0 0 8px; color: #8b949e; font-size: 14px; }}
  .card .value {{ font-size: 28px; font-weight: bold; color: #58a6ff; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th, td {{ text-align: left; padding: 6px 12px; border-bottom: 1px solid #30363d; }}
  th {{ color: #8b949e; font-weight: normal; }}
  .section {{ margin: 24px 0; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; background: #21262d; }}
</style>
</head>
<body>
<h1>eCOS Dashboard <span class="badge">Phase {phase}</span></h1>
<div class="cards">
  <div class="card"><h3>Health Score</h3><div class="value">{health_score}</div></div>
  <div class="card"><h3>Services</h3><div class="value">{len(services)}</div></div>
  <div class="card"><h3>Debt Items</h3><div class="value">{debt_total}</div></div>
  <div class="card"><h3>Open Debt</h3><div class="value">{debt_open}</div></div>
  <div class="card"><h3>KEI Audit</h3><div class="value">{kei_lines}</div></div>
</div>

<div class="section">
<h2>Service Health</h2>
<table><tr><th></th><th>Service</th><th>Status</th></tr>{service_rows}</table>
</div>

<footer style="margin-top:32px;color:#484f58;font-size:12px">
  eCOS Dashboard · {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")} · auto-refresh 30s
</footer>
</body></html>"""
    return html


def cmd_dashboard_serve(port: int) -> int:
    """Start HTTP server serving the dashboard."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            html = _generate_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[dashboard] {args[0]} {args[1]} {args[2]}\n")

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)  # noqa: S104
    print(f"🚀 eCOS Dashboard: http://localhost:{port}")
    print(f"   Auto-refresh: 30s")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo dashboard", description="eCOS Dashboard server")
    sub = parser.add_subparsers(dest="command")
    ds = sub.add_parser("serve", help="Start HTTP dashboard server")
    ds.add_argument("--port", "-p", type=int, default=9090, help="Port (default: 9090)")
    args = parser.parse_args(argv)
    if args.command == "serve":
        return cmd_dashboard_serve(args.port)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
