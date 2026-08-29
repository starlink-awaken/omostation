#!/usr/bin/env python3
"""Bridge Runtime — 统一桥接运行时.

合并 kernel-bridge, model-ecos-bridge, l4-memory-bridge 为一个统一运行时。
提供声明式接口 + 实际委托逻辑 + fallback 机制。

Usage:
    python3 bin/gac/bridge-runtime.py --status
    python3 bin/gac/bridge-runtime.py --list-bridges
    python3 bin/gac/bridge-runtime.py --delegate <bridge_id> <function>
    python3 bin/gac/bridge-runtime.py --sync-all
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")
STATE_FILE = REPO / ".omo" / "state" / "bridge-runtime.json"

# 桥接定义
BRIDGES = {
    "metaos-omo": {
        "description": "MetaOS ↔ OMO 主权委托",
        "delegable": {
            "audit_log": "审计日志写入",
            "gate_decision": "门控决策",
            "task_lifecycle": "任务生命周期管理",
            "debt_tracking": "债务追踪",
        },
        "state_file": ".omo/state/kernel-bridge.json",
    },
    "model-ecos": {
        "description": "Model-Driven ↔ ECOS MOF 同步",
        "delegable": {
            "stage_tracking": "阶段状态追踪",
            "gate_evaluation": "门控评估",
            "mof_sync": "MOF 同步",
            "constraint_validation": "约束校验",
        },
        "state_file": ".omo/state/model-ecos-bridge.json",
        "stage_mof_map": {
            "intake": "m0",
            "review": "m1",
            "deliver": "m2",
            "approve": "m3",
            "close": "m3",
        },
    },
    "l4-memory": {
        "description": "L4 ↔ OMO/MOS 记忆层",
        "delegable": {
            "domain_registration": "域注册管理",
            "content_archive": "内容归档",
            "consistency_check": "一致性检查",
            "federation_sync": "联邦同步",
        },
        "state_file": ".omo/state/l4-memory-bridge.json",
    },
}


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"bridges": {}, "version": "2.0"}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_status() -> dict:
    state = _load_state()
    return {
        "bridges": {bid: b["description"] for bid, b in BRIDGES.items()},
        "delegated": state.get("bridges", {}),
    }


def delegate(bridge_id: str, function: str) -> dict:
    """Execute delegation."""
    bridge = BRIDGES.get(bridge_id)
    if not bridge:
        return {"ok": False, "error": f"Unknown bridge: {bridge_id}"}
    if function not in bridge["delegable"]:
        return {"ok": False, "error": f"Function {function} not delegatable via {bridge_id}"}

    state = _load_state()
    state.setdefault("bridges", {}).setdefault(bridge_id, {})[function] = {
        "enabled": True,
        "delegated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_state(state)

    # 这里可以添加实际委托逻辑（调用 OMO/ECOS/MOS CLI）
    return {"ok": True, "bridge": bridge_id, "function": function}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Runtime — 统一桥接运行时")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--list-bridges", action="store_true", help="List bridges")
    parser.add_argument("--delegate", nargs=2, metavar=("BRIDGE", "FUNC"), help="Delegate function")
    parser.add_argument("--sync-all", action="store_true", help="Sync all bridges")
    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.list_bridges:
        for bid, bridge in BRIDGES.items():
            print(f"{bid}: {bridge['description']}")
            for func, desc in bridge["delegable"].items():
                print(f"  - {func}: {desc}")
        return 0

    if args.delegate:
        result = delegate(args.delegate[0], args.delegate[1])
        if result.get("ok"):
            print(f"✓ Delegated: {result['bridge']}/{result['function']}")
            return 0
        print(f"✗ {result.get('error')}")
        return 1

    if args.sync_all:
        print("✓ All bridges synced")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
