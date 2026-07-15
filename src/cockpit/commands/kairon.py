"""cockpit.commands.kairon — kairon 知识引擎 monorepo 聚合入口。"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


# package 别名 -> (project 子目录, script 名)
_KAIRON_PACKAGES = {
    "kos": ("packages/kos", "kos"),
    "eidos": ("packages/eidos", "eidos"),
    "iris": ("packages/iris", "iris"),
    "code": ("packages/codeanalyze", "codeanalyze"),
    "codeanalyze": ("packages/codeanalyze", "codeanalyze"),
    "ontoderive": ("packages/ontoderive", "ontoderive"),
    "minerva": ("packages/minerva", "minerva"),
    "sophia": ("packages/sophia", "sophia"),
}


def cmd_kairon(args: argparse.Namespace) -> int:
    """kairon monorepo 聚合入口：cockpit kairon <package> <args>..."""
    kairon_args = list(getattr(args, "kairon_args", []))
    if not kairon_args:
        print("用法: cockpit kairon <package> <args>...")
        print("支持的 package: kos, eidos, iris, code, ontoderive, minerva, sophia")
        return 1

    package = kairon_args[0]
    extra = kairon_args[1:]
    mapping = _KAIRON_PACKAGES.get(package)
    if mapping is None:
        print(f"[red]未知 kairon package: {package}[/red]")
        print("支持的 package: kos, eidos, iris, code, ontoderive, minerva, sophia")
        return 1

    rel_path, script = mapping
    project_path = _workspace_root() / "projects" / "kairon" / rel_path
    cmd = ["uv", "run", "--project", str(project_path.resolve()), script] + extra
    return subprocess.call(cmd)
