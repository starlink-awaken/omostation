from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime

from rich.console import Console

from .base import _panel

console = Console()


def _cmd_brief(args: Namespace) -> int:
    """生成会话简报 (产品走查 v5 #V5-07: 加 P0 待办 + 类型分布 + 建议, 非仅活跃卡片数)."""
    console.print(_panel("[bold cyan]📋 会话简报[/]", "cyan"))

    try:
        from cockpit.scripts.cockpit_mcp import cards_status, workspace_context

        ctx = json.loads(workspace_context())
        cards = json.loads(cards_status()) or []

        console.print(f"Phase {ctx['phase']} · {ctx.get('theme', '')}")
        cs = ctx.get("cards_summary", {}) or {}
        active = cs.get("active", 0)
        p0_open = cs.get("p0_open", 0)
        console.print(f"活跃卡片: {active} (P0: {p0_open})")

        # P0 待办 (始终显示前 5, 不再要求 --force 才看 — 管理者简报核心价值)
        p0 = [c for c in cards if c.get("priority") == "P0"][:5]
        if p0:
            console.print("\n[bold]🔴 P0 待办 (前 5):[/]")
            for c in p0:
                console.print(f"  [red]▪[/] {str(c.get('title', ''))[:50]}")

        # 按类型聚合 (产品决策支持: idea/task/debt/delivery 分布)
        by_type: dict[str, int] = {}
        for c in cards:
            t = c.get("type", "?")
            by_type[t] = by_type.get(t, 0) + 1
        if by_type:
            breakdown = " · ".join(f"{k}:{v}" for k, v in sorted(by_type.items()))
            console.print(f"\n[bold]📊 类型分布:[/] {breakdown}")

        # 建议下一步 (管理者要"该干啥", 非仅数字)
        console.print("\n[bold green]💡 建议下一步:[/]")
        if p0_open > 0:
            console.print(f"  · {p0_open} 个 P0 待办, 优先认领 (cockpit cards)")
        console.print("  · cockpit status — 看工作台当前研究")
        console.print("  · cockpit governance — 治理概览")
        console.print("  · cockpit compass radar — 战略对齐审计")

        console.print(f"\n[dim]生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/]")
    except Exception as e:  # defensive fallback  # noqa: BLE001
        console.print(f"[yellow]⚠ Brief generation limited: {e}[/]")

    return 0
