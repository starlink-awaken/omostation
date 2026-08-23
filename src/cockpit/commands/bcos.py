"""cockpit.commands.bcos — 委派 bin/bc-os/*.py（BCOS 业务域系统, W1~W4）。"""

from __future__ import annotations

import argparse
import subprocess

from .base import _CLI_DIR


def _bcos_script(script: str):
    """根仓 bin/bc-os/<script> 绝对路径。

    _CLI_DIR = <root>/projects/cockpit/src/cockpit
    → .parent.parent.parent.parent = <root>
    """
    return _CLI_DIR.parent.parent.parent.parent / "bin" / "bc-os" / script


def cmd_bcos(args: argparse.Namespace) -> int:
    """cockpit bcos <sub> — BCOS 业务域系统命令。

    委派到根仓 bin/bc-os/*.py（SSOT 入口, 见 docs/architecture/bcos-system-v1.md）。
    子命令: evolve / signals / north-star
    """
    rest = list(getattr(args, "bcos_args", []))
    sub = rest[0] if rest else "evolve"
    extra = rest[1:]
    script_map = {
        "evolve": "evolution_engine.py",
        "signals": "signal_router.py",
        "north-star": "north_star_meter_v2.py",
    }
    script = script_map.get(sub, "evolution_engine.py")
    cmd = ["python3", str(_bcos_script(script))] + extra
    return subprocess.call(cmd)
