"""Cockpit swarm-activity — 多 agent 实时活动监控 (封装 swarm-activity-dashboard)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    # commands/ → cockpit/ → src/ → cockpit package root → projects/cockpit → projects → workspace
    return Path(__file__).resolve().parents[5]


def cmd_swarm(args: Any) -> int:
    """Run swarm-activity-dashboard (active runs/locks/worktree/claims/子模块 dirty/冲突)."""
    root = _workspace_root()
    script = root / "bin" / "gac" / "swarm-activity-dashboard.py"
    if not script.is_file():
        print(f"❌ missing dashboard script: {script}")
        return 1

    cmd = [sys.executable, str(script)]
    if getattr(args, "tui", False):
        cmd.append("--tui")
        cmd.extend(["--refresh", str(getattr(args, "refresh", 5))])
    elif getattr(args, "json", False):
        cmd.append("--json")
    elif getattr(args, "watch", 0):
        cmd.append("--watch")
        cmd.append(str(args.watch))

    r = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0 and r.stderr:
        print(r.stderr.rstrip(), file=sys.stderr)
    return r.returncode
