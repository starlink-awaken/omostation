#!/usr/bin/env python3
"""infinite-loop-detector — 死循环自检。

检测连续两次执行相同操作得到相同异常结果的情况。
包装命令执行，自动检测死循环。

Usage:
    python3 bin/gac/infinite-loop-detector.py -- command [args...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / ".infinite-loop-state.json"
MAX_RETRIES = 2


def get_command_hash(cmd: list[str]) -> str:
    """生成命令指纹。"""
    return hashlib.md5(" ".join(cmd).encode()).hexdigest()[:12]


def load_state() -> dict:
    """加载状态。"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    """保存状态。"""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main():
    parser = argparse.ArgumentParser(description="死循环检测包装器")
    parser.add_argument("command", nargs="+", help="要执行的命令")
    args = parser.parse_args()

    cmd = args.command
    cmd_hash = get_command_hash(cmd)
    state = load_state()

    # 检查是否连续失败
    if cmd_hash in state:
        last = state[cmd_hash]
        if last["status"] == "failed" and last["count"] >= MAX_RETRIES:
            print(f"⚠️ 死循环检测: 命令 '{' '.join(cmd)}' 已连续失败 {last['count']} 次", file=sys.stderr)
            print("建议: 停止当前操作，换策略或请求人工介入", file=sys.stderr)
            return 2

    # 执行命令
    start = time.time()
    result = subprocess.run(cmd, capture_output=True)
    elapsed = time.time() - start

    # 更新状态
    if result.returncode != 0:
        state[cmd_hash] = {
            "status": "failed",
            "count": state.get(cmd_hash, {}).get("count", 0) + 1,
            "last_error": result.stderr.decode()[:200],
            "timestamp": time.time(),
        }
    else:
        state[cmd_hash] = {
            "status": "ok",
            "count": 0,
            "timestamp": time.time(),
        }

    save_state(state)

    # 输出结果
    print(result.stdout.decode(), end="")
    print(result.stderr.decode(), end="", file=sys.stderr)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
