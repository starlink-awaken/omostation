#!/usr/bin/env python3
"""
Autonomous Daemon Watchdog & Self-Healing Supervisor (ADR-0427 / Phase 8)
========================================================================
Proactively monitors the Agora 2.0 In-Memory Bus (:7432) and BOS services.
Automatically heals and restarts downed services with zero human intervention.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

# Add workspace environment via cockpit.env_resolver
_ROOT = Path(__file__).resolve().parents[2]
_COCKPIT_SRC = _ROOT / "projects" / "cockpit" / "src"
if _COCKPIT_SRC.is_dir() and str(_COCKPIT_SRC) not in sys.path:
    sys.path.insert(0, str(_COCKPIT_SRC))

from cockpit.env_resolver import setup_workspace_paths, get_workspace_root  # noqa: E402

_ROOT = setup_workspace_paths()

HEALTH_URL = "http://127.0.0.1:7432/health"
STATUS_FILE = _ROOT / ".omo" / "state" / "daemon-watchdog.json"
LOG_FILE = _ROOT / ".omo" / "_delivery" / "watchdog.log"
_REFUSAL_MESSAGE = (
    "Mesh successor is pending; Cockpit PR #78 is retirement evidence only, "
    "never the delivered successor."
)


def _refuse_retired_surface(command: str) -> NoReturn:
    print(
        json.dumps(
            {
                "ok": False,
                "status": "retired",
                "successor": "Mesh-bound capability admission",
                "successor_status": "pending",
                "retirement_evidence": "Cockpit PR #78",
                "value_indicator_policy": False,
                "command": command,
                "message": _REFUSAL_MESSAGE,
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(2)


def check_daemon_health(timeout: float = 2.0) -> dict:
    """Probes the Agora daemon /health endpoint."""
    _refuse_retired_surface("daemon-watchdog.check_daemon_health")
    start_time = time.time()
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "omostation-watchdog/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "ok": True,
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "port": 7432,
                    "raw": data,
                }
            return {
                "ok": False,
                "status": f"http_{response.status}",
                "latency_ms": latency_ms,
                "port": 7432,
            }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "ok": False,
            "status": "unreachable",
            "error": str(e),
            "latency_ms": latency_ms,
            "port": 7432,
        }


def restart_daemon() -> bool:
    """Attempts self-healing restart via cockpit daemon manager."""
    _refuse_retired_surface("daemon-watchdog.restart_daemon")
    try:
        from cockpit.commands.daemon import restart_daemon_service
        restart_daemon_service()
        time.sleep(1.0)
        # Verify restart success
        probe = check_daemon_health(timeout=3.0)
        return probe["ok"]
    except Exception as e:
        log_event(f"Restart failed: {e}")
        return False


def log_event(message: str):
    """Appends an event to the watchdog log."""
    _refuse_retired_surface("daemon-watchdog.log_event")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def run_watchdog(fix: bool = True, output_json: bool = False) -> int:
    """Executes a single watchdog scan cycle."""
    _refuse_retired_surface("daemon-watchdog.run_watchdog")
    probe = check_daemon_health()
    healed = False

    if not probe["ok"] and fix:
        log_event(f"Daemon unhealthy ({probe['status']}). Initiating self-healing restart...")
        if restart_daemon():
            probe = check_daemon_health()
            healed = True
            log_event("Self-healing successful. Daemon is now healthy.")
        else:
            log_event("Self-healing restart attempt failed.")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe": probe,
        "self_healed": healed,
        "healthy": probe["ok"],
    }

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if output_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if probe["ok"]:
            heal_str = " (Auto-Healed)" if healed else ""
            print(f"✅ Agora 2.0 总线健康: :7432 [Latency: {probe['latency_ms']}ms]{heal_str}")
        else:
            print(f"❌ Agora 2.0 总线异常: {probe.get('error', probe['status'])}")

    return 0 if probe["ok"] else 1


def main():
    _refuse_retired_surface("daemon-watchdog")
    parser = argparse.ArgumentParser(description="Autonomous Daemon Watchdog (ADR-0427)")
    parser.add_argument("--fix", action="store_true", default=True, help="Auto-heal downed services")
    parser.add_argument("--no-fix", dest="fix", action="store_false", help="Do not attempt auto-heal")
    parser.add_argument("--json", action="store_true", help="Output JSON status")
    args = parser.parse_args()

    sys.exit(run_watchdog(fix=args.fix, output_json=args.json))


if __name__ == "__main__":
    main()
