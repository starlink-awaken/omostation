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

    if action == "install-service" or action == "install":
        return install_service(port)
    elif action == "uninstall-service" or action == "uninstall":
        return uninstall_service()
    elif action == "status":
        return status_service(port)
    elif action == "restart":
        uninstall_service()
        return install_service(port)
    else:
        from agora.daemon import run_daemon

        run_daemon(port=port)
        return 0


def install_service(port: int = 7432) -> int:
    system = platform.system()
    workspace = Path(__file__).resolve().parents[5]
    agora_venv_python = workspace / "projects" / "agora" / ".venv" / "bin" / "python"
    python_bin = str(agora_venv_python) if agora_venv_python.is_file() else sys.executable

    if system == "Darwin":
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_NAME_MACOS}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>-m</string>
        <string>agora.daemon</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{workspace}/projects/agora/src:{workspace}/projects/cockpit/src</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>{workspace}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{workspace}/runtime/agora-daemon.log</string>
    <key>StandardErrorPath</key>
    <string>{workspace}/runtime/agora-daemon.err</string>
</dict>
</plist>
"""
        PLIST_PATH.write_text(plist_content, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True)
        if res.returncode == 0:
            console.print(f"[bold green]✅ 已成功注册并启动 macOS launchd 守护服务:[/] {PLIST_PATH}")
            return 0
        else:
            console.print(f"[bold yellow]⚠️ launchctl load 返回 {res.returncode}:[/] {res.stderr.decode()}")
            return res.returncode
    elif system == "Linux":
        SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
        service_content = f"""[Unit]
Description=Agora 2.0 In-Memory Agent Bus Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory={workspace}
Environment=PYTHONPATH={workspace}/projects/agora/src:{workspace}/projects/cockpit/src
ExecStart={python_bin} -m agora.daemon
Restart=always
RestartSec=1s
StandardOutput=append:{workspace}/runtime/agora-daemon.log
StandardError=append:{workspace}/runtime/agora-daemon.err

[Install]
WantedBy=default.target
"""
        SYSTEMD_PATH.write_text(service_content, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        res = subprocess.run(
            ["systemctl", "--user", "enable", "--now", "omostation-agora.service"], capture_output=True
        )
        if res.returncode == 0:
            console.print(f"[bold green]✅ 已成功注册并启动 Linux systemd 用户服务:[/] {SYSTEMD_PATH}")
            return 0
        else:
            console.print(f"[bold yellow]⚠️ systemctl 返回 {res.returncode}:[/] {res.stderr.decode()}")
            return res.returncode
    else:
        console.print(f"[bold red]❌ 不支持的操作系统:[/] {system}")
        return 1


def uninstall_service() -> int:
    system = platform.system()
    if system == "Darwin":
        if PLIST_PATH.is_file():
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
            PLIST_PATH.unlink()
            console.print(f"[bold green]✅ 已卸载并移除 macOS launchd 服务:[/] {PLIST_PATH}")
        else:
            console.print("[dim]未找到已安装的 plist 服务[/]")
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
