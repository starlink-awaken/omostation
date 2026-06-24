"""cockpit.commands.governance — governance command (delegates to arcnode-* scripts)."""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console

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


def _run_omo_verify(workspace_root: Path) -> int:
    omo_project = workspace_root / "projects" / "omo"
    verify_steps = [
        [
            "python",
            "-W",
            "ignore::DeprecationWarning",
            "-m",
            "omo.cli",
            "governance",
            "surfaces",
            "--workspace-root",
            "../..",
            "--json",
        ],
        [
            "python",
            "-W",
            "ignore::DeprecationWarning",
            "-m",
            "omo.cli",
            "lint",
            "ingress-registry",
            "--workspace-root",
            "../..",
        ],
        [
            "python",
            "-W",
            "ignore::DeprecationWarning",
            "-m",
            "omo.cli",
            "lint",
            "mutation-surfaces",
            "--workspace-root",
            "../..",
        ],
        [
            "python",
            "-W",
            "ignore::DeprecationWarning",
            "-m",
            "omo.cli",
            "lint",
            "internal-write-profiles",
            "--workspace-root",
            "../..",
        ],
        [
            "python",
            "-W",
            "ignore::DeprecationWarning",
            "-m",
            "omo.cli",
            "lint",
            "task-policy",
            "--all",
            "--workspace-root",
            "../..",
        ],
    ]
    for step in verify_steps:
        cmd = ["uv", "run", "--directory", str(omo_project), *step]
        rendered = " ".join(shlex.quote(part) for part in cmd)
        _get_console().print(f"[cyan]$ {rendered}[/]")
        result = subprocess.run(cmd, cwd=str(workspace_root))
        if result.returncode != 0:
            return result.returncode
    return 0


def cmd_governance(args: argparse.Namespace) -> int:
    import shutil

    if not args.subcommand:
        # 产品走查 v3 #18: 无参数显示治理概览(surfaces), 而非裸命令列表 — 用户敲了期待看状态
        workspace_root = resolve_workspace_root()
        _get_console().print("[cyan]📋 治理概览:[/]")
        rc = _run_omo_governance(["surfaces"], workspace_root)
        _get_console().print(
            "\n[yellow]更多子命令:[/] cockpit governance "
            "{report|verify|calibrate|drift-check|surfaces --json|rechain|...}"
        )
        return rc
    subcmd = args.subcommand
    if subcmd in _OMO_GOVERNANCE_SUBCOMMANDS:
        workspace_root = resolve_workspace_root()
        return _run_omo_governance([subcmd, *(args.extra_args or [])], workspace_root)
    if subcmd == "verify":
        workspace_root = resolve_workspace_root()
        return _run_omo_verify(workspace_root)
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
