#!/usr/bin/env python3
"""
Agora Watchdog (P2 SPOF Mitigation)
Monitors the Agora /v1/health endpoint. If it times out or fails 3 times consecutively,
it finds and kills the agora process to allow the system process manager (e.g. systemd or run-all.sh)
to restart it.
"""

import os
import time
import subprocess
import httpx
import logging
import signal

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("agora.watchdog")

AGORA_HEALTH_URL = os.environ.get("AGORA_HEALTH_URL", "http://127.0.0.1:8080/v1/health")
CHECK_INTERVAL = 10
MAX_FAILURES = 3


def get_agora_pids():
    """Finds PIDs of running agora processes using pgrep."""
    try:
        # Looking for processes that match 'agora' but excluding watchdog
        result = subprocess.run(
            ["pgrep", "-f", "agora"], capture_output=True, text=True
        )
        if result.returncode == 0:
            pids = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                pid = int(line)
                if pid != os.getpid():
                    pids.append(pid)
            return pids
        return []
    except Exception as e:
        logger.error(f"Failed to pgrep agora: {e}")
        return []


def main():
    logger.info(
        f"Agora Watchdog started. Monitoring {AGORA_HEALTH_URL} every {CHECK_INTERVAL}s"
    )
    failures = 0

    while True:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(AGORA_HEALTH_URL)
                resp.raise_for_status()
                failures = 0  # reset
        except Exception as e:
            failures += 1
            logger.warning(f"Health check failed ({failures}/{MAX_FAILURES}): {e}")

            if failures >= MAX_FAILURES:
                logger.error("Agora is unresponsive. Initiating kill sequence...")
                pids = get_agora_pids()
                if not pids:
                    logger.warning("Could not find any agora PIDs to kill.")
                else:
                    for pid in pids:
                        logger.info(f"Killing agora process PID {pid} (SIGKILL)")
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except OSError as kille:
                            logger.error(f"Failed to kill PID {pid}: {kille}")

                # Reset failures to avoid spamming kill, wait for restart
                failures = 0
                time.sleep(15)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
