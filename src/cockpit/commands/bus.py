"""cockpit.commands.bus — Omni-Bus 三平面入口。"""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def cmd_bus(args: argparse.Namespace) -> int:
    """Omni-Bus 入口：status / topics / publish / metrics。"""
    try:
        import bus_foundation
        import bus_foundation.facade.event as event_plane
        import bus_foundation.topics as topics
    except ImportError as exc:
        console.print(f"[red]bus_foundation 未安装: {exc}[/red]")
        return 1

    subcmd = getattr(args, "bus_command", None)
    if subcmd == "status" or not subcmd:
        _print_bus_status(bus_foundation)
        return 0
    if subcmd == "topics":
        _print_topics(topics)
        return 0
    if subcmd == "publish":
        topic = getattr(args, "topic", None)
        payload = getattr(args, "payload", None)
        if not topic:
            console.print("[red]缺少 --topic[/red]")
            return 1
        try:
            data: dict[str, Any] = json.loads(payload or "{}")
        except json.JSONDecodeError as exc:
            console.print(f"[red]payload JSON 解析失败: {exc}[/red]")
            return 1
        event_plane.publish(topic, data)
        console.print(f"[green]已发布事件到 {topic}[/green]")
        return 0
    if subcmd == "metrics":
        console.print_json(data=bus_foundation.metrics_snapshot())
        return 0
    console.print(f"[red]未知 bus 子命令: {subcmd}[/red]")
    return 1


def _print_bus_status(bus_foundation: Any) -> None:
    table = Table(title="Omni-Bus 状态", box=None)
    table.add_column("项", style="cyan")
    table.add_column("值")
    table.add_row("version", getattr(bus_foundation, "__version__", "unknown"))
    table.add_row(
        "metrics_enabled",
        str(bool(getattr(bus_foundation, "_MetricsRegistry", type("X", (), {"enabled": False}))().enabled)),
    )
    console.print(table)


def _print_topics(topics: Any) -> None:
    table = Table(title="已注册 Bus Topics", box=None)
    table.add_column("常量名", style="cyan")
    table.add_column("topic 字符串")
    for name in sorted(getattr(topics, "__all__", [])):
        value = getattr(topics, name, "")
        if isinstance(value, str):
            table.add_row(name, value)
    console.print(table)
