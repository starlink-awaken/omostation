from __future__ import annotations

from argparse import Namespace

from rich.console import Console
from rich.panel import Panel

from .help_map import all_command_names, render_discover_map


def _cmd_discover(args: Namespace) -> int:
    """发现可用功能和资源 — 命令地图与 cockpit help 共用 help_map.GROUPS。"""
    console = Console()
    n = len(all_command_names())
    console.print(
        Panel.fit(
            f"[bold bright_cyan]🛸 cockpit 可用功能[/]\n"
            f"[dim]命令目录与 [cyan]cockpit help[/] 同源（help_map）· 共 {n} 个顶层命令[/]",
            border_style="bright_cyan",
        )
    )
    console.print("\n[bold]入口[/]")
    console.print("  [cyan]cockpit help[/]              — 产品地图（推荐）")
    console.print("  [cyan]cockpit help <关键词>[/]     — 搜 CLI / MCP / BOS")
    console.print("  [cyan]cockpit memory[/]            — Memory OS 控制面")
    console.print("  [cyan]cockpit health --full[/]     — 全栈健康检查")
    console.print("  [cyan]cockpit search --all KEY[/]  — 跨源搜索")
    console.print("  [cyan]cockpit discover[/]          — 本页面\n")
    console.print("[bold]BOS 资源域[/] [dim](agora · 例 :7431)[/]")
    console.print("  [cyan]memory/[/]     — 知识 + [bold]Memory OS[/] (bos://memory/mos/*)")
    console.print("  [cyan]governance/[/] — 治理 (omo + cockpit MCP)")
    console.print("  [cyan]analysis/[/]   — 分析 (minerva/ontoderive/codeanalyze)")
    console.print("  [cyan]persona/[/]    — 人格 (runtime)")
    console.print("  [cyan]capability/[/] — 能力 (forge/agora-proxy)\n")
    console.print("[bold]文档[/]")
    console.print("  [cyan]docs/architecture/memory-os.md[/]     — Memory OS 导航")
    console.print("  [cyan]docs/SYSTEM-INDEX.md[/]               — 系统索引")
    console.print("  [cyan]docs/operations/memory-os-neo4j-local.md[/] — 本机图库\n")

    render_discover_map(console)
    console.print(
        "\n[dim]提示: Agora MCP 可 resolve_bos_uri(bos://memory/mos/*); "
        "env: source bin/memory-os-env.sh · smoke: make memory-os-smoke[/]"
    )
    return 0
