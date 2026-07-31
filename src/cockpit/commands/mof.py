"""Cockpit MOF Commands — MOF 元模型操作入口 (委托给 mof CLI)"""

from __future__ import annotations

import subprocess
import sys


def _mof() -> list[str]:
    """返回运行 mof 的命令列表"""
    return [sys.executable, "-m", "ecos.ssot.tools.mof"]


def cmd_mof(args) -> int:
    """MOF 元模型操作 (检查/验证/审计/强制执行)"""
    cmd = _mof() + args.extra
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode
