"""cockpit.commands.governance — governance command (delegates to arcnode-* scripts)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .base import _get_console


def cmd_governance(args: argparse.Namespace) -> int:
    import shutil

    if not args.subcommand:
        _get_console().print("[yellow]可用治理子命令:[/]")
        for cmd in ["calibrate", "rechain", "evolve", "report", "drift-check", "validate"]:
            _get_console().print(f"  workspace governance {cmd}")
        _get_console().print("\n[yellow]示例:[/]")
        _get_console().print("  workspace governance calibrate --check")
        _get_console().print("  workspace governance rechain")
        return 0
    subcmd = args.subcommand
    script_name = f"arcnode-{subcmd}"
    script = shutil.which(script_name)
    if not script:
        script = str(Path.home() / ".hermes" / "scripts" / script_name)
    if not Path(script).exists():
        _get_console().print(f"[red]❌ 未知治理命令: {subcmd}[/]")
        return 1
    extra = args.extra_args or []
    result = subprocess.run([script] + extra)
    return result.returncode
