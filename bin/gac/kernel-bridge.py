#!/usr/bin/env python3
"""Kernel Bridge — MetaOS ↔ OMO 连接桥.

不迁移代码，而是创建连接层：
- MetaOS 核心功能委托给 OMO
- 保持 MetaOS 独立运行能力
- 逐步切换流量

Usage:
    python3 bin/gac/kernel-bridge.py --status
    python3 bin/gac/kernel-bridge.py --delegate <function>
    python3 bin/gac/kernel-bridge.py --sync-state
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))
from repo_root import code_root  # noqa: E402

REPO = code_root()
STATE_FILE = REPO / ".omo" / "state" / "kernel-bridge.json"

DELEGATABLE_FUNCTIONS = {
    "audit_log": "审计日志写入",
    "task_lifecycle": "任务生命周期管理",
    "debt_tracking": "债务追踪",
    "gate_decision": "门控决策",
}


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"delegations": {}, "version": "1.0"}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kernel Bridge — MetaOS ↔ OMO")
    parser.add_argument("--status", action="store_true", help="Show bridge status")
    parser.add_argument("--delegate", help="Enable delegation for function")
    parser.add_argument("--sync-state", action="store_true", help="Sync state between kernels")
    args = parser.parse_args()

    if args.status:
        state = _load_state()
        print(json.dumps({
            "delegated": state.get("delegations", {}),
            "available": DELEGATABLE_FUNCTIONS,
        }, indent=2, ensure_ascii=False))
        return 0

    if args.delegate:
        if args.delegate not in DELEGATABLE_FUNCTIONS:
            print(f"Unknown function: {args.delegate}")
            return 1
        state = _load_state()
        state.setdefault("delegations", {})[args.delegate] = {
            "enabled": True,
            "delegated_at": datetime.now(UTC).isoformat(),
        }
        _save_state(state)
        print(f"✓ Delegated: {args.delegate}")
        return 0

    if args.sync_state:
        # 2026-11-13: 原实现只打印 "✓ State sync completed" 而**不读不写** ——
        # _load_state/_save_state 就在旁边却没被调用, 也没有对端可同步。**假成功
        # 会让调用方以为两侧状态已一致**。改为显式拒绝并指路。
        print("✗ --sync-state 未实现：本桥只落 .omo/state/kernel-bridge.json, 无对端可同步。")
        print("  查看状态: python3 bin/gac/kernel-bridge.py --status")
        print("  开启委托: python3 bin/gac/kernel-bridge.py --delegate <function>")
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
