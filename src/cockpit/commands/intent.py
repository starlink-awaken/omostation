"""cockpit.commands.intent — 自然语言意图解构与工程规格编译器入口 (ADR-0195)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def cmd_intent(args: argparse.Namespace) -> int:
    console = _get_console()
    prompt = " ".join(args.prompt) if isinstance(args.prompt, list) else str(args.prompt or "")
    if not prompt:
        console.print("[red]❌ 缺少 prompt 参数: cockpit intent \"<自然语言意图>\"[/]")
        return 1

    cmd = ["ecos-constraint", "intent", "compile", prompt]
    if getattr(args, "domain", None):
        cmd.extend(["--domain", args.domain])
    if getattr(args, "json", False):
        cmd.append("--json")

    workspace_root = resolve_workspace_root()
    ecos_project = workspace_root / "projects" / "ecos"

    # 优先用 uv run projects/ecos 执行
    full_cmd = ["uv", "run", "--directory", str(ecos_project), *cmd]
    try:
        res = subprocess.run(full_cmd, cwd=str(workspace_root), capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(res.stdout, end="")
            return 0
        else:
            console.print(f"[red]❌ intent 编译失败 (rc={res.returncode}):\n{res.stderr or res.stdout}[/]")
            return res.returncode
    except Exception as e:
        console.print(f"[red]❌ 执行异常: {e}[/]")
        return 1
