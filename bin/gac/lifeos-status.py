#!/usr/bin/env python3
"""LifeOS Status — 统一系统状态查看.

一个命令看全局: UHS 健康度 + 活跃场景 + 待处理告警 + 最近事件.

用法:
    python3 lifeos-status.py              # 文本报告
    python3 lifeos-status.py --json       # JSON 输出
    python3 lifeos-status.py --watch      # 持续监控模式 (每 30 秒刷新)
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # bin/gac/ → Workspace/


def get_uhs() -> dict:
    """获取 UHS 评分."""
    history_file = REPO / ".omo/state/history/uhs.jsonl"
    if not history_file.exists():
        return {"uhs": None, "scores": {}}
    with open(history_file) as f:
        lines = f.readlines()
        if not lines:
            return {"uhs": None, "scores": {}}
        latest = json.loads(lines[-1])
    return {
        "uhs": latest.get("uhs", "?"),
        "grade": "A" if latest.get("uhs", 0) >= 90 else "B" if latest.get("uhs", 0) >= 80 else "C",
        "scores": {k: latest.get(k, "?") for k in ["tools", "governance", "scenes", "docs", "value", "runtime"]},
    }


def get_active_scenes() -> dict:
    """获取活跃场景."""
    scene_dir = REPO / "docs/scene-cards"
    if not scene_dir.exists():
        return {"total": 0, "active": 0, "scenes": []}
    scenes = []
    for f in sorted(scene_dir.glob("*.yaml")) + sorted(scene_dir.glob("v2/*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = {}
            for part in text.split("---"):
                part = part.strip()
                if not part:
                    continue
                try:
                    data = yaml.safe_load(part)
                    if isinstance(data, dict):
                        fm.update(data)
                except Exception:
                    pass
            if fm.get("status") in ("active", "assisted", "pilot", "routine"):
                scenes.append(fm.get("scene_id", fm.get("title", f.stem)))
        except Exception:
            continue
    return {"total": len(scenes), "active": len(scenes), "scenes": scenes}


def get_pending_alerts() -> list[dict]:
    """获取待处理告警."""
    alert_file = REPO / ".omo/_delivery/ingress/alerts.jsonl"
    if not alert_file.exists():
        return []
    alerts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with open(alert_file) as f:
        for line in f:
            try:
                alert = json.loads(line.strip())
                ts = datetime.fromisoformat(alert.get("timestamp", "2020-01-01T00:00:00+00:00"))
                if ts >= cutoff:
                    alerts.append(alert)
            except Exception:
                continue
    return alerts[-10:]  # 最近 10 条


def get_recent_events() -> list[dict]:
    """获取最近事件."""
    event_file = REPO / ".omo/_knowledge/audit-log/resident-events.jsonl"
    if not event_file.exists():
        return []
    events = []
    with open(event_file) as f:
        for line in f:
            try:
                events.append(json.loads(line.strip()))
            except Exception:
                continue
    return events[-5:]  # 最近 5 条


def get_value_progress() -> dict:
    """获取价值度量进度."""
    evidence_file = REPO / ".omo/_delivery/ingress/value-evidence.jsonl"
    if not evidence_file.exists():
        return {"total": 0, "qualifying": 0, "target": 12}
    total = qualifying = 0
    with open(evidence_file) as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                total += 1
                if data.get("qualifying"):
                    qualifying += 1
            except Exception:
                continue
    return {"total": total, "qualifying": qualifying, "target": 12}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LifeOS Status")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()

    if args.watch:
        import time
        print("LifeOS Watch Mode (Ctrl+C to stop)")
        print("=" * 56)
        while True:
            print(f"\033[2J\033[H")  # 清屏
            print_report()
            time.sleep(30)
        return

    if args.json:
        print(json.dumps({
            "uhs": get_uhs(),
            "scenes": get_active_scenes(),
            "alerts": get_pending_alerts(),
            "events": get_recent_events(),
            "value": get_value_progress(),
        }, ensure_ascii=False, indent=2))
        return

    print_report()


def print_report():
    """打印文本报告."""
    uhs = get_uhs()
    scenes = get_active_scenes()
    alerts = get_pending_alerts()
    events = get_recent_events()
    value = get_value_progress()

    print("=" * 56)
    print("  LifeOS 系统状态")
    print("=" * 56)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # UHS
    uhs_score = uhs.get("uhs", "?")
    uhs_grade = uhs.get("grade", "?")
    print(f"  UHS 健康度: {uhs_score}/100 (Grade: {uhs_grade})")
    if uhs.get("scores"):
        for dim, score in uhs["scores"].items():
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            print(f"    {dim:12s}: {bar} {score}%")
    print()

    # 场景
    print(f"  活跃场景: {scenes['active']}/{scenes['total']}")
    for s in scenes.get("scenes", [])[:5]:
        print(f"    ✓ {s}")
    print()

    # 价值
    print(f"  价值度量: {value['qualifying']}/{value['target']} qualifying episodes")
    print()

    # 告警
    if alerts:
        print(f"  待处理告警 ({len(alerts)}):")
        for a in alerts[-3:]:
            print(f"    ⚠ {a.get('message', a.get('type', 'unknown'))[:50]}")
    else:
        print("  告警: 无 ✓")
    print()

    # 最近事件
    if events:
        print("  最近事件:")
        for e in events[-3:]:
            print(f"    → {e.get('event_type', '?')}: {e.get('payload', {}).get('status', '?')}")
    print()


if __name__ == "__main__":
    sys.exit(main())
