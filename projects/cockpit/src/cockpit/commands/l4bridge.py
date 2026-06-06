"""cockpit.commands.l4bridge — L4 bridge CLI commands (context, cards, vault)."""

from __future__ import annotations

import json
import sys
from argparse import Namespace

from .base import _get_console, _get_err, _panel

try:
    from cockpit.scripts.cockpit_mcp import (
        workspace_context,
        cards_status,
        cards_check,
        vault_search,
    )

    _HAS_L4 = True
except ImportError:
    _HAS_L4 = False


def cmd_context(_args: Namespace) -> int:
    """显示 workspace 完整上下文 (Phase / CARDS / 约束 / 引导)。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    try:
        ctx = json.loads(workspace_context())
    except Exception as e:
        _get_err().print(f"[red]❌ workspace_context 调用失败: {e}[/]")
        return 1

    # Phase
    console.print(
        _panel(
            f"[bold cyan]🛸 Workspace Context[/bold cyan]\n"
            f"Phase [bold]{ctx['phase']}[/bold] · {ctx['theme']}\n"
            f"状态: [bold green]{ctx.get('phase_status', '?')}[/]",
            "cyan",
        )
    )

    # P0 Cards
    cards = ctx.get("cards_summary", {})
    if cards.get("p0_open", 0) > 0:
        console.print(f"\n[bold red]⚡ P0 活跃 ({cards['p0_open']}):[/]")
        for title in cards.get("p0_titles", []):
            console.print(f"  [red]▪[/] {title}")
    else:
        console.print("\n[green]✅ 无 P0 待处理[/]")

    # Constraints
    constraints = ctx.get("constraints", [])
    console.print(f"\n[bold yellow]🔒 约束 ({len(constraints)}):[/]")
    for c in constraints[:5]:
        console.print(f"  [dim]◦[/] {c}")

    # Guidance
    guidance = ctx.get("next_guidance", "")
    if guidance:
        console.print(f"\n[bold blue]🧭 下一步:[/]")
        for line in guidance.split("."):
            if line.strip():
                console.print(f"  [blue]→[/] {line.strip()}.")

    console.print()
    return 0


def cmd_cards(args: Namespace) -> int:
    """显示 CARDS 状态。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    if getattr(args, "check", False):
        card_id = getattr(args, "card_id", "") or ""
        try:
            result = json.loads(cards_check(card_id=card_id))
        except Exception as e:
            _get_err().print(f"[red]❌ cards_check 失败: {e}[/]")
            return 1

        if result["compliant"]:
            console.print("[bold green]✅ 合规[/]")
        else:
            console.print("[bold red]❌ 违规:[/]")
            for v in result.get("violations", []):
                console.print(f"  [red]▪[/] {v}")
        console.print(f"\n[dim]已检查 {result['constraints_checked']} 项约束[/]")
        return 0

    try:
        items = json.loads(cards_status())
    except Exception as e:
        _get_err().print(f"[red]❌ cards_status 失败: {e}[/]")
        return 1

    console.print(_panel(f"[bold cyan]🃏 CARDS ({len(items)} active)[/]", "cyan"))

    for card in items:
        color = {"P0": "red", "P1": "yellow", "P2": "blue", "P3": "dim"}.get(card["priority"], "dim")
        status_color = "green" if card["status"] != "closed" else "dim"
        console.print(
            f"  [[{color}]{card['priority']}[/]] "
            f"[{status_color}]{card['title']}[/] "
            f"[dim]({card['type']} · {card['domain']})[/]"
        )

    console.print()
    return 0


def cmd_vault(args: Namespace) -> int:
    """搜索 L4 Vault。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    keyword = getattr(args, "keyword", "") or ""
    if not keyword:
        _get_err().print("[yellow]用法: workspace vault search <keyword>[/]")
        return 1

    try:
        result = json.loads(vault_search(keyword=keyword))
    except Exception as e:
        _get_err().print(f"[red]❌ vault_search 失败: {e}[/]")
        return 1

    console.print(f"[bold cyan]🔍 Vault 搜索: \"{keyword}\" ({result['total']} 结果)[/]\n")

    for r in result.get("results", []):
        console.print(f"  [bold]{r['title']}[/]")
        console.print(f"  [dim]{r['path']}[/]")
        if r.get("snippet"):
            snippet = r["snippet"].replace(keyword, f"[bold yellow]{keyword}[/]")
            console.print(f"  {snippet}\n")

    return 0
