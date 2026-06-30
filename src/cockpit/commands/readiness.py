"""cockpit.commands.readiness — readiness dashboard 子命令 (P65-P66 增).

P66 升级: 从 P65 wrapper 升级为 cockpit 子命令.
委派到根仓 bin/dashboard-readiness-summary.py 工具, 输出结构化 dashboard 数据.
支持 JSON / text 两种格式, 可写文件.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console


def _run_readiness_summary(args: list[str], workspace_root: Path) -> int:
    """委派到根仓 bin/dashboard-readiness-summary.py."""
    bin_tool = workspace_root / "bin" / "dashboard-readiness-summary.py"
    if not bin_tool.exists():
        console = _get_console()
        console.print(f"[red]❌ {bin_tool} 不存在[/red]")
        return 1
    cmd = ["python3", str(bin_tool), *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace_root, timeout=60)
        # 转发子进程输出 (修复 capture_output 吞输出 → readiness 空显示 bug)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return result.returncode
    except Exception as e:  # defensive fallback
        console = _get_console()
        console.print(f"[red]❌ 执行失败: {e}[/red]")
        return 1


def cmd_readiness(args: argparse.Namespace) -> int:
    """readiness dashboard 子命令."""
    workspace_root = resolve_workspace_root()
    arg_list = [str(workspace_root)]
    if args.format:
        arg_list.extend(["--format", args.format])
    if args.output:
        arg_list.extend(["--output", args.output])
    return _run_readiness_summary(arg_list, workspace_root)
