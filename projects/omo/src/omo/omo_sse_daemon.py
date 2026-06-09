"""
OMO SSE Daemon (Experimental)
Phase 34 Wave 3: Event-Driven Transition.
Listens to Agora's SSE Event Bus instead of polling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys

import httpx

from omo.omo_daemon import run_once, _write_pid_file, _clear_pid_file, _setup_logging
from omo.omo_paths import OMO_ROOT
SSE_DAEMON_PORT = os.environ.get("OMO_SSE_DAEMON_PORT", "9091")

from omo.omo_self_healing import get_healing_engine, start_http_status_server, start_hot_reload, notify_webhook

DAEMON_PID_FILE = OMO_ROOT / ".omo" / "_delivery" / "sse_daemon.pid"
DAEMON_LOG_FILE = OMO_ROOT / ".omo" / "_delivery" / "sse_daemon.log"

AGORA_SSE_URL = os.environ.get("AGORA_SSE_URL", "http://127.0.0.1:8080/v1/events")
ENABLE_SELF_HEALING = os.environ.get("OMO_SELF_HEALING", "1") == "1"
ENABLE_NOTIFICATIONS = os.environ.get("OMO_NOTIFY", "0") == "1"


def _send_notification(title: str, message: str) -> None:
    """发送 macOS 桌面通知。"""
    if not ENABLE_NOTIFICATIONS:
        return
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"',
        ], capture_output=True, timeout=3)
    except Exception:
        pass


async def listen_to_sse(stop_event: asyncio.Event, logger: logging.Logger):
    """Connect to Agora SSE, run OMO sync + self-healing on events."""
    logger.info(f"Connecting to Agora SSE bus at {AGORA_SSE_URL}...")
    healing = get_healing_engine() if ENABLE_SELF_HEALING else None
    if healing:
        logger.info(f"Self-healing engine enabled: {len(healing._rules)} rules configured")

    timeout = httpx.Timeout(None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        while not stop_event.is_set():
            try:
                async with client.stream("GET", AGORA_SSE_URL) as response:
                    if response.status_code != 200:
                        logger.error(f"Failed to connect to SSE: HTTP {response.status_code}")
                        await asyncio.sleep(5)
                        continue

                    logger.info("SSE Connection established.")

                    async for line in response.aiter_lines():
                        if stop_event.is_set():
                            break

                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                event = json.loads(data_str)
                                ev_type = event.get("type", "UNKNOWN")
                                logger.info(f"Received event: {ev_type}")

                                # 事件类型路由:
                                # 治理/债务/完成类事件 → 运行 OMO Sync + audit
                                # 错误/宕机/超时 → 运行 self-healing
                                # 其他 → 仅计数 (不触发全量 audit)

                                _governance_types = (
                                    "pipeline:completed", "pipeline:step:ok",
                                    "registry:service.registered", "node_completed",
                                    "debt:created", "debt:reviewed",
                                )
                                if ev_type in _governance_types or ev_type.startswith("pipeline:") or ev_type.startswith("debt:"):
                                    loop = asyncio.get_running_loop()
                                    tick_result = await loop.run_in_executor(None, run_once)
                                    if tick_result.error:
                                        logger.error(f"tick_error: {tick_result.error}")
                                    else:
                                        logger.info(
                                            f"tick_done score={tick_result.audit_score} diffs={tick_result.sync_diff_count}"
                                        )

                                # Run self-healing engine (所有事件都送入)
                                if healing:
                                    healing_actions = await healing.on_event(event)
                                    if healing_actions:
                                        logger.warning(
                                            "self_healing_triggered actions=%s",
                                            json.dumps(healing_actions, default=str)[:500],
                                        )
                                        # 通知
                                        for ha in healing_actions:
                                            if ha.get("severity") in ("critical", "high") or any(
                                                a.get("type") == "debt_created" for a in ha.get("actions", [])
                                            ):
                                                _send_notification(
                                                    f"OMO Self-Healing: {ha['rule']}",
                                                    f"事件 {ha['event_type']} × {ha['count']} 触发 {ha['rule']}",
                                                )
                                                notify_webhook(ha["rule"], ha["event_type"], ha["count"], ha.get("severity", "warning"))

                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_str}")

                        elif line == ": ping":
                            pass
                            
            except httpx.RequestError as e:
                if not stop_event.is_set():
                    logger.error(f"SSE connection error: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
            except Exception as e:
                if not stop_event.is_set():
                    logger.exception(f"Unexpected error in SSE loop: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)


def main():
    if DAEMON_PID_FILE.exists():
        try:
            pid = int(DAEMON_PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"ERROR: SSE daemon already running (PID {pid})", file=sys.stderr)
            sys.exit(1)
        except OSError:
            pass

    _write_pid_file(DAEMON_PID_FILE)
    logger = _setup_logging(DAEMON_LOG_FILE)
    logger.info(f"omo_sse_daemon_started pid={os.getpid()}")

    # Start HTTP health server (SSE_DAEMON_PORT env override) for status queries
    start_http_status_server()
    logger.info("healing_http_server_started port=" + SSE_DAEMON_PORT)

    # Start hot-reload for config changes
    start_hot_reload()
    logger.info("healing_hot_reload_started")
    logger.info("healing_http_server_started port=" + SSE_DAEMON_PORT)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _handle_signal(signum, _frame):
        logger.info(f"omo_sse_daemon_signal_received signum={signum}")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        loop.run_until_complete(listen_to_sse(stop_event, logger))
    finally:
        _clear_pid_file(DAEMON_PID_FILE)
        logger.info("omo_sse_daemon_stopped")
        loop.close()


if __name__ == "__main__":
    main()
