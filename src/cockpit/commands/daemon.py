"""Agora 2.0 Daemon management commands (Service Install/Uninstall/Status/Run)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

from rich.console import Console

console = Console()

SERVICE_NAME_MACOS = "com.omostation.agora.daemon"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_NAME_MACOS}.plist"
SYSTEMD_PATH = Path.home() / ".config" / "systemd" / "user" / "omostation-agora.service"


def cmd_daemon_dispatch(args) -> int:
    action = getattr(args, "daemon_action", None) or "run"
    port = getattr(args, "port", 7432)

    if action in ("install-service", "install"):
        return install_service(port)
    elif action in ("uninstall-service", "uninstall"):
        return uninstall_service()
    elif action == "status":
        return status_service(port)
    elif action == "restart":
        uninstall_service()
        return install_service(port)
    elif action == "run":
        from agora.daemon import run_daemon

        run_daemon(port=port)
        return 0
    else:
        console.print(f"[red]未知 daemon 动作: {action}[/]")
        return 1


def install_service(port: int = 7432) -> int:
    system = platform.system()
    if system == "Darwin":
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        py_exe = sys.executable
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_NAME_MACOS}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exe}</string>
        <string>-m</string>
        <string>agora.daemon</string>
        <string>--port</string>
        <string>{port}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home() / ".omo" / "state" / "agora-daemon.log"}</string>
    <key>StandardErrorPath</key>
    <string>{Path.home() / ".omo" / "state" / "agora-daemon.err"}</string>
</dict>
</plist>
"""
        PLIST_PATH.write_text(plist_content, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True)
        if res.returncode == 0:
            console.print(f"[bold green]✅ 已成功注册并启动 macOS launchd 守护服务:[/] {SERVICE_NAME_MACOS}")
            console.print(f"  - 配置文件: {PLIST_PATH}")
            return 0
        else:
            console.print(f"[red]❌ 启动 launchd 服务失败: {res.stderr.decode()}[/]")
            return 1

    elif system == "Linux":
        SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
        py_exe = sys.executable
        service_content = f"""[Unit]
Description=OMOStation Agora 2.0 In-Memory Bus Daemon
After=network.target

[Service]
Type=simple
ExecStart={py_exe} -m agora.daemon --port {port}
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
"""
        SYSTEMD_PATH.write_text(service_content, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        res = subprocess.run(
            ["systemctl", "--user", "enable", "--now", "omostation-agora.service"], capture_output=True
        )
        if res.returncode == 0:
            console.print("[bold green]✅ 已成功注册并启动 Linux systemd 用户服务:[/] omostation-agora.service")
            console.print(f"  - 配置文件: {SYSTEMD_PATH}")
            return 0
        else:
            console.print(f"[red]❌ 启动 systemd 服务失败: {res.stderr.decode()}[/]")
            return 1
    else:
        console.print(
            f"[yellow]⚠️ 当前操作系统 ({system}) 暂不支持自动注册系统服务，请使用 `cockpit daemon run` 前台运行。[/]"
        )
        return 0


def uninstall_service() -> int:
    system = platform.system()
    if system == "Darwin":
        if PLIST_PATH.is_file():
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
            PLIST_PATH.unlink()
            console.print(f"[bold green]✅ 已卸载并移除 macOS launchd 服务:[/] {SERVICE_NAME_MACOS}")
        else:
            console.print("[dim]未找到已安装的 launchd 服务[/]")
        return 0
    elif system == "Linux":
        if SYSTEMD_PATH.is_file():
            subprocess.run(["systemctl", "--user", "stop", "omostation-agora.service"], capture_output=True)
            subprocess.run(["systemctl", "--user", "disable", "omostation-agora.service"], capture_output=True)
            SYSTEMD_PATH.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            console.print(f"[bold green]✅ 已卸载并移除 Linux systemd 服务:[/] {SYSTEMD_PATH}")
        else:
            console.print("[dim]未找到已安装的 systemd 服务[/]")
        return 0
    return 0


def status_service(port: int = 7432) -> int:
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cockpit-probe"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
            console.print(f"[bold green]🟢 Agora 2.0 守护总线运行中[/] (端口 :{port})")
            console.print(f"  - 状态: [cyan]{data.get('status')}[/]")
            console.print(f"  - 活跃 Agent 连接数: [cyan]{data.get('active_agents', 0)}[/]")
            console.print(f"  - 已订阅主题数: [cyan]{len(data.get('subscribed_topics', []))}[/]")
            return 0
    except Exception as e:
        console.print(f"[bold red]🔴 Agora 2.0 守护总线未响应[/] (端口 :{port}): {e}")
        return 1
