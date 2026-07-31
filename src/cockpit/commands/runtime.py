"""cockpit.commands.runtime — 委派 runtime CLI（L1 运行时入口）。"""

from __future__ import annotations

import argparse
import subprocess

from .base import _SCRIPT_DIR


def cmd_runtime(args: argparse.Namespace) -> int:
    """通用 runtime CLI 委派包装。"""
    runtime_project = _SCRIPT_DIR.parent.parent.parent.parent / "runtime"
    cmd = [
        "uv",
        "run",
        "--directory",
        str(runtime_project.resolve()),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "runtime.cli",
    ] + list(getattr(args, "runtime_args", []))
    return subprocess.call(cmd)
