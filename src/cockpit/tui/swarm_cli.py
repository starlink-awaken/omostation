"""
cockpit.tui.swarm_cli — Multi-Agent Observability CLI 快照模式 (bin/omo-status)

提供 <0.2s 极速单次 Rich Panel 终端输出与 --json 机器可读导出。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cockpit.tui.swarm_collector import SwarmGlobalState, SwarmStateCollector


def render_swarm_status_panel(state: SwarmGlobalState, console: Console | None = None) -> None:
    """渲染 4 象限 Rich Panel 综合大盘。"""
    c = console or Console()

    # 1. 顶部 Header Banner
    health_icon = (
        "● [bold green]HEALTHY[/bold green]"
        if state.agents.healthy_count > 0
        else "○ [bold yellow]DEGRADED[/bold yellow]"
    )
    header_content = Text.from_markup(
        f"  {health_icon}  [dim]·[/dim]  [bold white]OMOSTATION MULTI-AGENT SWARM[/bold white]  "
        f"[dim]·[/dim]  [cyan]{state.agents.healthy_count}/{state.agents.total_agents} Agents Active[/cyan]  "
        f"[dim]·[/dim]  [magenta]D2/D3 Locks: {state.locks.active_runs} active / {state.locks.stale_locks} stale[/magenta]\n"
        f"  [bold]BET Progress:[/bold] [green]{state.bets.done_count}/{state.bets.total_bets} ({state.bets.overall_percent}%)[/green]  "
        f"[dim]·[/dim]  [bold]Submodules:[/bold] [cyan]{state.submodules.aligned_count}/{state.submodules.total_submodules} Aligned[/cyan]  "
        f"[dim]·[/dim]  [dim]{state.timestamp_iso}[/dim]"
    )
    header_panel = Panel(
        header_content,
        title="🛰️  [bold cyan]SWARM OBSERVABILITY CONTROL PLANE[/bold cyan]",
        title_align="left",
        border_style="cyan",
        box=box.ROUNDED,
    )
    c.print(header_panel)

    # 2. 象限 1: Agent Swarm 表格
    agent_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold")
    agent_table.add_column("AGENT", style="bold white", width=18)
    agent_table.add_column("STATE", width=10)
    agent_table.add_column("ACTION", style="dim", width=10)
    agent_table.add_column("SEEN", justify="right")

    for a in state.agents.agents:
        st_markup = "[green]● active[/green]" if a.status == "healthy" else "[yellow]◌ stale[/yellow]"
        seen_str = f"{int(a.seconds_ago)}s ago" if a.seconds_ago >= 0 else "N/A"
        agent_table.add_row(a.name, st_markup, a.action, f"[dim]{seen_str}[/]")

    p_agents = Panel(
        agent_table,
        title=f"🤖  [bold]Agent Swarm ({state.agents.total_agents})[/bold]",
        title_align="left",
        border_style="blue",
        box=box.ROUNDED,
    )

    # 3. 象限 2: BET Ledger 进度条
    bet_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold")
    bet_table.add_column("TRACK", style="bold cyan", width=12)
    bet_table.add_column("PROGRESS BAR", width=18)
    bet_table.add_column("DONE", justify="right", width=8)

    for tr in state.bets.tracks[:6]:  # 展示前 6 条主要轨道
        bar_len = 10
        filled = int(tr.percent / 100.0 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        color = "green" if tr.percent >= 70 else "yellow"
        bet_table.add_row(
            tr.track,
            f"[{color}]{bar}[/] [dim]{tr.percent}%[/]",
            f"{tr.done}/{tr.total}",
        )

    p_bets = Panel(
        bet_table,
        title=f"📈  [bold]BET Ledger ({state.bets.overall_percent}% Done)[/bold]",
        title_align="left",
        border_style="green",
        box=box.ROUNDED,
    )

    # 4. 象限 3: Submodules Radar (展示前 6 个或漂移项)
    sub_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold")
    sub_table.add_column("MODULE", style="bold white", width=14)
    sub_table.add_column("SHA", style="cyan", width=9)
    sub_table.add_column("STATUS", justify="right", width=10)

    # 优先展示 drift 的，再展示正常的
    sorted_subs = sorted(
        state.submodules.items,
        key=lambda s: (0 if s.drift_status == "drifted" else 1, s.name),
    )
    for sub in sorted_subs[:6]:
        st = "[green]● aligned[/green]" if sub.drift_status == "aligned" else "[bold red]✖ drifted[/bold red]"
        sub_table.add_row(sub.name, sub.current_sha, st)

    p_subs = Panel(
        sub_table,
        title=f"🧭  [bold]Submodules Radar ({state.submodules.total_submodules})[/bold]",
        title_align="left",
        border_style="yellow",
        box=box.ROUNDED,
    )

    # 5. 象限 4: Recent A2A Messages (最近 5 条)
    msg_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold")
    msg_table.add_column("ROUTE", style="bold magenta", width=16)
    msg_table.add_column("EVENT / ACTION", style="dim", no_wrap=True)

    for m in state.recent_messages[:6]:
        route = f"{m.from_agent}→{m.to_agent}"
        msg_table.add_row(route, m.summary)

    p_msgs = Panel(
        msg_table,
        title=f"💬  [bold]Recent A2A Events ({len(state.recent_messages)})[/bold]",
        title_align="left",
        border_style="magenta",
        box=box.ROUNDED,
    )

    # 6. 双列网格输出
    col1 = Columns([p_agents, p_bets], equal=True, expand=True)
    col2 = Columns([p_subs, p_msgs], equal=True, expand=True)
    c.print(col1)
    c.print(col2)


def main() -> None:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(description="omostation Multi-Agent Swarm Observability Snapshot")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    parser.add_argument(
        "--probe-remote",
        action="store_true",
        help="Probe remote submodule repositories (may take 1-2s)",
    )
    args = parser.parse_args()

    collector = SwarmStateCollector()
    state = collector.collect_all(probe_remote_submodules=args.probe_remote)

    if args.json:
        print(json.dumps(asdict(state), indent=2, ensure_ascii=False))
        sys.exit(0)

    render_swarm_status_panel(state)


if __name__ == "__main__":
    main()
