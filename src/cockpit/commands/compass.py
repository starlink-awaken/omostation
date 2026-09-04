"""cockpit.commands.compass — L3 入口暴露 c2g 5 机制与战略罗盘全景 (BET-Y1Q4-T8-13 现代化重构).

L0 约束: CLI 命名规范 kebab-case (governance-charter §1.1)
DRY: 复用 projects/omo 注册的 vendored C2G console 与 8D 全景追溯
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from cockpit.domain.exit_codes import ExitCode

_SCRIPT_DIR = Path(__file__).resolve().parent
_COCKPIT_PROJECT = _SCRIPT_DIR.parent.parent.parent
_WORKSPACE_ROOT = _COCKPIT_PROJECT.parent.parent
_OMO_PROJECT = str((_WORKSPACE_ROOT / "projects" / "omo").resolve())

C2G_SUBCOMMANDS = [
    ("brainstorm", "[V2P] 触发 MetaOS 发散生成 Pitch 草案", "cockpit compass brainstorm '主题'"),
    ("draft", "[V2P] 交互式向导起草结构化 Pitch", "cockpit compass draft"),
    ("bet", "[C2G] 将 Pitch 桥接并落盘为治理 Bet", "cockpit compass bet Idea-xxx.md"),
    ("radar", "[AGC] 审计系统全域战略一致性雷达", "cockpit compass radar"),
    ("gc", "[AGC] 清理已衰减过期的 Sandbox Pitch", "cockpit compass gc --dry-run"),
    ("outcome", "[NEW] 追踪并度量 Pitch 最终产出效能", "cockpit compass outcome"),
    ("suggest", "[NEW] 获取 Pitch 质量提升建议", "cockpit compass suggest"),
    ("trace", "[8D] 全景元架构立体重构与链路追溯", "cockpit compass trace G27.1"),
]


def cmd_compass(args: argparse.Namespace) -> int:
    """Cockpit compass 战略罗盘统一入口 (支持 --json, --dry-run, 8D trace 与 c2g 分发)."""
    compass_args = list(getattr(args, "compass_args", []) or [])
    is_json = getattr(args, "json", False) or "--json" in compass_args
    is_dry_run = getattr(args, "dry_run", False) or "--dry-run" in compass_args
    console = Console()

    # 提取非通用 flag 的有效子命令
    filtered = [a for a in compass_args if a not in ("--json", "--dry-run", "-q", "--quiet", "-v", "--verbose")]

    # 1. 空参或帮助调用：输出 C2G 战略流水线概览
    if not filtered or filtered[0] in ("-h", "--help", "help"):
        if is_json:
            payload: dict[str, Any] = {
                "status": "ok",
                "pipeline": "Concept-to-Goal (C2G)",
                "adapter": "ecos",
                "subcommands": [c[0] for c in C2G_SUBCOMMANDS],
                "subcommand_details": [
                    {"name": name, "description": desc, "example": ex}
                    for name, desc, ex in C2G_SUBCOMMANDS
                ],
                "ready": True,
            }
            if is_dry_run:
                payload["dry_run"] = True
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return int(ExitCode.SUCCESS)

        console.print("[bold cyan]🧭 C2G 战略罗盘 (Concept-to-Goal Strategic Pipeline)[/bold cyan]")
        if is_dry_run:
            console.print("[yellow][DRY-RUN 模式][/yellow]")

        table = Table(title="战略机制一览", border_style="cyan")
        table.add_column("子命令 (Command)", style="bold cyan")
        table.add_column("机制说明 (Mechanism)", style="white")
        table.add_column("调用示例 (Example)", style="dim")

        for name, desc, ex in C2G_SUBCOMMANDS:
            table.add_row(name, desc, ex)
        console.print(table)

        console.print("\n[dim]💡 提示: 运行 [cyan]cockpit compass --json[/cyan] 可输出机器可读的战略流水线规约。[/dim]")
        return int(ExitCode.SUCCESS)

    subcmd = filtered[0]
    rest = filtered[1:]

    # 2. trace 子命令：路由到 omo.cli compass trace
    if subcmd == "trace":
        cmd = ["uv", "run", "--project", _OMO_PROJECT, "python", "-m", "omo.cli", "compass", "trace"]
        if rest:
            cmd.extend(rest)
        if is_json and "--json" not in cmd:
            cmd.append("--json")
    else:
        # 3. c2g 子命令分发
        cmd = [
            "uv",
            "run",
            "--project",
            _OMO_PROJECT,
            "c2g",
            "--adapter",
            "ecos",
            subcmd,
            *rest,
        ]
        if is_dry_run and subcmd == "gc" and "--dry-run" not in cmd:
            cmd.append("--dry-run")

    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    result = subprocess.run(cmd, cwd=str(_WORKSPACE_ROOT), env=env, check=False)
    return result.returncode


def main() -> int:
    """CLI wrapper for direct invocation."""
    parser = argparse.ArgumentParser(prog="cockpit-compass")
    parser.add_argument("compass_args", nargs=argparse.REMAINDER)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return cmd_compass(args)


if __name__ == "__main__":
    sys.exit(main())
