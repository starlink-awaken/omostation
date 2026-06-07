"""P48-W2 omo/sync 真重构 — stdio JSON-RPC serve 模式 (P49-simplify 用 omo_stdio_rpc helper).

P47 简化版: internal transport (同进程 importlib).
P48-W2: stdio subprocess 模式, command 走 'python -m omo.omo_sync serve'.
"""
from __future__ import annotations

from typing import Any

from omo.omo_stdio_rpc import run_stdio_dispatch
from omo.omo_sync import run_sync  # P47 internal sync function


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P48-W2: action → omo_sync function 分发."""
    if action == "sync":
        return run_sync(args)
    if action == "ping":
        return {"status": "ok", "result": {"pong": True}}
    return {"status": "error", "error": f"unknown action: {action}"}


def serve() -> int:
    """P48-W2: serve 模式入口 (P49-simplify 用 omo_stdio_rpc 共用 helper)."""
    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action"]
