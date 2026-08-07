"""cockpit.commands.bus — Omni-Bus 三平面入口。"""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def cmd_bus(args: argparse.Namespace) -> int:
    """Omni-Bus 入口：status / topics / publish / metrics / data / control。"""
    try:
        import bus_foundation
        import bus_foundation.facade.control as control_plane
        import bus_foundation.facade.data as data_plane
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
    if subcmd == "data":
        return _cmd_bus_data(data_plane, args)
    if subcmd == "control":
        return _cmd_bus_control(control_plane, args)
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
    reg = getattr(bus_foundation, "_MetricsRegistry", None)
    table.add_row(
        "metrics_enabled",
        str(bool(reg.is_enabled() if reg else False)),
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


def _cmd_bus_data(data_plane: Any, args: argparse.Namespace) -> int:
    """数据平面：emit 高吞吐 fire-and-forget 数据。"""
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
    data_plane.emit(topic, data)
    console.print(f"[green]已发出数据到 {topic} (fire-and-forget)[/green]")
    return 0


def _cmd_bus_control(control_plane: Any, args: argparse.Namespace) -> int:
    """控制平面：submit / ack / nack。"""
    action = getattr(args, "control_command", None)
    if action == "submit":
        topic = getattr(args, "topic", None)
        payload = getattr(args, "payload", None)
        if not topic:
            console.print("[red]缺少 --topic[/red]")
            return 1
        try:
            data = json.loads(payload or "{}")
        except json.JSONDecodeError as exc:
            console.print(f"[red]payload JSON 解析失败: {exc}[/red]")
            return 1
        task_id = control_plane.submit_task(topic, data)
        console.print(f"[green]任务已提交: {task_id}[/green]")
        return 0
    if action == "ack":
        task_id = getattr(args, "task_id", None)
        if not task_id:
            console.print("[red]缺少 --task-id[/red]")
            return 1
        control_plane.ack(task_id)
        console.print(f"[green]任务已 ACK: {task_id}[/green]")
        return 0
    if action == "nack":
        task_id = getattr(args, "task_id", None)
        error = getattr(args, "error", "nacked")
        if not task_id:
            console.print("[red]缺少 --task-id[/red]")
            return 1
        control_plane.nack(task_id, error)
        console.print(f"[green]任务已 NACK: {task_id} ({error})[/green]")
        return 0
    console.print("[red]未知 control 子命令[/red]")
    console.print("可用: submit --topic <t> --payload <json> | ack --task-id <id> | nack --task-id <id> --error <msg>")
    return 1


def main(argv: list[str] | None = None) -> int:
    """直接入口：python -m cockpit.commands.bus [subcommand] ..."""
    parser = argparse.ArgumentParser(prog="cockpit bus", description="Omni-Bus 三平面入口")
    sub = parser.add_subparsers(dest="bus_command")
    sub.add_parser("status", help="Bus 状态")
    sub.add_parser("topics", help="列出已注册 topic")
    sub.add_parser("metrics", help="查看 bus metrics 快照")
    publish_p = sub.add_parser("publish", help="发布事件")
    publish_p.add_argument("--topic", required=True, help="topic 名")
    publish_p.add_argument("--payload", default="{}", help="JSON payload")
    data_p = sub.add_parser("data", help="数据平面：emit 高吞吐 fire-and-forget")
    data_p.add_argument("--topic", required=True, help="topic 名")
    data_p.add_argument("--payload", default="{}", help="JSON payload")
    control_p = sub.add_parser("control", help="控制平面：submit / ack / nack")
    control_sub = control_p.add_subparsers(dest="control_command")
    submit_p = control_sub.add_parser("submit", help="提交控制任务")
    submit_p.add_argument("--topic", required=True, help="topic 名")
    submit_p.add_argument("--payload", default="{}", help="JSON payload")
    ack_p = control_sub.add_parser("ack", help="确认任务完成")
    ack_p.add_argument("--task-id", required=True, help="任务 ID")
    nack_p = control_sub.add_parser("nack", help="否定确认任务")
    nack_p.add_argument("--task-id", required=True, help="任务 ID")
    nack_p.add_argument("--error", default="nacked", help="失败原因")
    args = parser.parse_args(argv)
    return cmd_bus(args)


if __name__ == "__main__":
    import sys

    sys.exit(main())
