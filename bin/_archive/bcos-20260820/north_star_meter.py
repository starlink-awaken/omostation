#!/usr/bin/env python3
"""north_star_meter.py — BCOS 北极星测量器 (W1-D7).

双指标:
  - consumed_journeys_per_week (主)
  - journey_completion_rate (辅)

数据源:
  - .omo/state/knowledge-shadow.json (知识闭环累积)
  - .omo/state/routed-signals.json (信号路由累积)
  - .omo/state/agent-beliefs/index.yaml (capability_calibrations)

输出: weekly_report (YAML/JSON)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHADOW_STATE = ROOT / ".omo" / "state" / "knowledge-shadow.json"
ROUTED_SIGNALS = ROOT / ".omo" / "state" / "routed-signals.json"
BELIEFS_STATE = ROOT / ".omo" / "state" / "agent-beliefs" / "index.yaml"

# 北极星目标
CONSUMED_TARGET_W1 = 5
CONSUMED_TARGET_W2 = 20
COMPLETION_TARGET_W1 = 0.65
COMPLETION_TARGET_W2 = 0.85


def measure_consumed_journeys(hours: int = 168) -> dict:
    """consumed_journeys_per_week.

    Definition: scenes whose output has been referenced/edited/submitted by human.
    Proxy: scenes with accepted knowledge samples + routed signals + valid calibrations.
    """
    by_scene: dict[str, int] = {}
    # 来源 1: shadow runner 接受的样本
    if SHADOW_STATE.exists():
        state = json.loads(SHADOW_STATE.read_text())
        for s in state.get("samples", []):
            scene = s.get("source_scene", "unknown")
            by_scene[scene] = by_scene.get(scene, 0) + 1
    # 来源 2: 路由信号 (signal_router)
    if ROUTED_SIGNALS.exists():
        routed = json.loads(ROUTED_SIGNALS.read_text())
        for r in routed:
            scene = r.get("source_scene", "unknown")
            by_scene[scene] = by_scene.get(scene, 0) + 1
    total = sum(by_scene.values())
    return {"total": total, "by_scene": by_scene}


def measure_completion_rate() -> float:
    """journey_completion_rate.

    Definition: succeeded / started.
    Proxy: accepted / total knowledge samples (as a sample-based proxy).
    """
    if not SHADOW_STATE.exists():
        return 0.0
    state = json.loads(SHADOW_STATE.read_text())
    total = state.get("total", 0)
    accepted = len(state.get("samples", []))
    if total == 0:
        return 0.0
    return round(accepted / total, 4)


def measure_calibration() -> float:
    """平均 calibration 评分."""
    if not SHADOW_STATE.exists():
        return 0.0
    state = json.loads(SHADOW_STATE.read_text())
    samples = state.get("samples", [])
    if not samples:
        return 0.0
    accepted = [s for s in samples if s.get("quality_score", 0) >= 0.6]
    return round(len(accepted) / len(samples), 4)


def weekly_report() -> dict:
    """生成双指标周报."""
    consumed = measure_consumed_journeys()
    completion = measure_completion_rate()
    calibration = measure_calibration()
    consumed_total = consumed["total"]
    # 达标判定
    pass_w1 = consumed_total >= CONSUMED_TARGET_W1 and completion >= COMPLETION_TARGET_W1
    pass_w2 = consumed_total >= CONSUMED_TARGET_W2 and completion >= COMPLETION_TARGET_W2
    return {
        "report_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": {
            "consumed_journeys_per_week": {
                "value": consumed_total,
                "by_scene": consumed["by_scene"],
                "target_w1": CONSUMED_TARGET_W1,
                "target_w2": CONSUMED_TARGET_W2,
                "pass_w1": consumed_total >= CONSUMED_TARGET_W1,
                "pass_w2": consumed_total >= CONSUMED_TARGET_W2,
            },
            "journey_completion_rate": {
                "value": completion,
                "target_w1": COMPLETION_TARGET_W1,
                "target_w2": COMPLETION_TARGET_W2,
                "pass_w1": completion >= COMPLETION_TARGET_W1,
                "pass_w2": completion >= COMPLETION_TARGET_W2,
            },
            "calibration_score": calibration,
        },
        "overall_pass_w1": pass_w1,
        "overall_pass_w2": pass_w2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = weekly_report()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        m = report["metrics"]
        print(f"=== BCOS 北极星 W1 验收 ===")
        print(f"consumed_journeys_per_week: {m['consumed_journeys_per_week']['value']} (目标 W1≥{CONSUMED_TARGET_W1}, W2≥{CONSUMED_TARGET_W2})")
        print(f"journey_completion_rate: {m['journey_completion_rate']['value']:.2%} (目标 W1≥{COMPLETION_TARGET_W1:.0%}, W2≥{COMPLETION_TARGET_W2:.0%})")
        print(f"calibration_score: {m['calibration_score']:.2%}")
        print(f"按场景: {m['consumed_journeys_per_week']['by_scene']}")
        print()
        print(f"W1 验收: {'✅ 通过' if report['overall_pass_w1'] else '❌ 未达'}  W2 验收: {'✅ 通过' if report['overall_pass_w2'] else '⏳ 进行中'}")


if __name__ == "__main__":
    sys.exit(main())