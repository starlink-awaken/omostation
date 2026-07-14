#!/usr/bin/env python3
"""agora-gateway health probe — 检查进程是否存活, 替代 HTTP /health.

Gateway 是 ProxyManager (MCP stdio 子进程管理), 无 HTTP 端口。
探针只需确认 PID 在运行 + 最近 stderr 没有 fatal 错误。

Usage:
    python bin/health/agora-gateway-probe.py
    echo $?  # 0=healthy, 1=unhealthy
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PID_FILE = Path.home() / "runtime" / "agora-gateway.pid"
LOG_FILE = Path.home() / "Library" / "Logs" / "agora-gateway.log"


def main() -> int:
    # 1. Try PID from common locations
    pid = _find_pid()
    if pid is None:
        print("[PROBE] agora-gateway: PID not found")
        return 1

    # 2. Check if PID is alive
    alive = _check_pid(pid)
    if not alive:
        print(f"[PROBE] agora-gateway: PID {pid} dead")
        return 1

    # 3. Check log for recent fatal errors
    if LOG_FILE.exists():
        recent = LOG_FILE.read_text(errors="replace")[-5000:]
        if "FATAL" in recent or "Traceback" in recent:
            print(f"[PROBE] agora-gateway: PID {pid} running but recent error in log")
            return 1

    print(f"[PROBE] agora-gateway: PID {pid} healthy")
    return 0


def _find_pid() -> int | None:
    # Try pidfile
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass

    # Try pgrep
    try:
        result = subprocess.run(
            ["pgrep", "-f", "agora.auth.mcp_gateway"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass

    return None


def _check_pid(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
