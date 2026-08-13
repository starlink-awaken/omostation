"""cockpit.commands.kems — KEMS (Knowledge Engineering Methodology System) 治理入口.

KEMS 的执行能力归 Workspace；Documents 仅保留内容、契约与证据.
本命令通过 l4bridge 复用已有 L4 能力, 不重写逻辑.

子命令:
  domains  — 列出 Documents 正式注册的知识域
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

from cockpit.adapters import governance_context

from .base import _get_console, _get_err, _panel


def cmd_kems_domains(args: argparse.Namespace) -> int:
    """cockpit kems domains — 列出 L4 所有域及其状态."""
    console = _get_console()
    result = governance_context.domains_list()
    if not result["available"]:
        _get_err().print(f"[red]❌ L4 域注册不可用: {result.get('error', 'unknown error')}[/red]")
        return 1

    console.print(
        _panel(
            f"[bold cyan]🧬 Documents 域注册 · {result['status']}[/bold cyan]",
            "cyan",
        )
    )
    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
    table.add_column("域", style="bold green")
    table.add_column("状态", style="cyan")
    table.add_column("BOS URI", style="dim")
    table.add_column("能力", style="dim")
    for domain in result["domains"]:
        table.add_row(
            domain["name"],
            "exists" if domain["exists"] else "missing",
            domain["bos_uri"],
            ", ".join(domain["capabilities"]),
        )
    console.print(table)
    console.print(f"\n[dim]共 {result['total']} 个域 · SSOT: {result.get('source', '?')}[/dim]")
    return 0 if result["status"] == "ok" else 1


def cmd_kems_status(args: argparse.Namespace) -> int:
    """cockpit kems status — KEMS 控制面状态."""
    console = _get_console()
    result = governance_context.kems_status()
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "ok" else 1
    audit = result["content_audit"]
    owners = result["owners"]
    console.print(
        _panel(
            f"[bold cyan]🧬 KEMS 控制面状态[/bold cyan]\n"
            f"状态: [bold]{result['status']}[/bold]\n"
            f"域注册: {result['domains']['status']} · {result['domains']['total']} domains\n"
            f"内容审计: {audit['status']} · violations={len(audit.get('violations', []))}\n"
            f"Owners: OMO={owners['omo']['status']} · Kairon={owners['kairon']['status']}",
            "cyan",
        )
    )
    if reason := audit.get("reason"):
        console.print(f"  [yellow]{reason}[/]")
    for violation in audit.get("violations", [])[:10]:
        console.print(f"  [yellow]{violation.get('code', '?')}[/] {violation.get('relative_path', '')}")
    return 0 if result["status"] == "ok" else 1


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
        "--summary",
    ]
    result = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
        data = payload["data"]
    except (json.JSONDecodeError, KeyError, TypeError):
        _get_err().print("[red]❌ L4 内容扫描未返回有效摘要[/red]")
        if result.stderr.strip():
            _get_err().print(result.stderr.strip())
        return result.returncode or 2

    counts = " · ".join(f"{kind}={count}" for kind, count in sorted(data.get("counts", {}).items()))
    console.print(
        _panel(
            f"[bold cyan]🔍 Documents 内容主权面扫描[/bold cyan]\n"
            f"状态: [bold]{'ok' if payload.get('ok') else 'violations'}[/bold]\n"
            f"分类: {counts or 'none'}\n"
            f"违规: {data.get('violation_count', 0)} · 未显示样例: {data.get('truncated_violation_count', 0)}",
            "cyan",
        )
    )
    for violation in data.get("violation_samples", []):
        console.print(f"  [yellow]{violation.get('code', '?')}[/] {violation.get('relative_path', '')}")
    if result.stderr.strip():
        _get_err().print(f"[yellow]{result.stderr.strip()}[/yellow]")
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
