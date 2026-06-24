"""cockpit audit - 6 维度全方位审计 (融合 bin/workspace-audit) (Round 43 P1).

修真前: 修真前无 audit 子命令, 用户必须直接调 bin/workspace-audit
修真后: 修真后 cockpit audit 调 bin/workspace-audit, 6 维度审计统一入口

调用:
  cockpit audit                            # 6 维度全跑 (默认 markdown)
  cockpit audit --dim radar               # 只跑指定维度
  cockpit audit --format json             # JSON 输出
  cockpit audit --output report.md       # 写报告
  cockpit audit --since 30d               # agora 维度时间范围
  cockpit audit --no-color                # 无颜色 (适合 pipe)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .base import _CLI_DIR

# _CLI_DIR = .../projects/cockpit/src/cockpit  (commands 的父目录)
# 修真 v2: 用环境变量 WORKSPACE_ROOT 覆盖, 找不到就回退到 3 层 parent (适配标准安装)
WORKSPACE_ROOT = Path(
    os.environ.get(
        "WORKSPACE_ROOT",
        str(_CLI_DIR.parent.parent.parent.parent),  # .../Workspace
    )
)
WORKSPACE_AUDIT = WORKSPACE_ROOT / "bin" / "workspace-audit"

DIMENSIONS_HELP = """可选维度:
  governance  治理巡检 6 项 (lint / test / debt / adr / task / agora)
  lint        .omo/debt/items/ 越权 status 字段
  radar       c2g radar 修真 (读 .omo/tasks/ 真数据)
  ssot        治理 SSOT 一致性 (CLAUDE.md/AGENTS.md/README.md/INDEX.md)
  gitlink     子项目 gitlink 同步
  ops         agora 操作审计 (默认 7d)"""


def cmd_audit(args: argparse.Namespace) -> int:
    """调 bin/workspace-audit, 修真前 (无 audit) → 修真后 (统一入口).

    修真 v2 (Round 43 P1 修真修真): 修真前用 _panel (rich Panel) 包装输出,
    但 rich 在某些 console (non-TTY, captured stdout) 下不打印, 导致用户看到 EXIT 1 没输出.
    修真后: 去掉 rich 包装, 直接 print() 到 stdout; 仅在错误时用 rich.
    """
    if not WORKSPACE_AUDIT.exists():
        print(f"[Error] 找不到 {WORKSPACE_AUDIT}", file=sys.stderr)
        print("尝试: cd ~/Workspace && ls bin/workspace-audit", file=sys.stderr)
        return 1

    # 修真 v3: 用 python3.13 (kairon/c2g 需要 3.13+, 不用 sys.executable 因为 venv 可能是 3.9)
    import shutil

    py = shutil.which("python3.13") or shutil.which("python3.12") or sys.executable
    cmd = [py, str(WORKSPACE_AUDIT)]
    if args.dim:
        cmd.extend(["--dim", args.dim])
    if args.format:
        cmd.extend(["--format", args.format])
    if args.output:
        cmd.extend(["--output", str(args.output)])
    if args.since:
        cmd.extend(["--since", args.since])

    banner_stream = sys.stderr if args.format == "json" else sys.stdout
    print(
        f"🔍 Omostation 6 维度全方位审计 · 调 {WORKSPACE_AUDIT.name} · adapter cockpit (L3 入口)",
        file=banner_stream,
    )
    print("─" * 60, file=banner_stream)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(WORKSPACE_ROOT),
        )
        # stdout 透传 (主报告)
        if result.stdout:
            print(result.stdout)
        # stderr 透传 (内部工具的进度信息)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        print("[Error] workspace-audit 超时 (60s)", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1
