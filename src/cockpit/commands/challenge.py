"""cockpit.commands.challenge — 影子红蓝对抗审查与合规自动补丁入口 (ADR-0196)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def cmd_challenge(args: argparse.Namespace) -> int:
    console = _get_console()
    target = args.target
    if not target:
        console.print("[red]❌ 缺少 target 参数: cockpit challenge <文件路径或方案文本>[/]")
        return 1

    cmd = ["ecos-constraint", "challenge", target]
    if getattr(args, "domain", None):
        cmd.extend(["--domain", args.domain])
    if getattr(args, "auto_patch", False):
        cmd.append("--auto-patch")
    if getattr(args, "strict", False):
        cmd.append("--strict")
    if getattr(args, "json", False):
        cmd.append("--json")

    workspace_root = resolve_workspace_root()
    ecos_project = workspace_root / "projects" / "ecos"

    full_cmd = ["uv", "run", "--directory", str(ecos_project), *cmd]
    try:
        res = subprocess.run(full_cmd, cwd=str(workspace_root), capture_output=True, text=True, check=False)
        if res.returncode == 0 or not getattr(args, "strict", False):
            print(res.stdout, end="")
            return res.returncode
        else:
            console.print(f"[red]❌ 影子对抗审查未通过 (rc={res.returncode}):\n{res.stderr or res.stdout}[/]")
            return res.returncode
    except Exception as e:
        console.print(f"[red]❌ 执行异常: {e}[/]")
        return 1
