"""cockpit.commands.fabric — 主权算力网络与 KV 缓存快照入口 (ADR-0197)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def cmd_fabric(args: argparse.Namespace) -> int:
    console = _get_console()
    action = args.action or "inspect"

    cmd = ["omlxc", "fabric", action]
    if action == "snapshot":
        if getattr(args, "snapshot_action", None):
            cmd.append(args.snapshot_action)
        if getattr(args, "name", None):
            cmd.extend(["--name", args.name])
        if getattr(args, "model", None):
            cmd.extend(["--model", args.model])
    elif action == "speculative-eval":
        if not getattr(args, "prompt", None):
            console.print('[red]❌ 缺少 prompt 参数: cockpit fabric speculative-eval "<prompt>"[/]')
            return 1
        cmd.append(args.prompt)
        if getattr(args, "domain", None):
            cmd.extend(["--domain", args.domain])

    workspace_root = resolve_workspace_root()
    omlxc_project = workspace_root / "projects" / "omlxc"

    full_cmd = ["uv", "run", "--directory", str(omlxc_project), *cmd]
    try:
        res = subprocess.run(full_cmd, cwd=str(workspace_root), capture_output=True, text=True, check=False)
        print(res.stdout, end="")
        if res.returncode != 0:
            console.print(f"[red]❌ fabric 操作失败:\n{res.stderr}[/]")
        return res.returncode
    except Exception as e:
        console.print(f"[red]❌ 执行异常: {e}[/]")
        return 1
