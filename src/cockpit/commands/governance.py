"""cockpit.commands.governance — governance command (delegates to arcnode-* scripts)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .base import _get_console
from ..data_index import resolve_workspace_root


_OMO_GOVERNANCE_SUBCOMMANDS = {"surfaces", "ingress-goal", "ingress-task", "ingress-debt"}


def _run_omo_governance(args: list[str], workspace_root: Path) -> int:
    omo_project = workspace_root / "projects" / "omo"
    cmd = [
        "uv",
        "run",
        "--directory",
        str(omo_project),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "omo.cli",
        "governance",
        *args,
    ]
    return subprocess.run(cmd, cwd=str(workspace_root)).returncode


def cmd_governance(args: argparse.Namespace) -> int:
    import shutil

    if not args.subcommand:
        _get_console().print("[yellow]可用治理子命令:[/]")
        for cmd in [
            "calibrate",
            "rechain",
            "evolve",
            "report",
            "drift-check",
            "validate",
            "surfaces",
            "ingress-goal",
            "ingress-task",
            "ingress-debt",
        ]:
            _get_console().print(f"  workspace governance {cmd}")
        _get_console().print("\n[yellow]示例:[/]")
        _get_console().print("  workspace governance calibrate --check")
        _get_console().print("  workspace governance surfaces --json")
        _get_console().print("  workspace governance rechain")
        return 0
    subcmd = args.subcommand
    if subcmd in _OMO_GOVERNANCE_SUBCOMMANDS:
        workspace_root = resolve_workspace_root()
        return _run_omo_governance([subcmd, *(args.extra_args or [])], workspace_root)
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
