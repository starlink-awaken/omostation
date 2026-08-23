"""cockpit.commands.resident — 委派 omo resident CLI（常驻 Agent 体系, WP-A~I）。"""

from __future__ import annotations

import argparse
import subprocess

from .base import _SCRIPT_DIR


def cmd_resident(args: argparse.Namespace) -> int:
    """cockpit resident <sub> — resident 常驻 Agent 体系命令。

    委派到 omo.cli resident（SSOT 入口, 见 docs/architecture/resident-agent-system-v1.md）。
    子命令: status / roles / daemon / signals / alert / decision / execute /
            sediment / memory / promote / resources / ingest
    """
    omo_project = _SCRIPT_DIR.parent.parent.parent.parent / "omo"
    cmd = [
        "uv",
        "run",
        "--directory",
        str(omo_project.resolve()),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "omo.cli",
        "resident",
    ] + list(getattr(args, "resident_args", []))
    return subprocess.call(cmd)
