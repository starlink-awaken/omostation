"""cockpit.commands.family_hub — 家庭数字枢纽入口。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _project_root() -> Path:
    return _workspace_root() / "projects" / "family-hub"


def cmd_family_hub(args: argparse.Namespace) -> int:
    """family-hub 入口：status / api / mcp。"""
    subcmd = getattr(args, "family_hub_command", None)

    if subcmd == "status":
        console.print("[cyan]family-hub[/cyan]")
        console.print("  API server:  bun run api  (api/server.ts)")
        console.print("  MCP server:  python mcp_server.py")
        return 0
    if subcmd == "api":
        bun_bin = shutil.which("bun")
        if not bun_bin:
            console.print("[red]未找到 bun[/red]")
            return 1
        return subprocess.call(
            [bun_bin, "run", "api"],
            cwd=str(_project_root().resolve()),
        )
    if subcmd == "mcp":
        return subprocess.call(
            ["python3", str((_project_root() / "mcp_server.py").resolve())],
            cwd=str(_project_root().resolve()),
        )

    console.print("[red]未知 family-hub 子命令[/red]")
    console.print("可用: status, api, mcp")
    return 1
