"""Cockpit Compute Commands — 算力与 LLM 网关操作 (委托给 aetherforge CLI/MCP)

替代已 deprecated 的 aetherforge 独立 CLI, 统一经 cockpit 入口.
"""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console

console = Console()


def _aetherforge() -> list[str]:
    """返回运行 aetherforge 的命令列表."""
    return [sys.executable, "-m", "aetherforge.cli"]


def _check_aetherforge() -> bool:
    """检查 aetherforge 是否可导入."""
    try:
        import importlib.util

        return importlib.util.find_spec("aetherforge") is not None
    except ImportError:
        return False


def cmd_compute(args) -> int:
    """算力与 LLM 网关操作 (gateway generate / mesh list / mesh status / swarm run)."""
    if not _check_aetherforge():
        console.print("[red]aetherforge 未安装. 请在 projects/aetherforge 运行 uv sync[/red]")
        return 1

    subcmd = getattr(args, "compute_command", None)
    if not subcmd:
        console.print("[yellow]用法: cockpit compute <gateway|mesh|swarm> <args>[/yellow]")
        console.print("  gateway generate <prompt>  — LLM 文本生成")
        console.print("  gateway list               — 列出可用 LLM 模型")
        console.print("  mesh list                  — 列出算力节点")
        console.print("  mesh status                — 算力节点健康状态")
        console.print("  mesh cost                  — 算力成本报告")
        console.print("  swarm run --goal <g>       — 多 Agent 工作流")
        return 0

    cmd = _aetherforge() + [subcmd] + args.extra
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode
