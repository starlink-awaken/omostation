#!/usr/bin/env python3
"""sunset_redirector.py — 治理双核下线平稳过渡与端口导流守护器 (BET-Y2Q2-T11-04).

用途:
  随着 Cockpit-UI (:5173 / :8090, /panorama) 正式确立为 omostation 唯一人类总控主入口，
  原 :43191 (知行底座) 与 :43910 (Panorama 静态服务) 进入下线导流阶段。
  本守护服务监听历史端口:
    1. 人类浏览器访问根路径/页面时，HTTP 302 自动重定向至 http://localhost:5173/panorama；
    2. 老旧脚本访问 /api/* 数据接口时，提供最新遥测快照 JSON 响应，确保平稳过渡与零业务中断。
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_TARGET = os.environ.get("PANORAMA_TARGET_URL", "http://localhost:5173/panorama")
DEFAULT_PORT = int(os.environ.get("SUNSET_PORT", "43910"))
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DATA_PATH = ROOT / "runtime" / "dashboard" / "data.json"


def get_latest_telemetry() -> dict[str, Any]:
    """读取最新的运行态遥测数据快照，如果不存在则返回基础降级载荷."""
    if RUNTIME_DATA_PATH.is_file():
        try:
            with open(RUNTIME_DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass

    return {
        "status": "CONVERGED_TO_COCKPIT",
        "message": "Dashboard has converged to Cockpit-UI at http://localhost:5173/panorama",
        "target": DEFAULT_TARGET,
        "gates": [],
        "guardian": {"healthScore": 100.0, "status": "HEALTHY"},
    }


class SunsetRedirectHandler(http.server.BaseHTTPRequestHandler):
    target_url: str = DEFAULT_TARGET

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # 静默常规日志，避免刷屏
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        # 1. 探活健康检查
        if path == "/health":
            body = json.dumps({
                "status": "SUNSET_REDIRECTING",
                "target": self.target_url,
                "converged": True,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 2. API 数据接口兼容
        if path.startswith("/api/") or path.endswith(".json"):
            data = get_latest_telemetry()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 3. 页面访问: 302 重定向至 Cockpit-UI 全景控制舱
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="1;url={self.target_url}">
  <title>正在进入织星体系全景控制舱...</title>
  <style>
    body {{
      background: #020617;
      color: #94a3b8;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
    }}
    .card {{
      background: #0f172a;
      border: 1px solid #1e293b;
      padding: 32px 40px;
      border-radius: 16px;
      text-align: center;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    h1 {{ color: #38bdf8; font-size: 20px; margin-bottom: 8px; }}
    p {{ font-size: 14px; margin: 12px 0; }}
    a {{ color: #818cf8; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🏛️ 双核已归一至 Cockpit-UI 全景控制舱</h1>
    <p>正在自动跳转中，若未跳转请点击：</p>
    <p><a href="{self.target_url}">{self.target_url}</a></p>
  </div>
</body>
</html>
""".encode("utf-8")

        self.send_response(302)
        self.send_header("Location", self.target_url)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def run_redirector(port: int = DEFAULT_PORT, target: str = DEFAULT_TARGET) -> None:
    SunsetRedirectHandler.target_url = target
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), SunsetRedirectHandler)
    print(f"🔄 Sunset Redirector listening on http://127.0.0.1:{port} -> {target}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown redirector.")
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sunset Redirector for legacy dashboard ports")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--target", type=str, default=DEFAULT_TARGET, help="Target Cockpit URL to redirect to")
    args = parser.parse_args()

    run_redirector(port=args.port, target=args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
