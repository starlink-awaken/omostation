from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime

from rich.console import Console

from .base import _panel

console = Console()

def _cmd_brief(args: Namespace) -> int:
    """生成会话简报。"""
    console.print(_panel("[bold cyan]📋 会话简报[/]", "cyan"))

    try:
        from cockpit.scripts.cockpit_mcp import cards_status, workspace_context

        ctx = json.loads(workspace_context())
        cards = json.loads(cards_status())

        console.print(f"Phase {ctx['phase']} · {ctx.get('theme', '')}")
        console.print(f"活跃卡片: {ctx['cards_summary']['active']} (P0: {ctx['cards_summary']['p0_open']})")

        if cards and getattr(args, "force", False):
            console.print("\n[bold]P0 优先:[/]")
            for c in [c for c in cards if c["priority"] == "P0"]:
                console.print(f"  [red]▪[/] {c['title']}")

        console.print(f"\n[dim]生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Brief generation limited: {e}[/]")

    return 0
