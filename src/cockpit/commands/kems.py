"""cockpit.commands.kems — KEMS (Knowledge Engineering Methodology System) 治理入口.

KEMS 的执行能力归 Workspace；Documents 仅保留内容、契约与证据.
本命令通过 l4bridge 复用已有 L4 能力, 不重写逻辑.

子命令:
  domains  — 列出 L4 所有域及其状态 (28 domains)
  status   — KEMS 控制面状态
  scan     — KEMS 平面扫描

设计: DRY — 复用 cockpit.commands.l4bridge 已有的 L4 bridge 函数.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .base import _get_console, _get_err, _panel


def cmd_kems_domains(args: argparse.Namespace) -> int:
    """cockpit kems domains — 列出 L4 所有域及其状态."""
    console = _get_console()
    try:
        from cockpit.scripts.cockpit_mcp import workspace_context
    except ImportError:
        _get_err().print("[red]❌ L4 bridge 不可用 (cockpit_mcp 未安装)[/red]")
        return 1

    try:
        ctx = json.loads(workspace_context())
    except Exception as exc:
        _get_err().print(f"[red]❌ workspace_context 调用失败: {exc}[/red]")
        return 1

    domains = ctx.get("domains") or ctx.get("domain_summary") or {}
    phase = ctx.get("phase", "?")

    console.print(
        _panel(
            f"[bold cyan]🧬 KEMS 域注册 · Phase {phase}[/bold cyan]",
            "cyan",
        )
    )

    if isinstance(domains, dict):
        from rich import box as rich_box
        from rich.table import Table

        table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
        table.add_column("域", style="bold green")
        table.add_column("状态", style="cyan")
        table.add_column("详情", style="dim")
        for name, info in sorted(domains.items()):
            if isinstance(info, dict):
                status = info.get("status", "?")
                detail = info.get("detail") or info.get("cards_count", "")
            else:
                status = str(info)
                detail = ""
            table.add_row(name, str(status), str(detail))
        console.print(table)
        console.print(f"\n[dim]共 {len(domains)} 个域[/dim]")
    elif isinstance(domains, list):
        for d in domains:
            console.print(f"  [green]▪[/] {d}")
        console.print(f"\n[dim]共 {len(domains)} 个域[/dim]")
    else:
        console.print(f"[yellow]域数据格式未知: {type(domains)}[/yellow]")
        console.print(json.dumps(ctx, ensure_ascii=False, indent=2)[:500])
    return 0


def cmd_kems_status(args: argparse.Namespace) -> int:
    """cockpit kems status — KEMS 控制面状态."""
    console = _get_console()
    try:
        from cockpit.scripts.cockpit_mcp import workspace_context
    except ImportError:
        _get_err().print("[red]❌ L4 bridge 不可用[/red]")
        return 1

    try:
        ctx = json.loads(workspace_context())
    except Exception as exc:
        _get_err().print(f"[red]❌ workspace_context 调用失败: {exc}[/red]")
        return 1

    cards = ctx.get("cards_summary", {})
    console.print(
        _panel(
            f"[bold cyan]🧬 KEMS 控制面状态[/bold cyan]\n"
            f"Phase: [bold]{ctx.get('phase', '?')}[/bold] · {ctx.get('theme', '')}\n"
            f"CARDS: P0={cards.get('p0_open', 0)} open · total={cards.get('total', '?')}\n"
            f"域数: {len(ctx.get('domains') or {})}",
            "cyan",
        )
    )
    return 0


def cmd_kems_scan(args: argparse.Namespace) -> int:
    """cockpit kems scan — 审计 Documents 内容主权面。"""
    console = _get_console()
    console.print("[cyan]🔍 Documents 内容主权面扫描中...[/cyan]")

    workspace = Path(__file__).resolve().parents[5]
    documents_root = Path(os.environ.get("L4_DOCUMENTS_ROOT", Path.home() / "Documents")).expanduser()
    cmd = [
        "uv",
        "run",
        "--directory",
        str(workspace / "projects" / "l4-kernel"),
        "python",
        "-m",
        "l4_kernel.cli",
        "content",
        "audit",
        str(documents_root),
        "--json",
    ]
    result = subprocess.run(cmd, cwd=str(workspace))
    return result.returncode


def cmd_kems(args: argparse.Namespace) -> int:
    """cockpit kems — KEMS 域治理入口."""
    sub = getattr(args, "kems_command", None)
    if sub == "domains":
        return cmd_kems_domains(args)
    if sub == "status":
        return cmd_kems_status(args)
    if sub == "scan":
        return cmd_kems_scan(args)

    console = _get_console()
    console.print(_panel("[bold cyan]🧬 KEMS · Knowledge Engineering Methodology System[/bold cyan]", "cyan"))
    console.print("\n[bold]可用子命令:[/]")
    console.print("  [cyan]cockpit kems domains[/]  — 列出当前注册域状态")
    console.print("  [cyan]cockpit kems status[/]   — 控制面状态")
    console.print("  [cyan]cockpit kems scan[/]     — Documents 内容主权面扫描")
    return 0
