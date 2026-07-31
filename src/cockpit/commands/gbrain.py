"""cockpit.commands.gbrain — Postgres-native 知识库入口委派。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def cmd_gbrain(args: argparse.Namespace) -> int:
    """gbrain CLI 委派包装（Bun/TypeScript）。"""
    gbrain_args = list(getattr(args, "gbrain_args", []))
    gbrain_bin = shutil.which("gbrain")
    if gbrain_bin:
        return subprocess.call([gbrain_bin] + gbrain_args)
    gbrain_project = _workspace_root() / "projects" / "gbrain"
    bun_bin = shutil.which("bun")
    if bun_bin:
        return subprocess.call(
            [bun_bin, "run", "src/cli.ts"] + gbrain_args,
            cwd=str(gbrain_project.resolve()),
        )
    return subprocess.call(
        ["npx", "tsx", "src/cli.ts"] + gbrain_args,
        cwd=str(gbrain_project.resolve()),
    )
