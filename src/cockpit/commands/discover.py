from __future__ import annotations

from argparse import Namespace

from rich.console import Console

def _cmd_discover(args: Namespace) -> int:
    """发现可用功能和资源。"""
    console = Console()
    console.print("[bold cyan]🛸 cockpit 可用功能[/bold cyan]\n")
    console.print("[bold]入口[/]")
    console.print("  [cyan]cockpit[/]                — 本帮助菜单")
    console.print("  [cyan]cockpit health --full[/]   — 全栈健康检查")
    console.print("  [cyan]cockpit search --all KEY[/]— 跨源搜索")
    console.print("  [cyan]cockpit discover[/]        — 本页面\n")
    console.print("[bold]BOS 资源域 (通过 agora MCP :7431)[/]")
    console.print("  [cyan]memory/[/]     — 知识存储 (kairon: kos/kronos/sophia)")
    console.print("  [cyan]governance/[/] — 治理 (omo + cockpit MCP)")
    console.print("  [cyan]analysis/[/]   — 分析 (minerva/ontoderive/codeanalyze)")
    console.print("  [cyan]persona/[/]    — 人格 (runtime)")
    console.print("  [cyan]capability/[/] — 能力 (forge/agora-proxy)\n")
    console.print("[bold]文档[/]")
    console.print("  [cyan]docs/PANORAMA.md[/]           — 系统全景架构")
    console.print("  [cyan]docs/JOURNEY-PROBES.md[/]     — 用户旅程探针")
    console.print("  [cyan]docs/ENTRY-CONVERGENCE.md[/]  — 入口收敛方案\n")
    console.print("[dim]提示: agora MCP 连接后可直接调用 resolve_bos_uri 使用所有功能[/]")
    return 0
