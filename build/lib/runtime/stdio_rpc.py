"""P49-simplify: 通用 stdio JSON-RPC serve helper (runtime 仓版, 跨仓复制自 omo.omo_stdio_rpc).

P49-W1 runtime_serve.py 共用此 helper.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

DispatchFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_stdio_dispatch(
    dispatch_fn: DispatchFn,
    on_quit: Callable[[], None] | None = None,
) -> int:
    """读 stdin JSON 行, 调 dispatch_fn(action, args), 写 stdout JSON 行."""
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
            resp = (
                result
                if isinstance(result, dict) and "status" in result
                else {"status": "ok", "result": result}
            )
        except Exception as exc:
            resp = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["run_stdio_dispatch", "DispatchFn"]
