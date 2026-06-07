"""P49-simplify: 通用 stdio JSON-RPC serve helper.

抽取 18+ 重复 serve 函数 (omo_sync_serve / runtime_serve / 16 kairon __main__)
的共同循环, 提供单入口 run_stdio_dispatch(dispatch_fn, on_quit=None).

用法:
    from omo.omo_stdio_rpc import run_stdio_dispatch

    def _call_action(action, args):
        if action == "sync":
            return run_sync(args)
        return {"status": "error", "error": f"unknown: {action}"}

    def serve() -> int:
        return run_stdio_dispatch(_call_action)

协议 (P33-W4 stdio JSON-RPC):
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 关闭: {"action": "QUIT"}\\n
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

DispatchFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_stdio_dispatch(
    dispatch_fn: DispatchFn,
    on_quit: Callable[[], None] | None = None,
) -> int:
    """P49-simplify: 通用 stdio JSON-RPC serve 入口.

    读 stdin JSON 行, 调 dispatch_fn(action, args), 写 stdout JSON 行.
    QUIT 关闭 (可选 on_quit 钩子).
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            if on_quit is not None:
                on_quit()
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
        try:
            result = dispatch_fn(action, args)
            resp = result if isinstance(result, dict) and "status" in result else {
                "status": "ok",
                "result": result,
            }
        except Exception as exc:
            resp = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["run_stdio_dispatch", "DispatchFn"]
