#!/usr/bin/env python3
"""omostation 主脑调度常驻守护 (Core Daemon - com.omostation.core)"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")
CORE_HEARTBEAT_FILE = WORKSPACE_ROOT / ".omo" / "state" / "core-heartbeat.json"


def write_heartbeat():
    CORE_HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "daemon": "com.omostation.core",
        "status": "active",
        "last_tick": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    }
    CORE_HEARTBEAT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def run_tick():
    write_heartbeat()


def main():
    print(f"[{datetime.now().isoformat()}] com.omostation.core daemon started (PID={os.getpid()})")
    while True:
        try:
            run_tick()
        except Exception as e:
            print(f"Core tick error: {e}", file=sys.stderr)
        time.sleep(30)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_tick()
        print("Core daemon ran once successfully.")
    else:
        main()
