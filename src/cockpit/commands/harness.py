"""cockpit.commands.harness — Harness 全生命周期合规命令 (Phase 8).

暴露 Harness 合规检查能力到 cockpit CLI:
  cockpit harness compliance  → 12 章节完整性检查
  cockpit harness mof         → MOF 约束联动
  cockpit harness omo         → OMO 状态同步
  cockpit harness enforce     → 统一约束与驱动
  cockpit harness full        → 全量检查
  cockpit harness status      → 合规状态总览
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def _run_harness_script(script: str, args: list[str], workspace_root: Path) -> int:
    """Run a harness script from bin/gac/."""
    cmd = [str(workspace_root / script)] + args
    console = _get_console()
    console.print(f"[dim]$ {' '.join(cmd)}[/]")
    return subprocess.run(cmd, cwd=str(workspace_root)).returncode


def cmd_harness(a: argparse.Namespace) -> int:
    """Harness 全生命周期合规命令入口."""
    workspace_root = resolve_workspace_root()
    subcommand = getattr(a, "subcommand", None)

    if subcommand == "compliance":
        return _run_harness_script(
            "bin/gac/harness-compliance-check.py", ["--report"], workspace_root
        )
    elif subcommand == "mof":
        return _run_harness_script(
            "bin/gac/harness-mof-bridge.py", [], workspace_root
        )
    elif subcommand == "omo":
        return _run_harness_script(
            "bin/gac/harness-omo-bridge.py", [], workspace_root
        )
    elif subcommand == "enforce":
        return _run_harness_script(
            "bin/gac/harness-constraint-enforcer.py", ["--ci"], workspace_root
        )
    elif subcommand == "full":
        return _run_harness_script(
            "bin/gac/harness-constraint-enforcer.py", ["--ci"], workspace_root
        )
    elif subcommand == "status":
        return _run_harness_script(
            "bin/gac/harness-compliance-check.py", [], workspace_root
        )
    else:
        console = _get_console()
        console.print("[red]未知子命令。可用: compliance / mof / omo / enforce / full / status[/]")
        return 1


def register_harness_subcommand(sub: argparse._SubParsersAction) -> None:
    """Register the harness subcommand parser."""
    harness_p = sub.add_parser(
        "harness",
        help="Harness 全生命周期合规 (12 章节 + MOF + OMO + 约束驱动)",
    )
    harness_p.add_argument(
        "subcommand",
        nargs="?",
        choices=["compliance", "mof", "omo", "enforce", "full", "status"],
        help="Harness 合规子命令",
    )
    harness_p.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="传递给底层脚本的额外参数",
    )
    harness_p.set_defaults(func=cmd_harness)
