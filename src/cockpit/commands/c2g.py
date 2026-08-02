"""cockpit.commands.c2g — C2G 战略罗盘全局状态入口.

C2G (Creative-to-Governance) 双擎流已有 compass/iterate/wave2 三个命令覆盖操作层.
本命令补全局状态视图, 让用户看到 C2G pipeline 的整体健康.

子命令:
  status   — C2G 全局状态 (pitch/bet/radar 统计)
  pipeline — pipeline 可视化

设计: DRY — 复用 projects/c2g CLI 的 radar/status 子命令, 不重写逻辑.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from .base import _get_console, _get_err, _panel

_WORKSPACE = Path(__file__).resolve().parents[5]
_C2G_PROJECT = str((_WORKSPACE / "projects" / "c2g").resolve())


def _run_c2g(*args: str) -> int:
    """调用 c2g CLI."""
    cmd = ["uv", "run", "--project", _C2G_PROJECT, "c2g", "--adapter", "ecos", *args]
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    return subprocess.run(cmd, cwd=str(_WORKSPACE), env=env).returncode


def cmd_c2g_status(args: argparse.Namespace) -> int:
    """cockpit c2g status — C2G 全局状态 (调 c2g radar)."""
    console = _get_console()
    console.print(_panel("[bold magenta]🎯 C2G 战略罗盘 · 全局状态[/bold magenta]", "magenta"))
    return _run_c2g("radar")


def cmd_c2g_pipeline(args: argparse.Namespace) -> int:
    """cockpit c2g pipeline — C2G pipeline 概览."""
    console = _get_console()
    console.print(
        _panel(
            "[bold magenta]🔄 C2G 双擎 Pipeline[/bold magenta]\n\n"
            "[bold]V2P (Vision-to-Pitch)[/]\n"
            "  [cyan]cockpit compass brainstorm <主题>[/]  — MetaOS 发散\n"
            "  [cyan]cockpit compass draft[/]              — 交互式起草\n\n"
            "[bold]C2G (Creative-to-Governance)[/]\n"
            "  [cyan]cockpit compass bet <file>[/]         — Pitch → Bet\n"
            "  [cyan]cockpit iterate[/]                    — 双擎编排流\n\n"
            "[bold]AGC (Auto-Governance-Cleanup)[/]\n"
            "  [cyan]cockpit compass radar[/]              — 战略一致性审计\n"
            "  [cyan]cockpit compass gc --dry-run[/]       — 清理衰减 Sandbox\n\n"
            "[bold]Wave2 (反馈/预测)[/]\n"
            "  [cyan]cockpit wave2 dashboard[/]            — 导出看板\n"
            "  [cyan]cockpit wave2 governance[/]           — 治理反馈\n"
            "  [cyan]cockpit wave2 predictive[/]           — 预测报告",
            "magenta",
        )
    )
    return 0


def cmd_c2g(args: argparse.Namespace) -> int:
    """cockpit c2g — C2G 战略罗盘全局状态入口."""
    sub = getattr(args, "c2g_command", None)
    if sub == "status":
        return cmd_c2g_status(args)
    if sub == "pipeline":
        return cmd_c2g_pipeline(args)

    console = _get_console()
    console.print(_panel("[bold magenta]🎯 C2G · Creative-to-Governance[/bold magenta]", "magenta"))
    console.print("\n[bold]可用子命令:[/]")
    console.print("  [cyan]cockpit c2g status[/]    — 全局状态 (radar)")
    console.print("  [cyan]cockpit c2g pipeline[/]  — pipeline 概览")
    console.print("\n[bold]操作入口 (compass/iterate/wave2):[/]")
    console.print("  [cyan]cockpit compass brainstorm <主题>[/]")
    console.print("  [cyan]cockpit iterate[/]")
    return 0
