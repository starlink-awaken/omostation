"""cockpit.commands.harness — Harness 统一入口 (P4 + Phase 8 合并).

合并 P4 的 8-stage DAG 可观测 (trace/verify/probe/gac/retro/run) 与 Phase 8 的
12 章节合规 (compliance/mof/omo/enforce/full/status)，单一入口收敛。

  cockpit harness trace --last --json  → bin/harness trace
  cockpit harness verify --parallel    → bin/harness verify
  cockpit harness probe --emit         → bin/harness probe
  cockpit harness gac validate --gate  → bin/harness gac validate
  cockpit harness compliance --report  → bin/gac/harness-compliance-check.py

SSOT: .omo/_truth/registry/harness-policy.yaml
ADR: ADR-0444 (P4), Phase 8
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from rich.console import Console

from ..data_index import resolve_workspace_root
from .base import _get_console

console = Console()

# P4 透传到 bin/harness 的子命令集合
P4_PROXY_CMDS = {"trace", "verify", "probe", "gac", "retro", "run", "explain", "ledger", "grill", "audit", "closeout"}


def _run_harness_script(script: str, args: list[str], workspace_root: Path) -> int:
    cmd = [str(workspace_root / script)] + args
    c = _get_console()
    c.print(f"[dim]$ {' '.join(cmd)}[/]")
    return subprocess.run(cmd, cwd=str(workspace_root)).returncode


def _run_bin_harness(args: list[str], workspace_root: Path) -> int:
    harness = workspace_root / "bin" / "harness"
    return subprocess.run(["python3", str(harness)] + args, cwd=str(workspace_root)).returncode


def cmd_harness(a: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root()
    subcommand = getattr(a, "subcommand", None)
    # 兼容 P4 的 harness_args REMAINDER 透传
    harness_args = getattr(a, "harness_args", None)
    extra_args = getattr(a, "extra_args", []) or []

    # 空参展示合并帮助
    if not subcommand and not harness_args:
        c = _get_console()
        c.print("[bold cyan]cockpit harness[/] — Harness 统一入口 (P4 可观测 + Phase 8 合规)")
        c.print("  [cyan]可观测 (P4):[/] trace / verify / probe / gac / retro / run / explain")
        c.print("    cockpit harness trace --last          # 最近 run 回放")
        c.print("    cockpit harness verify --parallel     # 并行验证")
        c.print("    cockpit harness probe --emit          # 7探针→Event Bus")
        c.print("    cockpit harness gac --list            # bin/gac 单入口")
        c.print("  [cyan]合规 (Phase 8):[/] compliance / mof / omo / enforce / full / status")
        c.print("    cockpit harness compliance --report   # 12 章节检查")
        c.print("    cockpit harness mof                   # MOF 联动")
        c.print("    cockpit harness status                # 合规总览")
        return 0

    # P4 代理路径：若 subcommand 属于 P4 集合，或 harness_args 非空，则透传 bin/harness
    # 兼容两种调用：`cockpit harness trace --last` (subcommand=trace) 与 `cockpit harness -- trace --last` (harness_args)
    if harness_args:
        # P4 透传模式：harness_args 包含完整透传参数
        return _run_bin_harness(list(harness_args), workspace_root)
    if subcommand in P4_PROXY_CMDS:
        # 将 subcommand + extra_args 透传
        return _run_bin_harness([subcommand] + list(extra_args), workspace_root)

    # Phase 8 合规路径
    if subcommand == "compliance":
        return _run_harness_script("bin/gac/harness-compliance-check.py", ["--report"] + extra_args, workspace_root)
    elif subcommand == "mof":
        return _run_harness_script("bin/gac/harness-mof-bridge.py", extra_args, workspace_root)
    elif subcommand == "omo":
        return _run_harness_script("bin/gac/harness-omo-bridge.py", extra_args, workspace_root)
    elif subcommand == "enforce":
        return _run_harness_script("bin/gac/harness-constraint-enforcer.py", ["--ci"] + extra_args, workspace_root)
    elif subcommand == "full":
        return _run_harness_script("bin/gac/harness-constraint-enforcer.py", ["--ci"] + extra_args, workspace_root)
    elif subcommand == "status":
        return _run_harness_script("bin/gac/harness-compliance-check.py", extra_args, workspace_root)
    else:
        c = _get_console()
        c.print("[red]未知子命令。可用: trace/verify/probe/gac/retro/run/explain + compliance/mof/omo/enforce/full/status[/]")
        return 1


def register_harness_subcommand(sub: argparse._SubParsersAction) -> None:
    harness_p = sub.add_parser(
        "harness",
        help="Harness 统一入口 (P4 可观测 + Phase 8 合规)",
    )
    # 合并两套子命令：P4 的 trace/verify 等 + Phase 8 的 compliance 等，统一为可选 subcommand + 透传
    harness_p.add_argument(
        "subcommand",
        nargs="?",
        choices=["trace", "verify", "probe", "gac", "retro", "run", "explain", "ledger", "grill", "audit", "closeout",
                 "compliance", "mof", "omo", "enforce", "full", "status"],
        help="Harness 子命令 (P4 可观测或 Phase 8 合规)",
    )
    harness_p.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="透传参数",
    )
    # 兼容 P4 的 harness_args 透传（保留但隐藏，实际由 extra_args 承载）
    harness_p.add_argument(
        "harness_args",
        nargs=argparse.REMAINDER,
        help=argparse.SUPPRESS,
    )
    harness_p.set_defaults(func=cmd_harness)
