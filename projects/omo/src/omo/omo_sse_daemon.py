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
import sys
from pathlib import Path

import httpx

from omo.omo_daemon import run_once, _write_pid_file, _clear_pid_file, _setup_logging
from omo.omo_paths import OMO_ROOT

DAEMON_PID_FILE = OMO_ROOT / ".omo" / "_delivery" / "sse_daemon.pid"
DAEMON_LOG_FILE = OMO_ROOT / ".omo" / "_delivery" / "sse_daemon.log"

AGORA_SSE_URL = os.environ.get("AGORA_SSE_URL", "http://127.0.0.1:8080/v1/events")


async def listen_to_sse(stop_event: asyncio.Event, logger: logging.Logger):
    """Connect to Agora SSE and trigger omo logic on events."""
    logger.info(f"Connecting to Agora SSE bus at {AGORA_SSE_URL}...")
    
    timeout = httpx.Timeout(None)  # no timeout for long-lived connection
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
                                
                                # Run OMO Sync in thread pool to avoid blocking SSE read
                                loop = asyncio.get_running_loop()
                                tick_result = await loop.run_in_executor(None, run_once)
                                
                                if tick_result.error:
                                    logger.error(f"tick_error: {tick_result.error}")
                                else:
                                    logger.info(f"tick_done score={tick_result.audit_score} diffs={tick_result.sync_diff_count}")
                                    
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_str}")
                                
                        elif line == ": ping":
                            # Keep-alive
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
