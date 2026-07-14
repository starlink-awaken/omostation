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


def _run_governance_evolution(args: list[str], workspace_root: Path) -> int:
    forwarded = args or ["status"]
    cmd = [
        "uv",
        "run",
        "--with",
        "pyyaml",
        "python",
        str(workspace_root / "bin" / "gac" / "governance-evolution.py"),
        *forwarded,
    ]
    return subprocess.run(cmd, cwd=str(workspace_root)).returncode


def _run_operating_rhythm(args: list[str], workspace_root: Path) -> int:
    """Run operating-rhythm commands (ADR-0119/0121, Meadows 9 范式级).

    Slots 来自 governance-evolution-roadmap.yaml::operating_rhythm:
      daily        - status 检查 (agent-workflow + governance-evolution)
      pre_release  - PR 合并前 gate (gac-local-gate + compliance)
      weekly       - MOF 桥接巡检 (mof-state-bridge)
    """
    slots: dict[str, list[list[str]]] = {
        "daily": [
            ["uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py", "status", "--json"],
            ["uv", "run", "--with", "pyyaml", "python", "bin/gac/governance-evolution.py", "status", "--json"],
        ],
        "pre_release": [
            ["make", "gac-local-gate"],
            ["uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py", "compliance", "--json"],
        ],
        "weekly": [
            ["python3", "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py", "--json"],
        ],
    }
    slot = args[0] if args else "daily"
    if slot not in slots:
        _get_console().print(f"[red]❌ 未知 rhythm slot: {slot}. 可用: {list(slots.keys())}[/]")
        return 1
    console = _get_console()
    console.print(f"[cyan]📋 operating-rhythm {slot}:[/]")
    overall_rc = 0
    for cmd in slots[slot]:
        result = subprocess.run(cmd, cwd=str(workspace_root))
        status = "[green]✅[/]" if result.returncode == 0 else "[red]❌[/]"
        console.print(f"  {status} {' '.join(cmd)} → rc={result.returncode}")
        if result.returncode != 0:
            overall_rc = result.returncode
    return overall_rc


def cmd_governance(args: argparse.Namespace) -> int:
    import shutil

    if not args.subcommand:
        # 产品走查 v3 #18: 无参数显示治理概览(surfaces), 而非裸命令列表 — 用户敲了期待看状态
        workspace_root = resolve_workspace_root()
        _get_console().print("[cyan]📋 治理概览:[/]")
        _run_omo_governance(["surfaces"], workspace_root)
        _get_console().print(
            "\n[yellow]更多子命令:[/] cockpit governance "
            "{report|verify|calibrate|drift-check|surfaces --json|rechain|rhythm <daily|pre_release|weekly>|...}"
        )
        # 概览仅用于展示状态，不因为治理发现 issues 而返回错误码；
        # 严格检查请使用 cockpit governance verify / surfaces --json。
        return 0
    subcmd = args.subcommand
    if subcmd in _OMO_GOVERNANCE_SUBCOMMANDS:
        workspace_root = resolve_workspace_root()
        return _run_omo_governance([subcmd, *(args.extra_args or [])], workspace_root)
    if subcmd == "report":
        # omo governance 默认即 audit/report 报告，不接收 "report" 子命令
        workspace_root = resolve_workspace_root()
        return _run_omo_governance([], workspace_root)
    if subcmd == "evolution":
        workspace_root = resolve_workspace_root()
        return _run_governance_evolution(args.extra_args or [], workspace_root)
    if subcmd == "verify":
        workspace_root = resolve_workspace_root()
        return _run_omo_verify(workspace_root)
    if subcmd == "rhythm":
        workspace_root = resolve_workspace_root()
        return _run_operating_rhythm(args.extra_args or [], workspace_root)
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
