"""Cockpit SSB Commands — SSB 签名链操作入口 (委托给 ecos-ssb)"""

from __future__ import annotations

import subprocess
import sys


def _ecos_ssb() -> list[str]:
    """返回运行 ecos-ssb 的命令列表"""
    return [sys.executable, "-m", "ecos.l0.ssb.ssb_client"]


def cmd_ssb(args) -> int:
    """SSB 签名链操作 (发布/查询/状态/恢复)"""
    cmd = _ecos_ssb() + args.extra
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode
