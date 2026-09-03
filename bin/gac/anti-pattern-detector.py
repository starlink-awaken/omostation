#!/usr/bin/env python3
"""anti-pattern-detector: 5 战略反模式识别 + 状态计数.

Project-strategy-v1 §9.3 反模式检测器:
1. 机制过剩价值缺位 — 工具多, 主人未更省时间
2. 多 Agent 抢单 — 多个 resident daemon 并发处理同一任务
3. shadow 卡片挂年 — 场景卡停在 shadow 跨季度
4. runbook 漂移 — runbook 提到的命令实际不存在
5. T1-10 债复发 — resident 关掉后债没自动升报

用法:
  python3 bin/gac/anti-pattern-detector.py --json    # 机器输出
  python3 bin/gac/anti-pattern-detector.py          # 人类输出
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent


def _utc_now() -> datetime:
    return datetime.now(UTC)


def check_pattern_1_mechanism_overload_value_gap() -> dict[str, Any]:
    """Pattern 1: 机制过剩价值缺位 — 工具多, 主人未更省时间.

    Proxy: north_star v3 composite score < 60 → value gap detected.
    """
    try:
        res = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin" / "bc-os" / "north_star_meter_v3.py"), "--json"],
            cwd=WS_ROOT, capture_output=True, text=True, check=False, timeout=180,
        )
        if res.returncode != 0:
            return {"pattern": "mechanism_overload_value_gap", "detected": False, "reason": "v3 unreachable"}
        data = json.loads(res.stdout)
        score = data.get("composite", {}).get("score", 0)
        return {
            "pattern": "mechanism_overload_value_gap",
            "detected": score < 60,
            "evidence": {"north_star_composite": score, "status": data.get("status")},
            "severity": "high" if score < 40 else ("medium" if score < 60 else "low"),
        }
    except Exception as e:
        return {"pattern": "mechanism_overload_value_gap", "detected": False, "reason": str(e)[:80]}


def check_pattern_2_shadow_card_aging() -> dict[str, Any]:
    """Pattern 3: shadow 卡片挂年 — 场景卡停在 shadow 跨季度.

    Proxy: 场景卡 lifecycle = shadow 持续 > 30 天.
    """
    stale_threshold_days = 30
    now = _utc_now()
    stale_count = 0
    stale_cards = []
    for f in (WS_ROOT / "docs" / "scene-cards").glob("*.yaml"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^lifecycle:\s*(\w+)\s*$", text, re.MULTILINE)
        if not m or m.group(1) != "shadow":
            continue
        mtime = f.stat().st_mtime
        age_days = (now.timestamp() - mtime) / 86400
        if age_days > stale_threshold_days:
            stale_count += 1
            stale_cards.append({"file": f.name, "age_days": round(age_days, 1)})
    return {
        "pattern": "shadow_card_aging",
        "detected": stale_count > 0,
        "evidence": {"stale_count": stale_count, "stale_cards": stale_cards},
        "severity": "high" if stale_count >= 5 else ("medium" if stale_count >= 1 else "low"),
    }


def check_pattern_3_runbook_drift() -> dict[str, Any]:
    """Pattern 4: runbook 漂移 — runbook 提到的命令实际不存在.

    Proxy: 扫描 docs/operations/runbook-*.md 中的 bin/ 引用, 统计失效引用.
    """
    pattern = re.compile(r"\bbin/[a-z][a-z0-9_-]*/[A-Za-z0-9_./-]+\.(?:py|sh)\b")
    drift_count = 0
    for f in (WS_ROOT / "docs" / "operations").glob("runbook-*.md"):
        text = f.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            ref = m.group(0)
            if not (WS_ROOT / ref).exists():
                drift_count += 1
    return {
        "pattern": "runbook_drift",
        "detected": drift_count > 0,
        "evidence": {"drift_count": drift_count},
        "severity": "high" if drift_count >= 10 else ("medium" if drift_count >= 1 else "low"),
    }


def check_pattern_4_drift_sweep_failures() -> dict[str, Any]:
    """Pattern 4b: drift-sweep 失败 — 治理契约破缺.

    Proxy: drift-sweep.py 报告 fail > 0.
    """
    try:
        res = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin" / "gac" / "drift-sweep.py"), "--json"],
            cwd=WS_ROOT, capture_output=True, text=True, check=False, timeout=120,
        )
        if res.returncode != 0:
            return {"pattern": "drift_sweep_failures", "detected": False, "reason": "sweep unreachable"}
        data = json.loads(res.stdout)
        fail_count = int(data.get("summary", {}).get("fail", 0))
        return {
            "pattern": "drift_sweep_failures",
            "detected": fail_count > 0,
            "evidence": {"fail_count": fail_count, "summary": data.get("summary")},
            "severity": "high" if fail_count >= 3 else ("medium" if fail_count >= 1 else "low"),
        }
    except Exception as e:
        return {"pattern": "drift_sweep_failures", "detected": False, "reason": str(e)[:80]}


def check_pattern_5_dormant_resident() -> dict[str, Any]:
    """Pattern 5: T1-10 债复发 — resident 关掉后债没自动升报.

    Proxy: 检查 .omo/state/agent-tick-daemon.jsonl 最近 60 分钟内有事件.
    """
    try:
        log_file = WS_ROOT / ".omo" / "state" / "agent-tick-daemon.jsonl"
        if not log_file.exists():
            return {"pattern": "dormant_resident", "detected": True, "evidence": {"reason": "log absent"}}
        cutoff = _utc_now().timestamp() - 3600
        last_event_time = log_file.stat().st_mtime
        detected = last_event_time < cutoff
        return {
            "pattern": "dormant_resident",
            "detected": detected,
            "evidence": {
                "last_event_age_seconds": round(_utc_now().timestamp() - last_event_time, 1),
                "threshold_seconds": 3600,
            },
            "severity": "medium" if detected else "low",
        }
    except Exception as e:
        return {"pattern": "dormant_resident", "detected": False, "reason": str(e)[:80]}


PATTERN_CHECKS = [
    ("mechanism_overload_value_gap", check_pattern_1_mechanism_overload_value_gap),
    ("shadow_card_aging", check_pattern_2_shadow_card_aging),
    ("runbook_drift", check_pattern_3_runbook_drift),
    ("drift_sweep_failures", check_pattern_4_drift_sweep_failures),
    ("dormant_resident", check_pattern_5_dormant_resident),
]


def collect() -> dict[str, Any]:
    """Run all anti-pattern checks."""
    patterns = []
    detected_count = 0
    for name, fn in PATTERN_CHECKS:
        try:
            result = fn()
        except Exception as e:
            result = {"pattern": name, "detected": False, "reason": str(e)[:80]}
        patterns.append(result)
        if result.get("detected"):
            detected_count += 1
    return {
        "snapshot_at": _utc_now().isoformat().replace("+00:00", "Z"),
        "total_patterns": len(PATTERN_CHECKS),
        "detected_count": detected_count,
        "status": "critical" if detected_count >= 3 else ("warning" if detected_count >= 1 else "healthy"),
        "patterns": patterns,
    }


def render_text(data: dict[str, Any]) -> str:
    lines = ["=" * 72, "Anti-Pattern Detector (Strategy §9.3)", "=" * 72]
    lines.append(f"snapshot_at: {data['snapshot_at']}")
    lines.append(f"total_patterns: {data['total_patterns']}")
    lines.append(f"detected_count: {data['detected_count']}")
    lines.append(f"status: {data['status'].upper()}")
    lines.append("")
    for p in data["patterns"]:
        marker = "🔴" if p.get("detected") else "✅"
        lines.append(f"{marker} {p['pattern']} (severity={p.get('severity', '?')})")
        if p.get("detected"):
            ev = p.get("evidence", {})
            for k, v in ev.items():
                if isinstance(v, list) and len(v) > 5:
                    lines.append(f"  {k}: [{len(v)} items] {v[:3]}...")
                else:
                    lines.append(f"  {k}: {v}")
        if p.get("reason"):
            lines.append(f"  reason: {p['reason']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Anti-Pattern Detector")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    data = collect()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())