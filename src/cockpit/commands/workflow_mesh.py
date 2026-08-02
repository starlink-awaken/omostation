"""cockpit.commands.workflow_mesh — workflow-mesh 可视化入口.

workflow-mesh 是 delivery 流水线的事件织网, 事件存储在:
  .omo/_knowledge/workflow-mesh/events.jsonl

本命令读取事件文件, 让 workflow-mesh 从"暗面"变为用户可见.

子命令:
  status    — workflow-mesh 运行状态 (最近事件统计)
  delivery  — delivery pipeline 状态
  events    — 查看最近 N 条事件

设计: KISS — 直接读 jsonl 文件, 无服务依赖.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .base import _get_console, _panel

_WORKSPACE = Path(__file__).resolve().parents[5]
_EVENTS_PATH = _WORKSPACE / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
_DELIVERY_EVENTS = _WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"


def _read_events(path: Path, limit: int = 100) -> list[dict]:
    """读取 jsonl 事件文件, 返回最近 limit 条 (倒序)."""
    if not path.exists():
        return []
    events: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    for line in reversed(lines[-limit * 3 :]):  # 多读一些再截断
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(events) >= limit:
            break
    return events


def cmd_mesh_status(args: argparse.Namespace) -> int:
    """cockpit workflow mesh status — workflow-mesh 运行状态."""
    console = _get_console()
    events = _read_events(_EVENTS_PATH, limit=200)

    if not events:
        # 降级到 delivery events
        events = _read_events(_DELIVERY_EVENTS, limit=200)
        source = _DELIVERY_EVENTS
    else:
        source = _EVENTS_PATH

    if not events:
        console.print(
            _panel(
                f"[yellow]⚠️  无 workflow-mesh 事件[/yellow]\n查找路径:\n  {_EVENTS_PATH}\n  {_DELIVERY_EVENTS}",
                "yellow",
            )
        )
        return 0

    # 统计
    kind_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for e in events:
        kind = e.get("kind") or e.get("event") or e.get("type") or "unknown"
        kind_counter[kind] += 1
        status = e.get("status") or e.get("track") or ""
        if status:
            status_counter[status] += 1

    latest_ts = events[0].get("ts") or events[0].get("timestamp") or "?"

    console.print(
        _panel(
            f"[bold cyan]🕸️  Workflow Mesh 状态[/bold cyan]\n"
            f"事件源: {source.relative_to(_WORKSPACE) if source.is_relative_to(_WORKSPACE) else source}\n"
            f"最近事件: {latest_ts}\n"
            f"事件总数 (采样): {len(events)}",
            "cyan",
        )
    )

    from rich import box as rich_box
    from rich.table import Table

    if kind_counter:
        table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="事件类型分布")
        table.add_column("类型", style="bold")
        table.add_column("次数", style="green", justify="right")
        for kind, count in kind_counter.most_common(10):
            table.add_row(kind, str(count))
        console.print(table)

    if status_counter:
        table2 = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="状态/轨道分布")
        table2.add_column("状态", style="bold")
        table2.add_column("次数", style="green", justify="right")
        for status, count in status_counter.most_common(10):
            table2.add_row(status, str(count))
        console.print(table2)

    return 0


def cmd_mesh_delivery(args: argparse.Namespace) -> int:
    """cockpit workflow mesh delivery — delivery pipeline 状态."""
    console = _get_console()
    events = _read_events(_DELIVERY_EVENTS, limit=500)

    if not events:
        console.print("[yellow]⚠️  无 delivery 事件[/yellow]")
        return 0

    # 按 track 分类
    track_counter: Counter[str] = Counter()
    for e in events:
        track = e.get("track") or "unknown"
        track_counter[track] += 1

    console.print(_panel(f"[bold green]📦 Delivery Pipeline · {len(events)} 事件[/bold green]", "green"))

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold green")
    table.add_column("轨道 (track)", style="bold")
    table.add_column("事件数", style="green", justify="right")
    table.add_column("占比", style="cyan", justify="right")
    total = len(events)
    for track, count in track_counter.most_common():
        pct = f"{count / total * 100:.1f}%"
        table.add_row(track, str(count), pct)
    console.print(table)

    governance_pct = track_counter.get("governance", 0) / total * 100 if total else 0
    if governance_pct > 40:
        console.print(f"\n[yellow]⚠️  治理事件占比 {governance_pct:.1f}% (GaC 门禁阈值 40%)[/yellow]")
    else:
        console.print(f"\n[green]✅ 治理事件占比 {governance_pct:.1f}% (≤40% 达标)[/green]")

    return 0


def cmd_mesh_events(args: argparse.Namespace) -> int:
    """cockpit workflow mesh events — 查看最近事件."""
    console = _get_console()
    limit = getattr(args, "limit", 20)
    events = _read_events(_EVENTS_PATH, limit=limit)
    if not events:
        events = _read_events(_DELIVERY_EVENTS, limit=limit)

    if not events:
        console.print("[yellow]⚠️  无事件[/yellow]")
        return 0

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title=f"最近 {len(events)} 条事件")
    table.add_column("#", style="dim", width=3)
    table.add_column("时间", style="cyan", width=20)
    table.add_column("类型", style="bold")
    table.add_column("状态", style="green")
    table.add_column("详情", style="dim", no_wrap=False)

    for i, e in enumerate(events, 1):
        ts = e.get("ts") or e.get("timestamp") or "?"
        ts_short = str(ts)[:19]
        kind = e.get("kind") or e.get("event") or e.get("type") or "?"
        status = e.get("status") or e.get("track") or ""
        detail_keys = [k for k in ("task_id", "run_id", "workflow_id", "source") if k in e]
        detail = ", ".join(f"{k}={e[k]}" for k in detail_keys[:2])
        table.add_row(str(i), ts_short, str(kind)[:20], str(status)[:12], detail[:40])
    console.print(table)
    return 0


def cmd_workflow_mesh(args: argparse.Namespace) -> int:
    """cockpit workflow mesh — workflow-mesh 可视化入口."""
    sub = getattr(args, "mesh_command", None)
    if sub == "status":
        return cmd_mesh_status(args)
    if sub == "delivery":
        return cmd_mesh_delivery(args)
    if sub == "events":
        return cmd_mesh_events(args)

    console = _get_console()
    console.print(_panel("[bold cyan]🕸️  Workflow Mesh · 交付事件织网[/bold cyan]", "cyan"))
    console.print("\n[bold]可用子命令:[/]")
    console.print("  [cyan]cockpit workflow mesh status[/]    — 运行状态")
    console.print("  [cyan]cockpit workflow mesh delivery[/]  — delivery pipeline")
    console.print("  [cyan]cockpit workflow mesh events[/]    — 最近事件")
    return 0
