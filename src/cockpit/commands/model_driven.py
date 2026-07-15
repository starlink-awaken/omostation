"""cockpit.commands.model_driven — 模型驱动生命周期入口委派。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def cmd_model_driven(args: argparse.Namespace) -> int:
    """model-driven CLI 委派包装。"""
    md_args = list(getattr(args, "model_driven_args", []))
    md_bin = shutil.which("model-driven")
    if md_bin:
        return subprocess.call([md_bin] + md_args)
    md_project = _workspace_root() / "projects" / "model-driven"
    cmd = [
        "uv",
        "run",
        "--project",
        str(md_project.resolve()),
        "model-driven",
    ] + md_args
    return subprocess.call(cmd)
