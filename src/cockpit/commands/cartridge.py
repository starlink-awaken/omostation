"""cockpit.commands.cartridge — 长尾领域治理卡带工坊管理入口 (ADR-0198)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def cmd_cartridge(args: argparse.Namespace) -> int:
    console = _get_console()
    action = args.action or "list"

    if action == "pack":
        from .cartridge_ops import pack_cartridge
        if not getattr(args, "source_dir", None) or not getattr(args, "output", None):
            console.print("[red]❌ 缺少必要参数: cockpit cartridge pack <DIR> --output <FILE>[/]")
            return 1
        return pack_cartridge(args.source_dir, args.output)
    
    if action == "run":
        from .cartridge_ops import run_cartridge
        if not getattr(args, "cartridge_file", None) or not getattr(args, "intent", None):
            console.print("[red]❌ 缺少必要参数: cockpit cartridge run <FILE> --intent <INTENT>[/]")
            return 1
        workspace_root = resolve_workspace_root()
        return run_cartridge(args.cartridge_file, args.intent, workspace_root)

    cmd = ["ecos-constraint", "cartridge", action]
    if action == "export":
        if not getattr(args, "cartridge_id", None):
            console.print("[red]❌ 缺少 cartridge_id 参数: cockpit cartridge export <ID> --output <FILE>[/]")
            return 1
        cmd.append(args.cartridge_id)
        if getattr(args, "output", None):
            cmd.extend(["--output", args.output])
    elif action == "validate":
        if not getattr(args, "file_path", None):
            console.print("[red]❌ 缺少 file_path 参数: cockpit cartridge validate <FILE>[/]")
            return 1
        cmd.append(args.file_path)

    workspace_root = resolve_workspace_root()
    ecos_project = workspace_root / "projects" / "ecos"

    full_cmd = ["uv", "run", "--directory", str(ecos_project), *cmd]
    try:
        res = subprocess.run(full_cmd, cwd=str(workspace_root), capture_output=True, text=True, check=False)
        print(res.stdout, end="")
        if res.returncode != 0:
            console.print(f"[red]❌ cartridge 操作失败:\n{res.stderr}[/]")
        return res.returncode
    except Exception as e:
        console.print(f"[red]❌ 执行异常: {e}[/]")
        return 1
