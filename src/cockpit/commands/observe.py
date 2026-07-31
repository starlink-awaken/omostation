"""cockpit.commands.observe — 可观测性栈（Langfuse）入口。"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _compose_file() -> Path:
    return _workspace_root() / "projects" / "observability" / "docker-compose.yml"


def _run_compose(args: list[str]) -> int:
    cmd = ["docker", "compose", "-f", str(_compose_file().resolve())] + args
    return subprocess.call(cmd)


def cmd_observe(args: argparse.Namespace) -> int:
    """可观测性栈入口：status / up / down / logs / url。"""
    subcmd = getattr(args, "observe_command", None)

    if subcmd == "status":
        return _run_compose(["ps"])
    if subcmd == "up":
        return _run_compose(["up", "-d"])
    if subcmd == "down":
        return _run_compose(["down"])
    if subcmd == "logs":
        service = getattr(args, "service", "langfuse-server")
        return _run_compose(["logs", "-f", service])
    if subcmd == "url":
        port = os.environ.get("LANGFUSE_PORT", "3050")
        console.print(f"Langfuse Web: http://127.0.0.1:{port}")
        return 0

    console.print("[red]未知 observe 子命令[/red]")
    console.print("可用: status, up, down, logs --service <name>, url")
    return 1
