#!/usr/bin/env python3
"""north_star_meter_v2.py — BCOS 北极星测量器 v2 (排除 self-data).

修复:
- 排除 shadow_runner 自我评估数据 (不计入真实消费)
- 加入 consumption_event 真实消费追踪 (需外部触发)
- 重新定义 consumed_journeys: 实际被人类使用的事件

数据源优先级:
1. .omo/state/consumption-events.json (真实人类消费) — 唯一计入
2. .omo/state/routed-signals.json (路由信号) — 仅作参考
3. .omo/state/knowledge-shadow.json (shadow runner) — 排除

consumed 定义: 外部事件 [opened, edited, submitted, referenced, approved]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSUMPTION_EVENTS = ROOT / ".omo" / "state" / "consumption-events.json"
SHADOW_STATE = ROOT / ".omo" / "state" / "knowledge-shadow.json"
ROUTED_SIGNALS = ROOT / ".omo" / "state" / "routed-signals.json"

CONSUMED_TARGET_W1 = 5
CONSUMED_TARGET_W2 = 20
COMPLETION_TARGET_W1 = 0.65
COMPLETION_TARGET_W2 = 0.85

VALID_ACTIONS = {"opened", "edited", "submitted", "referenced", "approved", "downloaded"}


def record_consumption(scene_id: str, action: str, consumer: str = "human", metadata: dict | None = None, journey_id: str | None = None) -> dict:
    """记录一次真实消费事件. 外部调用入口."""
    if action not in VALID_ACTIONS:
        return {"ok": False, "reason": f"invalid action: {action}"}
    import uuid as _uuid
    event = {
        "id": _uuid.uuid4().hex[:12],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scene_id": scene_id,
        "action": action,
        "consumer": consumer,
        "journey_id": journey_id or f"j-{int(time.time())}-{_uuid.uuid4().hex[:6]}",
        "metadata": metadata or {},
    }
    events = []
    if CONSUMPTION_EVENTS.exists():
        events = json.loads(CONSUMPTION_EVENTS.read_text())
    events.append(event)
    CONSUMPTION_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    CONSUMPTION_EVENTS.write_text(json.dumps(events, indent=2, ensure_ascii=False))
    return {"ok": True, "event": event}


def measure_consumed_journeys(hours: int = 168) -> dict:
    """consumed_journeys_per_week (修正版: 仅统计真实消费事件).

    Returns: {"total": N, "by_scene": {scene: N}, "by_action": {action: N}}
    """
    if not CONSUMPTION_EVENTS.exists():
        return {"total": 0, "by_scene": {}, "by_action": {}}
    events = json.loads(CONSUMPTION_EVENTS.read_text())
    # 时间窗口过滤 (默认 168 小时 = 7 天)
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [e for e in events if e.get("timestamp", "") >= cutoff_str]
    by_scene: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for e in recent:
        s = e.get("scene_id", "unknown")
        a = e.get("action", "unknown")
        by_scene[s] = by_scene.get(s, 0) + 1
        by_action[a] = by_action.get(a, 0) + 1
    return {"total": len(recent), "by_scene": by_scene, "by_action": by_action}


def measure_completion_rate() -> float:
    """journey_completion_rate (修正版: 用 journey_id 追踪).

    公式: approved_journeys / (approved_journeys + rejected_journeys)
    不计算 edited/opened (它们是中间状态).
    """
    if not CONSUMPTION_EVENTS.exists():
        return 0.0
    events = json.loads(CONSUMPTION_EVENTS.read_text())
    if not events:
        return 0.0
    # 收集每个 journey_id 的最终状态
    journey_state: dict[str, str] = {}
    for e in events:
        jid = e.get("journey_id", "")
        action = e.get("action", "")
        if not jid:
            continue
        # approved/rejected 是终止态, opened/edited 是中间态
        if action == "approved":
            journey_state[jid] = "approved"
        elif action in {"rejected", "needs_revision"}:
            # 已被 approved 的不会被 rejected 覆盖
            if journey_state.get(jid) != "approved":
                journey_state[jid] = "rejected"
        elif action == "opened" and jid not in journey_state:
            journey_state[jid] = "opened"
    approved_n = sum(1 for s in journey_state.values() if s == "approved")
    rejected_n = sum(1 for s in journey_state.values() if s == "rejected")
    total_closed = approved_n + rejected_n
    if total_closed == 0:
        return 0.0
    return round(approved_n / total_closed, 4)


def weekly_report() -> dict:
    """生成修正版双指标周报."""
    consumed = measure_consumed_journeys()
    completion = measure_completion_rate()
    consumed_total = consumed["total"]
    pass_w1 = consumed_total >= CONSUMED_TARGET_W1 and completion >= COMPLETION_TARGET_W1
    pass_w2 = consumed_total >= CONSUMED_TARGET_W2 and completion >= COMPLETION_TARGET_W2
    return {
        "report_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "v2 (修正版)",
        "metrics": {
            "consumed_journeys_per_week": {
                "value": consumed_total,
                "by_scene": consumed["by_scene"],
                "by_action": consumed["by_action"],
                "target_w1": CONSUMED_TARGET_W1,
                "target_w2": CONSUMED_TARGET_W2,
                "pass_w1": consumed_total >= CONSUMED_TARGET_W1,
                "pass_w2": consumed_total >= CONSUMED_TARGET_W2,
                "note": "仅统计真实消费事件, 排除 shadow_runner 自我评估",
            },
            "journey_completion_rate": {
                "value": completion,
                "target_w1": COMPLETION_TARGET_W1,
                "target_w2": COMPLETION_TARGET_W2,
                "pass_w1": completion >= COMPLETION_TARGET_W1,
                "pass_w2": completion >= COMPLETION_TARGET_W2,
            },
        },
        "overall_pass_w1": pass_w1,
        "overall_pass_w2": pass_w2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--record", action="store_true", help="记录消费事件 (需 --scene --action)")
    parser.add_argument("--scene", help="场景 ID")
    parser.add_argument("--action", help="消费动作 (opened/edited/submitted/referenced/approved)")
    parser.add_argument("--consumer", default="human")
    parser.add_argument("--journey-id", help="journey 唯一 ID (用于 completion 追踪)")
    args = parser.parse_args()
    if args.record:
        if not args.scene or not args.action:
            print("--record requires --scene and --action")
            return 1
        result = record_consumption(args.scene, args.action, args.consumer)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    report = weekly_report()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        m = report["metrics"]
        print(f"=== BCOS 北极星 (v2 修正版) ===")
        print(f"consumed_journeys_per_week: {m['consumed_journeys_per_week']['value']} (W1≥{CONSUMED_TARGET_W1}, W2≥{CONSUMED_TARGET_W2})")
        print(f"  按场景: {m['consumed_journeys_per_week']['by_scene']}")
        print(f"  按动作: {m['consumed_journeys_per_week']['by_action']}")
        print(f"journey_completion_rate: {m['journey_completion_rate']['value']:.2%} (W1≥{COMPLETION_TARGET_W1:.0%}, W2≥{COMPLETION_TARGET_W2:.0%})")
        print(f"\n{W1_result}: {'✅' if report['overall_pass_w1'] else '❌'}  W2: {'✅' if report['overall_pass_w2'] else '⏳'}")

if __name__ == "__main__":
    W1_result = "W1 验收"
    sys.exit(main())