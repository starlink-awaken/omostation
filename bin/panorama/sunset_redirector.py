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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TARGET = os.environ.get("PANORAMA_TARGET_URL", "http://localhost:5173/panorama")
DEFAULT_PORT = int(os.environ.get("SUNSET_PORT", "43910"))
# 根是参数不是事实 (ADR-0456)：优先 PANORAMA_ROOT（与 collector 同一 seam），
# 未声明时回退到本文件的相对布局，行为与历史逐字节一致。
ROOT = Path(os.environ.get("PANORAMA_ROOT") or Path(__file__).resolve().parents[2])
RUNTIME_DATA_PATH = ROOT / "runtime" / "dashboard" / "data.json"
# 扁平 data.json 由 launchd com.omostation.panorama-dashboard-refresh 每 240s 写入。
# 2026-09-23→09-27 该 job 被静默 disable 期间，:43910 对外把 2 天前的旧快照当
# "最新遥测" 提供且无任何标记 —— 因此超 cadence 必须显式标注 stale。
REFRESH_CADENCE_SECONDS = int(os.environ.get("PANORAMA_REFRESH_SECONDS", "240"))
DATA_STALE_SECONDS = int(
    os.environ.get("SUNSET_DATA_STALE_SECONDS", str(REFRESH_CADENCE_SECONDS * 3))
)


def _read_runtime_snapshot() -> dict[str, Any] | None:
    """读扁平 data.json；缺失或不可解析时返回 None（交由降级载荷兜底）。"""
    if not RUNTIME_DATA_PATH.is_file():
        return None
    try:
        with open(RUNTIME_DATA_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:  # noqa: BLE001 - 兼容层绝不因坏数据 500
        return None
    return payload if isinstance(payload, dict) else None


def runtime_freshness(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """扁平快照新鲜度：生成时间 / 年龄秒 / 是否 stale。

    generated_at 缺失或不可解析一律按 stale 处理（fail-visible，不 fail-closed）。
    """
    if snapshot is None:
        snapshot = _read_runtime_snapshot()
    generated_at = snapshot.get("generated_at") if snapshot else None
    age_seconds: float | None = None
    if isinstance(generated_at, str):
        try:
            generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if generated.tzinfo is None:
                generated = generated.replace(tzinfo=timezone.utc)
            age_seconds = round((datetime.now(timezone.utc) - generated).total_seconds(), 1)
        except ValueError:
            age_seconds = None
    return {
        "path": str(RUNTIME_DATA_PATH),
        "generated_at": generated_at if isinstance(generated_at, str) else None,
        "age_seconds": age_seconds,
        "stale": age_seconds is None or age_seconds > DATA_STALE_SECONDS,
        "stale_after_seconds": DATA_STALE_SECONDS,
    }


def get_latest_telemetry() -> dict[str, Any]:
    """读取最新的运行态遥测数据快照，如果不存在则返回基础降级载荷.

    返回值始终附带 ``_meta`` 新鲜度标签，调用方一眼可见数据是否已过 cadence。
    """
    snapshot = _read_runtime_snapshot()
    if snapshot is not None:
        snapshot["_meta"] = runtime_freshness(snapshot)
        return snapshot

    return {
        "status": "CONVERGED_TO_COCKPIT",
        "message": "Dashboard has converged to Cockpit-UI at http://localhost:5173/panorama",
        "target": DEFAULT_TARGET,
        "gates": [],
        "guardian": {"healthScore": 100.0, "status": "HEALTHY"},
        "_meta": runtime_freshness(),
    }


class SunsetRedirectHandler(http.server.BaseHTTPRequestHandler):
    target_url: str = DEFAULT_TARGET

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # 静默常规日志，避免刷屏
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        # 1. 探活健康检查（同时暴露扁平快照新鲜度，stale 不再静默）
        if path == "/health":
            freshness = runtime_freshness()
            body = json.dumps({
                "status": "SUNSET_REDIRECTING",
                "target": self.target_url,
                "converged": True,
                "data_generated_at": freshness["generated_at"],
                "data_age_seconds": freshness["age_seconds"],
                "data_stale": freshness["stale"],
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
