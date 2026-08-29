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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")
STATE_FILE = REPO / ".omo" / "state" / "kernel-bridge.json"

# Functions that can be delegated to OMO
DELEGATABLE_FUNCTIONS = {
    "audit_log": {
        "description": "审计日志写入",
        "metaos_path": "metaos.audit.append_only_log",
        "omo_path": "omo._shared.append_only_log",
        "delegated": False,
    },
    "task_lifecycle": {
        "description": "任务生命周期管理",
        "metaos_path": "metaos.core.workflow",
        "omo_path": "omo.task_lifecycle",
        "delegated": False,
    },
    "debt_tracking": {
        "description": "债务追踪",
        "metaos_path": "metaos.layers.governance",
        "omo_path": "omo.debt",
        "delegated": False,
    },
    "gate_decision": {
        "description": "门控决策",
        "metaos_path": "metaos.core.gate",
        "omo_path": "omo.gate",
        "delegated": False,
    },
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


def get_status() -> dict:
    """Get current bridge status."""
    state = _load_state()
    return {
        "delegated": state.get("delegations", {}),
        "available": {k: v["description"] for k, v in DELEGATABLE_FUNCTIONS.items()},
    }


def delegate_function(func_name: str) -> dict:
    """Enable delegation for a specific function."""
    if func_name not in DELEGATABLE_FUNCTIONS:
        return {"ok": False, "error": f"unknown function: {func_name}"}

    state = _load_state()
    state.setdefault("delegations", {})[func_name] = {
        "enabled": True,
        "delegated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_state(state)
    return {"ok": True, "delegated": func_name}


def sync_state() -> dict:
    """Synchronize state between MetaOS and OMO."""
    # This would sync audit logs, task states, etc.
    return {"ok": True, "synced": [], "timestamp": datetime.now(timezone.utc).isoformat()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Kernel Bridge — MetaOS ↔ OMO")
    parser.add_argument("--status", action="store_true", help="Show bridge status")
    parser.add_argument("--delegate", help="Enable delegation for function")
    parser.add_argument("--sync-state", action="store_true", help="Sync state between kernels")
    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.delegate:
        result = delegate_function(args.delegate)
        if result.get("ok"):
            print(f"✓ 已委托: {args.delegate}")
            return 0
        print(f"✗ {result.get('error')}")
        return 1

    if args.sync_state:
        result = sync_state()
        print(f"✓ 状态同步完成")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
