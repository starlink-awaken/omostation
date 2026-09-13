#!/usr/bin/env python3
"""Service Keeper — ensures core services (Agora/Cockpit/KOS) stay running.

Usage:
  python3 bin/ssot/service-keeper.py check
  python3 bin/ssot/service-keeper.py start
  python3 bin/ssot/service-keeper.py status
  python3 bin/ssot/service-keeper.py install  # install launchd plists
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SERVICES = {
    "agora-sse": {
        "port": 7431,
        "health": "/health",
        "start_cmd": [
            "uv", "run", "--directory", str(ROOT / "projects" / "agora"),
            "agora-mcp", "--sse",
        ],
        "log_file": ROOT / "runtime" / "agora-sse.log",
    },
    "cockpit-dashboard": {
        "port": 8090,
        "health": "/",
        "start_cmd": [
            "uv", "run", "--directory", str(ROOT / "projects" / "cockpit"),
            "python", "-m", "cockpit.dashboard_server",
        ],
        "log_file": ROOT / "runtime" / "cockpit-dashboard.log",
    },
    "kos-api": {
        "port": 8766,
        "health": "/health",
        "start_cmd": [
            sys.executable,
            str(ROOT / "projects" / "knowledge" / "kairon" / "packages" / "kos" / "src" / "kos" / "api" / "__init__.py"),
        ],
        "env": {"PYTHONPATH": str(ROOT / "projects" / "knowledge" / "kairon" / "packages" / "kos" / "src")},
        "log_file": ROOT / "runtime" / "kos-api.log",
    },
}


def check_port(port: int) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
        return True
    except Exception:
        return False


def check_service(name: str) -> dict:
    svc = SERVICES[name]
    running = check_port(svc["port"])
    return {
        "name": name,
        "port": svc["port"],
        "running": running,
        "label": f"com.omostation.{name}",
    }


def start_service(name: str) -> bool:
    svc = SERVICES[name]
    if check_port(svc["port"]):
        print(f"  {name} already running on port {svc['port']}")
        return True

    svc["log_file"].parent.mkdir(parents=True, exist_ok=True)
    log = open(svc["log_file"], "a")
    env = os.environ.copy()
    if svc.get("env"):
        env.update(svc.get("env", {}))

    try:
        proc = subprocess.Popen(
            svc["start_cmd"],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
        )
        # Wait for service to start
        for _ in range(30):
            time.sleep(0.5)
            if check_port(svc["port"]):
                print(f"  {name} started (PID {proc.pid})")
                return True
        print(f"  {name} failed to start within 15s")
        return False
    except Exception as e:
        print(f"  {name} start error: {e}")
        return False


def stop_service(name: str) -> bool:
    label = f"com.omostation.{name}"
    try:
        subprocess.run(["launchctl", "unload", "-w",
                        str(Path.home() / "Library" / "LaunchAgents" / f"{label}.plist")],
                       capture_output=True, check=False)
    except Exception:
        pass
    # Also try to kill by port
    svc = SERVICES[name]
    try:
        subprocess.run(["lsof", "-ti", f":{svc['port']}"], capture_output=True, check=False)
    except Exception:
        pass
    return not check_port(svc["port"])


def get_status() -> list[dict]:
    return [check_service(name) for name in SERVICES]


def install_launchd():
    """Install launchd plists for all services."""
    launchd_dir = Path.home() / "Library" / "LaunchAgents"
    launchd_dir.mkdir(parents=True, exist_ok=True)

    for name, svc in SERVICES.items():
        label = f"com.omostation.{name}"
        plist_path = launchd_dir / f"{label}.plist"

        # Unload existing
        subprocess.run(["launchctl", "unload", "-w", str(plist_path)],
                       capture_output=True, check=False)

        # Determine Python executable for KOS
        program_args = []
        for arg in svc["start_cmd"]:
            if arg == sys.executable:
                program_args.append(sys.executable)
            else:
                program_args.append(str(arg) if isinstance(arg, Path) else arg)

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        {"\n        ".join(f"<string>{a}</string>" for a in program_args)}
    </array>
    <key>WorkingDirectory</key>
    <string>{ROOT}</string>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{svc['log_file']}</string>
    <key>StandardErrorPath</key>
    <string>{svc['log_file']}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
"""
        plist_path.write_text(plist_content)
        print(f"  Installed: {plist_path}")

    print(f"\n{len(SERVICES)} launchd plists installed to {launchd_dir}")
    print("Start services: launchctl load -w <plist_path>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "start", "stop", "status", "install"])
    parser.add_argument("--service", choices=list(SERVICES), help="Single service")
    args = parser.parse_args(argv)

    if args.command == "status":
        for s in get_status():
            icon = "✅" if s["running"] else "❌"
            print(f"  {icon} {s['name']:<25} port {s['port']}")
        return 0

    if args.command == "check":
        for s in get_status():
            icon = "✅" if s["running"] else "❌"
            print(f"  {icon} {s['name']:<25} port {s['port']}")
        return 0

    if args.command == "install":
        install_launchd()
        return 0

    if args.command == "start":
        target = [args.service] if args.service else list(SERVICES)
        for name in target:
            print(f"Starting {name}...")
            start_service(name)
        return 0

    if args.command == "stop":
        target = [args.service] if args.service else list(SERVICES)
        for name in target:
            print(f"Stopping {name}...")
            stop_service(name)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
