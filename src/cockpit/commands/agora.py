"""cockpit.commands.agora — Agora BOS 网关入口委派。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def cmd_agora(args: argparse.Namespace) -> int:
    """通用 Agora CLI 委派包装。

    优先用项目内 agora (uv run --directory projects/agora), 仅当系统 agora
    可正常执行 (--version 通过) 才用系统二进制。此前 shutil.which 找到
    坏二进制 (ModuleNotFoundError) 导致委派静默失败。
    """
    agora_args = list(getattr(args, "agora_args", []))
    agora_project = _workspace_root() / "projects" / "agora"

    # 探测系统 agora 是否可用 (只探 --version, 失败不阻塞)
    agora_bin = shutil.which("agora")
    if agora_bin:
        probe = subprocess.run(
            [agora_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode == 0:
            return subprocess.call([agora_bin] + agora_args)

    # 回退: 项目内 agora (uv run --directory)
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
