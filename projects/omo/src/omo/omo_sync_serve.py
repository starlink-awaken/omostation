"""P48-W2 omo/sync 真重构 — stdio JSON-RPC serve 模式.

P47 简化版: internal transport (同进程 importlib).
P48-W2: stdio subprocess 模式, command 走 'python -m omo.omo_sync serve'.
协议同 P33-W4 agora daemon + P48-W0 runtime serve dispatcher:
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 客户端关闭: {"action": "QUIT"}\\n
"""
from __future__ import annotations

import json
import sys
from typing import Any

from omo.omo_sync import run_sync  # P47 internal sync function


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P48-W2: action → omo_sync function 分发."""
    if action == "sync":
        return run_sync(args)
    if action == "ping":
        return {"status": "ok", "result": {"pong": True}}
    return {"status": "error", "error": f"unknown action: {action}"}


def serve() -> int:
    """P48-W2: serve 模式入口, stdio JSON-RPC."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            break
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(
                json.dumps({"status": "error", "error": f"json_decode: {exc}"}) + "\n"
            )
            sys.stdout.flush()
            continue
        action = req.get("action", "")
        args = req.get("args", {}) or {}
        resp = _call_action(action, args)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["serve", "_call_action"]
