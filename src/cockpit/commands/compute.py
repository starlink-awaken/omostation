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
    import sys
    from pathlib import Path

    try:
        # 动态定位当前 workspace root 并在 sys.path 中注入 aetherforge 路径
        cur = Path(__file__).resolve()
        workspace_root = None
        for parent in cur.parents:
            if (parent / "docs" / "project-registry.yaml").is_file():
                workspace_root = parent
                break

        if workspace_root:
            aether_src = workspace_root / "projects" / "aetherforge" / "src"
            mesh_src = workspace_root / "projects" / "aetherforge" / "packages" / "mesh" / "src"
            if aether_src.is_dir() and str(aether_src) not in sys.path:
                sys.path.insert(0, str(aether_src))
            if mesh_src.is_dir() and str(mesh_src) not in sys.path:
                sys.path.insert(0, str(mesh_src))

        import importlib.util

        return importlib.util.find_spec("aetherforge") is not None
    except Exception:
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
        console.print("  mesh wakeup <node_id>      — 网络唤醒物理从机节点 (WoL)")
        console.print("  swarm run --goal <g>       — 多 Agent 工作流")
        return 0

    import os
    from pathlib import Path

    env = os.environ.copy()

    # 动态定位并向 PYTHONPATH 注入 aetherforge 路径
    cur = Path(__file__).resolve()
    workspace_root = None
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            workspace_root = parent
            break

    if workspace_root:
        aether_src = workspace_root / "projects" / "aetherforge" / "src"
        mesh_src = workspace_root / "projects" / "aetherforge" / "packages" / "mesh" / "src"
        paths = []
        if aether_src.is_dir():
            paths.append(str(aether_src))
        if mesh_src.is_dir():
            paths.append(str(mesh_src))
        if paths:
            existing = env.get("PYTHONPATH", "")
            if existing:
                env["PYTHONPATH"] = os.pathsep.join(paths) + os.pathsep + existing
            else:
                env["PYTHONPATH"] = os.pathsep.join(paths)

    cmd = _aetherforge() + [subcmd] + args.extra
    result = subprocess.run(cmd, env=env, capture_output=False, text=True)
    return result.returncode
