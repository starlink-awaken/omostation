"""cockpit.commands.agora — Agora BOS 网关入口委派。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def cmd_agora(args: argparse.Namespace) -> int:
    """通用 Agora CLI 委派包装。"""
    agora_args = list(getattr(args, "agora_args", []))
    agora_bin = shutil.which("agora")
    if agora_bin:
        return subprocess.call([agora_bin] + agora_args)
    agora_project = _workspace_root() / "projects" / "agora"
    cmd = [
        "uv",
        "run",
        "--directory",
        str(agora_project.resolve()),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "agora.cli",
    ] + agora_args
    return subprocess.call(cmd)
