"""cockpit.commands.compass — L3 入口暴露 c2g 5 机制 (subprocess 复用, 不重写逻辑).

L0 约束: CLI 命名规范 kebab-case (governance-charter §1.1)
DRY: 复用 projects/c2g/ CLI, 不重复造轮子
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = (
    _SCRIPT_DIR.parent.parent.parent
)  # cockpit/src/cockpit/commands → cockpit/src/cockpit → cockpit/src → cockpit/ → projects/
_C2G_PROJECT = str((_WORKSPACE_ROOT.parent / "c2g").resolve())


def main() -> int:
    """cockpit-compass CLI 入口: 暴露 c2g 5 子命令."""
    parser = argparse.ArgumentParser(
        prog="cockpit-compass",
        description="C2G 战略罗盘 — V2P/C2G/AGC 5 机制暴露",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  brainstorm  [V2P] 触发 MetaOS 发散生成 Pitch
  draft      [V2P] 交互式向导起草 Pitch
  bet        [C2G] 将 Pitch 桥接为 Bet
  radar      [AGC] 审计系统战略一致性
  gc         [AGC]  清理衰减的 Sandbox Pitch

示例:
  cockpit-compass brainstorm "工程质量提升"
  cockpit-compass draft
  cockpit-compass bet Idea-xxx.md
  cockpit-compass radar
  cockpit-compass gc --dry-run
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # brainstorm
    p_bs = sub.add_parser("brainstorm", help="[V2P] 触发 MetaOS 生成 Pitch")
    p_bs.add_argument("topic", help="Brainstorm 主题")

    # draft
    sub.add_parser("draft", help="[V2P] 交互式向导起草 Pitch")

    # bet
    p_bet = sub.add_parser("bet", help="[C2G] 将 Pitch 转为 Bet")
    p_bet.add_argument("source_file", help="Pitch markdown 文件路径")

    # radar
    sub.add_parser("radar", help="[AGC] 战略一致性审计")

    # gc
    p_gc = sub.add_parser("gc", help="[AGC] 清理衰减的 Sandbox Pitch")
    p_gc.add_argument("--dry-run", action="store_true", help="预览 GC 不实际移动文件")

    args = parser.parse_args()

    cmd: list[str] = [
        "uv",
        "run",
        "--project",
        _C2G_PROJECT,
        "c2g",
        "--adapter",
        "ecos",
        args.command,
    ]
    # 透传额外参数 (bet source_file, gc --dry-run)
    if args.command == "bet":
        cmd.append(args.source_file)
    elif args.command == "gc" and getattr(args, "dry_run", False):
        cmd.append("--dry-run")

    # 清 VIRTUAL_ENV/PYTHONHOME 避免 uv venv 冲突 (cockpit → c2g subprocess 继承父环境)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    return subprocess.run(cmd, cwd=str(_WORKSPACE_ROOT), env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
