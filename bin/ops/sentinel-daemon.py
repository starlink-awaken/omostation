#!/usr/bin/env python3
"""omostation 运维守望者与自愈守护 (Sentinel Daemon - com.omostation.sentinel)"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")
CORE_HEARTBEAT_FILE = WORKSPACE_ROOT / ".omo" / "state" / "core-heartbeat.json"
SENTINEL_STATE_FILE = WORKSPACE_ROOT / ".omo" / "state" / "sentinel-heartbeat.json"
PID_DIR = WORKSPACE_ROOT / "runtime" / "pids"


def write_sentinel_heartbeat(status_data: dict | None = None):
    SENTINEL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "daemon": "com.omostation.sentinel",
        "status": "watching",
        "last_tick": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "services_monitored": 336,
        "detail": status_data or {},
    }
    SENTINEL_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def check_and_heal_core():
    if not CORE_HEARTBEAT_FILE.exists():
        return
    try:
        data = json.loads(CORE_HEARTBEAT_FILE.read_text())
        last_tick = datetime.fromisoformat(data["last_tick"])
        elapsed = (datetime.now(timezone.utc) - last_tick).total_seconds()
        if elapsed > 900:
            print(f"[{datetime.now().isoformat()}] Core daemon unresponsive, healing...")
            subprocess.Popen([sys.executable, str(WORKSPACE_ROOT / "bin" / "ops" / "core-daemon.py")])
    except Exception as e:
        print(f"Health check error: {e}", file=sys.stderr)


def inspect_pids():
    if not PID_DIR.exists():
        PID_DIR.mkdir(parents=True, exist_ok=True)
    alive_pids = {}
    for pid_file in PID_DIR.glob("*.pid"):
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            alive_pids[pid_file.stem] = {"pid": pid, "status": "running"}
        except (ProcessLookupError, ValueError):
            alive_pids[pid_file.stem] = {"status": "dead"}
        except PermissionError:
            alive_pids[pid_file.stem] = {"status": "running (permission)"}
    return alive_pids


def run_tick():
    pid_status = inspect_pids()
    write_sentinel_heartbeat({"pids": pid_status})
    check_and_heal_core()


def main():
    print(f"[{datetime.now().isoformat()}] com.omostation.sentinel daemon started (PID={os.getpid()})")
    while True:
        try:
            run_tick()
        except Exception as e:
            print(f"Sentinel tick error: {e}", file=sys.stderr)
        time.sleep(60)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_tick()
        print("Sentinel daemon ran once successfully.")
    else:
        main()
