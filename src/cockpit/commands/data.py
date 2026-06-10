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
    try:
        result = sweep_tmp_data(
            _root_from_args(args),
            max_age_seconds=int(float(getattr(args, "max_age_hours", 24)) * 60 * 60),
        )
    except FileNotFoundError as exc:
        _get_err().print(f"[red]❌ {exc}[/red]")
        return 1
    if getattr(args, "json", False):
        _get_console().print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    _get_console().print(f"[green]✅ 已清理 {len(result['deleted_paths'])} 个临时文件[/green]")
    if result["deleted_paths"]:
        for path in result["deleted_paths"]:
            _get_console().print(f"  - {path}")
    return 0


def _root_from_args(args: argparse.Namespace) -> Path | None:
    explicit_root = getattr(args, "root", None)
    if explicit_root:
        return Path(explicit_root)
    return resolve_workspace_root()
