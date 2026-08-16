#!/usr/bin/env python3
# ruff: noqa
"""
KOS Daemon — 生产级进程管理

管理 KOS 守护进程 (索引器、监控器、watcher) 的生命周期。

Usage:
    kos daemon start      # 启动所有守护进程
    kos daemon stop       # 停止所有守护进程
    kos daemon restart    # 重启所有守护进程
    kos daemon status     # 查看守护进程状态
    kos daemon install    # 安装为系统服务 (launchd)
    kos daemon uninstall  # 卸载系统服务
"""

from __future__ import annotations

import json
import os
import signal
import subprocess as sp
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# PID 文件目录
PID_DIR = Path.home() / ".kos" / "pids"
PID_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOG_DIR = Path.home() / ".kos" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 守护进程配置
DAEMONS = {
    "indexer": {
        "description": "增量索引服务 (每5分钟扫描文件变更)",
        "command": [sys.executable, "-m", "kos.maintenance.indexer", "--daemon"],
        "interval": 300,  # 5 minutes
    },
    "watcher": {
        "description": "文件变更实时监控",
        "command": [sys.executable, "-m", "kos.maintenance.watcher", "--interval", "60"],
        "interval": 60,
    },
    "health-monitor": {
        "description": "健康监控 (每10分钟检查 + 告警)",
        "command": [sys.executable, "-m", "kos.maintenance.alerts", "--notify"],
        "interval": 600,  # 10 minutes
    },
}


class DaemonManager:
    """KOS 守护进程管理器。"""

    def __init__(self):
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保必要目录存在。"""
        PID_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def start(self, daemon_name: str | None = None) -> dict[str, Any]:
        """启动守护进程。

        Args:
            daemon_name: 指定守护进程名，None 表示全部。
        """
        results = {}
        daemons = {daemon_name: DAEMONS[daemon_name]} if daemon_name else DAEMONS

        for name, config in daemons.items():
            if self.is_running(name):
                results[name] = {"status": "already_running", "pid": self._get_pid(name)}
                continue

            try:
                # 启动进程
                log_file = LOG_DIR / f"{name}.log"
                with open(log_file, "a") as log:
                    process = sp.Popen(
                        config["command"],
                        stdout=log,
                        stderr=sp.STDOUT,
                        start_new_session=True,  # Detach from terminal
                    )

                # 写入 PID 文件
                self._set_pid(name, process.pid)

                results[name] = {
                    "status": "started",
                    "pid": process.pid,
                    "log": str(log_file),
                }
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    def stop(self, daemon_name: str | None = None) -> dict[str, Any]:
        """停止守护进程。"""
        results = {}
        daemons = {daemon_name: DAEMONS[daemon_name]} if daemon_name else DAEMONS

        for name in daemons:
            pid = self._get_pid(name)
            if not pid:
                results[name] = {"status": "not_running"}
                continue

            try:
                os.kill(pid, signal.SIGTERM)
                # 等待进程退出
                for _ in range(10):
                    if not self.is_running(name):
                        break
                    time.sleep(0.5)
                else:
                    # 强制终止
                    os.kill(pid, signal.SIGKILL)

                self._remove_pid(name)
                results[name] = {"status": "stopped", "pid": pid}
            except ProcessLookupError:
                self._remove_pid(name)
                results[name] = {"status": "stopped", "pid": pid, "note": "process already exited"}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    def restart(self, daemon_name: str | None = None) -> dict[str, Any]:
        """重启守护进程。"""
        stop_results = self.stop(daemon_name)
        time.sleep(1)
        start_results = self.start(daemon_name)
        return {"stop": stop_results, "start": start_results}

    def status(self, daemon_name: str | None = None) -> dict[str, Any]:
        """查看守护进程状态。"""
        daemons = {daemon_name: DAEMONS[daemon_name]} if daemon_name else DAEMONS
        results = {}

        for name in daemons:
            pid = self._get_pid(name)
            running = self.is_running(name) if pid else False

            results[name] = {
                "status": "running" if running else "stopped",
                "pid": pid,
                "description": DAEMONS[name]["description"],
            }

        return results

    def is_running(self, name: str) -> bool:
        """检查守护进程是否运行。"""
        pid = self._get_pid(name)
        if not pid:
            return False

        try:
            os.kill(pid, 0)  # Signal 0 = check if process exists
            return True
        except ProcessLookupError:
            self._remove_pid(name)
            return False
        except PermissionError:
            return True  # Process exists but we can't signal it

    def install(self) -> dict[str, Any]:
        """安装为 macOS launchd 服务。"""
        results = {}

        for name, config in DAEMONS.items():
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.kos.{name}.plist"

            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kos.{name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{config["command"][0]}</string>
        {"".join(f"        <string>{arg}</string>" for arg in config["command"][1:])}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_DIR}/{name}.log</string>
    <key>StandardErrorPath</key>
    <string>{LOG_DIR}/{name}.error.log</string>
    <key>ThrottleInterval</key>
    <integer>{config["interval"]}</integer>
</dict>
</plist>"""

            try:
                plist_path.write_text(plist_content)
                results[name] = {"status": "installed", "plist": str(plist_path)}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    def uninstall(self) -> dict[str, Any]:
        """卸载 launchd 服务。"""
        results = {}

        for name in DAEMONS:
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.kos.{name}.plist"

            try:
                if plist_path.exists():
                    # Unload first
                    sp.run(["launchctl", "unload", str(plist_path)], capture_output=True)
                    plist_path.unlink()
                    results[name] = {"status": "uninstalled"}
                else:
                    results[name] = {"status": "not_installed"}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    # ── PID 文件管理 ────────────────────────────────────────

    def _get_pid(self, name: str) -> int | None:
        """获取 PID。"""
        pid_file = PID_DIR / f"{name}.pid"
        if pid_file.exists():
            try:
                return int(pid_file.read_text().strip())
            except (ValueError, IOError):
                return None
        return None

    def _set_pid(self, name: str, pid: int):
        """写入 PID。"""
        pid_file = PID_DIR / f"{name}.pid"
        pid_file.write_text(str(pid))

    def _remove_pid(self, name: str):
        """删除 PID 文件。"""
        pid_file = PID_DIR / f"{name}.pid"
        if pid_file.exists():
            pid_file.unlink()


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS Daemon Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start daemons")
    sub.add_parser("stop", help="Stop daemons")
    sub.add_parser("restart", help="Restart daemons")
    sub.add_parser("status", help="Check daemon status")
    sub.add_parser("install", help="Install as system service")
    sub.add_parser("uninstall", help="Uninstall system service")

    parser.add_argument("--daemon", help="Specific daemon name")
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = DaemonManager()

    if args.command == "start":
        result = manager.start(args.daemon)
    elif args.command == "stop":
        result = manager.stop(args.daemon)
    elif args.command == "restart":
        result = manager.restart(args.daemon)
    elif args.command == "status":
        result = manager.status(args.daemon)
    elif args.command == "install":
        result = manager.install()
    elif args.command == "uninstall":
        result = manager.uninstall()
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
