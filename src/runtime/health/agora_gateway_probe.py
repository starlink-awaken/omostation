#!/usr/bin/env python3
"""agora-gateway 健康探针 — 进程存活 + 后端心跳健康度, 替代 HTTP /health.

Gateway 是 ProxyManager (MCP stdio 子进程管理), 无 HTTP 端口。
探针三态返回:
    0 = healthy   (PID 活 + 无 fatal + 后端有响应)
    1 = unhealthy (PID 死 / fatal / 后端全死)
    2 = degraded  (PID 活但部分后端无心跳响应; stdio 按需服务不响应属预期, 可能误报)

heartbeat 检测 parse gateway-stdout.log 最新 heartbeat_report 行
(alive/dead/total)。全死才 unhealthy, 部分死只 degraded — 假 dead 噪音
不淹没真病, 也不把 stdio 按需服务误判成瘫 (见 ADR-0179 / p76-launcher-zombie)。

Usage:
    python bin/health/agora-gateway-probe.py
    echo $?  # 0=healthy, 1=unhealthy, 2=degraded
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PID_FILE = Path.home() / "runtime" / "agora-gateway.pid"
LOG_FILE = Path.home() / ".agora" / "logs" / "gateway-stdout.log"
# heartbeat_report alive=6 dead=14 total=20
_HEARTBEAT_RE = re.compile(r"heartbeat_report.*alive=(\d+).*dead=(\d+).*total=(\d+)")


def main() -> int:
    # 1. PID
    pid = _find_pid()
    if pid is None:
        print("[PROBE] agora-gateway: PID not found")
        return 1
    if not _check_pid(pid):
        print(f"[PROBE] agora-gateway: PID {pid} dead")
        return 1

    # 2. 最近 fatal 错误
    if LOG_FILE.exists():
        recent = LOG_FILE.read_text(errors="replace")[-5000:]
        if "FATAL" in recent or "Traceback" in recent:
            print(f"[PROBE] agora-gateway: PID {pid} running but recent fatal in log")
            return 1

    # 3. 后端心跳健康度 (agora hub 代理的子服务响应率)
    hb = _check_heartbeat()
    if hb is not None:
        alive, dead, total = hb
        if total > 0 and alive == 0:
            print(
                f"[PROBE] agora-gateway: PID {pid} alive but ALL {total} backends dead"
            )
            return 1
        if dead > 0:
            print(
                f"[PROBE] agora-gateway: PID {pid} degraded — "
                f"{dead}/{total} backends unresponsive (stdio transient likely)"
            )
            return 2

    print(f"[PROBE] agora-gateway: PID {pid} healthy")
    return 0


def _find_pid() -> int | None:
    # pidfile
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
    # launchctl (launchd KeepAlive 管理的真实 PID)
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.agora.gateway"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        m = re.search(r'"PID"\s*=\s*(\d+)', result.stdout)
        if m:
            return int(m.group(1))
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    # pgrep fallback
    try:
        result = subprocess.run(
            ["pgrep", "-f", "agora"],
            capture_output=True,
            text=True,
            timeout=5,
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


def _check_heartbeat() -> tuple[int, int, int] | None:
    """Parse 最新 heartbeat_report 行, 返回 (alive, dead, total).

    日志格式: [warning] heartbeat_report alive=6 dead=14 total=20
    找不到则 None (日志无此信息, 不据此判病)。
    """
    if not LOG_FILE.exists():
        return None
    try:
        tail = LOG_FILE.read_text(errors="replace")[-20000:]
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        m = _HEARTBEAT_RE.search(line)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


if __name__ == "__main__":
    sys.exit(main())
