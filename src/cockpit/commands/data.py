from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich import box
from rich.table import Table

from ..data_index import build_data_index, load_type_registry, resolve_workspace_root, sweep_tmp_data
from .base import _get_console, _get_err


def cmd_data_index(args: argparse.Namespace) -> int:
    try:
        result = build_data_index(_root_from_args(args))
    except FileNotFoundError as exc:
        _get_err().print(f"[red]❌ {exc}[/red]")
        return 1
    if getattr(args, "json", False):
        _get_console().print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    table = Table(title="Workspace Data Index", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("目录", style="cyan")
    for directory in result["directories"]:
        table.add_row(directory)
    _get_console().print(table)
    _get_console().print(f"[green]✅ 已刷新类型注册表 ({len(result['types'])} types)[/green]")
    return 0


def cmd_data_types(args: argparse.Namespace) -> int:
    try:
        types = load_type_registry(_root_from_args(args))
    except FileNotFoundError as exc:
        _get_err().print(f"[red]❌ {exc}[/red]")
        return 1
    if getattr(args, "json", False):
        _get_console().print(json.dumps({"types": types}, ensure_ascii=False, indent=2))
        return 0
    table = Table(title="Workspace Data Types", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Retention", style="magenta")
    for item in types:
        table.add_row(str(item.get("id", "")), str(item.get("label", "")), str(item.get("retention_class", "")))
    _get_console().print(table)
    return 0


def cmd_data_gc(args: argparse.Namespace) -> int:
    is_dry_run = getattr(args, "dry_run", False)
    try:
        if is_dry_run:
            result = {"dry_run": True, "deleted_paths": [], "ready": True}
        else:
            result = sweep_tmp_data(
                _root_from_args(args),
                max_age_seconds=int(float(getattr(args, "max_age_hours", 24)) * 60 * 60),
            )
    except FileNotFoundError as exc:
        _get_err().print(f"[red]❌ {exc}[/red]")
        return 1
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if is_dry_run:
        _get_console().print("[bold cyan]🔍 [Dry-Run] 预检临时文件清理 (未实际删除)[/]")
        return 0
    _get_console().print(f"[green]✅ 已清理 {len(result['deleted_paths'])} 个临时文件[/green]")
    if result["deleted_paths"]:
        for path in result["deleted_paths"]:
            _get_console().print(f"  - {path}")
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    """统一数据平面入口 — 自动聚合摘要 / 子命令路由。"""
    from cockpit.domain.exit_codes import ExitCode

    sub = getattr(args, "data_command", "")
    import sys
    cli_mod = sys.modules.get("cockpit.cli")
    cli_target = getattr(cli_mod, f"cmd_data_{sub}", None) if cli_mod else None
    if cli_target is not None and cli_target not in (cmd_data_index, cmd_data_types, cmd_data_gc):
        return cli_target(args)
    if sub == "index":
        return cmd_data_index(args)
    if sub == "types":
        return cmd_data_types(args)
    if sub == "gc":
        return cmd_data_gc(args)

    as_json = getattr(args, "json", False) or getattr(args, "global_output", "text") == "json"
    root = _root_from_args(args)

    try:
        types = load_type_registry(root)
    except Exception:
        types = []

    data_dir = root / "data" if root else Path("data")
    tmp_dir = data_dir / "tmp"
    tmp_count = len(list(tmp_dir.glob("*"))) if tmp_dir.is_dir() else 0

    payload = {
        "status": "ok",
        "data_dir": str(data_dir),
        "registered_types_count": len(types),
        "tmp_files_count": tmp_count,
        "available_commands": ["index", "types", "gc"],
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return ExitCode.SUCCESS

    c = _get_console()
    c.print("[bold cyan]📦 Workspace 数据目录概览 (Data Plane)[/]")
    c.print(f"  • 数据目录: [dim]{data_dir}[/]")
    c.print(f"  • 已注册数据类型: [green]{len(types)}[/] 种 (查看详情: [cyan]cockpit data types[/])")
    c.print(f"  • 待清理临时文件: [yellow]{tmp_count}[/] 个 (清理命令: [cyan]cockpit data gc[/])")
    c.print("\n[dim]提示: 常用子命令: index(刷新索引) · types(查看类型) · gc(清理临时文件)[/dim]")
    return ExitCode.SUCCESS


def _root_from_args(args: argparse.Namespace) -> Path | None:
    explicit_root = getattr(args, "root", None)
    if explicit_root:
        return Path(explicit_root)
    return resolve_workspace_root()

