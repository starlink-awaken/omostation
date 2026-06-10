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
        return run_stdio_dispatch(_call_action, daemon_mode=True)  # P64-W0

协议 (P33-W4 stdio JSON-RPC):
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 关闭: {"action": "QUIT"}\\n

P64-W0: 加 daemon_mode 参数 (镜像 P63-W0-D kairon 模式) — launchd plist 没 pipe stdin,
daemon 模式 EOF sleep 30s 重试, 避免 KeepAlive 重启风暴. 正常模式立即 return 0 (P49-W0 era).
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable

DispatchFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_stdio_dispatch(
    dispatch_fn: DispatchFn,
    on_quit: Callable[[], None] | None = None,
    daemon_mode: bool = False,
    restart_delay_sec: int = 0,
) -> int:
    """P49-simplify: 通用 stdio JSON-RPC serve 入口.
    P64-W0: 加 daemon_mode 参数.
    /simplify P68 review: 加 restart_delay_sec 参数 (镜像 kairon_utils helper, 防漂移).

    读 stdin JSON 行, 调 dispatch_fn(action, args), 写 stdout JSON 行.
    QUIT 关闭 (可选 on_quit 钩子).

    3 模式 (跟 kairon_utils.stdio_rpc 一致):
    - daemon_mode=False: stdin EOF 立即 return 0 (P49-W0 era 默认).
    - daemon_mode=True, restart_delay_sec=0: EOF sleep 30s + retry forever.
    - daemon_mode=True, restart_delay_sec=N: EOF sleep Ns + return 0 (配 launchd 重启).
    """
    while True:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "QUIT":
                if on_quit is not None:
                    on_quit()
                return 0
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
        # stdin EOF
        if not daemon_mode:
            return 0
        if restart_delay_sec > 0:
            sys.stderr.write(f"[daemon] stdin EOF, sleep {restart_delay_sec}s then exit (launchd restart)\n")
            sys.stderr.flush()
            time.sleep(restart_delay_sec)
            return 0
        sys.stderr.write("[daemon] stdin EOF, sleep 30s then retry (forever)\n")
        sys.stderr.flush()
        time.sleep(30)


__all__ = ["run_stdio_dispatch", "DispatchFn"]
