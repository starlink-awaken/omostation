#!/usr/bin/env python3
"""P65 R1: cockpit readiness wrapper.

P65 原本设计为 cockpit 子命令, 但 cockpit cli.py 有 pre-existing ruff 错误
(P65 范围外), 改在根仓 bin/ 提供独立 wrapper.

设计:
- 委派到 bin/governance-dashboard.py --readiness-summary (P64/ADR-0115 合并)
- 支持 JSON / text 两种格式
- 支持 --output 写文件
- 60s timeout

使用:
  python3 bin/cockpit-readiness.py              # JSON 格式到 stdout
  python3 bin/cockpit-readiness.py --format text # 人类可读
  python3 bin/cockpit-readiness.py --output /tmp/dash.json
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_workspace_root() -> Path:
    """从当前脚本位置回溯找到 workspace 根 (含 .omo/ 目录)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # 最多向上 5 层
        if (current / ".omo").exists():
            return current
        current = current.parent
    # fallback: 假设 PWD 是 workspace
    return Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P65: cockpit readiness wrapper (委派 bin/governance-dashboard.py --readiness-summary)"
    )
    parser.add_argument(
        "--format", choices=["json", "text"], default="json",
        help="输出格式 (默认 json)",
    )
    parser.add_argument("--output", help="输出文件路径 (默认 stdout)")
    args = parser.parse_args()

    workspace_root = find_workspace_root()
    bin_tool = workspace_root / "bin" / "governance-dashboard.py"
    if not bin_tool.exists():
        print(f"❌ {bin_tool} 不存在", file=sys.stderr)
        return 1

    cmd = ["python3", str(bin_tool), "--root", str(workspace_root), "--readiness-summary", "--format", args.format]
    if args.output:
        cmd.extend(["--output", args.output])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if args.output:
            print(f"✅ 已写入 {args.output}")
        else:
            print(result.stdout, end="")
        return result.returncode
    except subprocess.TimeoutExpired:
        print("❌ 执行超时 (60s)", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ 执行失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())