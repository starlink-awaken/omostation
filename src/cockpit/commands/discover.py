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
    # 产品走查 v5 #V5-05: 同步 help 全量命令地图 (之前 discover 仅列 ~10 入口,
    # 与 help 矛盾; 现补全 37 命令分 6 组, 两个发现入口一致)
    console.print("[bold]命令地图 (39 个, 分 6 组)[/]")
    console.print("  [green]入门导览[/] demo · status · daily · help · quickstart · discover · version")
    console.print("  [green]知识研究[/] research · import · vault · search · skill")
    console.print(
        "  [green]生活场景(6一等公民)[/] gongwen公文 · vault知识 · research学习 · scenario家庭 · health健康 · finance财务"
    )
    console.print("  [green]个人家庭工作[/] profile · cards · scenario · brief · context · domains · gongwen")
    console.print("  [green]健康治理[/] health · product-health · audit · governance · monitor")
    console.print("  [green]战略Agent[/] compass · iterate · workflow · mcp · bos · events · code")
    console.print("  [green]数据底层[/] data · contracts · dashboard · ssb · mof\n")
    console.print("[dim]提示: agora MCP 连接后可直接调用 resolve_bos_uri; 完整地图 → cockpit help[/]")
    return 0
