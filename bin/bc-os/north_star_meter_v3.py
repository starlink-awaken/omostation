#!/usr/bin/env python3
"""north_star_meter_v3: 复合制价值证明 (project-strategy-v1 §5.2 落地).

3 轴复合 (D4 混合数据源策略):
  A 时间账本 (主, 70%): 系统自动化事件数 × 估时/事件 → 月可证时间节省
  B 决策吞吐 (30%): 决策收件箱条目数 + cadence (0/低/中/高)
  C 项目推进力 (佐证, 0%): BET done rate (无成本导出)

输出: provable / partial / unprovable + 三轴各自得分.

用法:
  python3 bin/bc-os/north_star_meter_v3.py --json
  python3 bin/bc-os/north_star_meter_v3.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent
HEALTH_HISTORY = WS_ROOT / ".omo" / "state" / "history" / "health.jsonl"
DECISIONS_LOG = WS_ROOT / ".omo" / "notepads" / "delegation-guardrails" / "decisions.md"
AUDIT_TICK = WS_ROOT / ".omo" / "state" / "autoloop-trace.jsonl"
DUCK_LOG = WS_ROOT / ".omo" / "state" / "agent-tick-daemon.jsonl"
CELL_STATE_FILE = WS_ROOT / ".omo" / "state" / "agent-cell" / "cell_states.json"

# A-axis: 系统自动化事件估时 (分钟/事件) — 这些值是经验估值, 后续可校准
TIME_PER_EVENT_MIN = {
    "compass_radar_run": 5,        # 一次健康巡检手动跑 ~5min
    "drift_sweep_run": 8,          # 漂移扫描 ~8min
    "signal_poll": 1,             # 信号轮询 ~1min
    "agent_tick": 2,              # 一次 agent 后台 tick ~2min
    "maturity_scorecard_run": 4,   # 成熟度扫描 ~4min
    "document_review_sample": 12,  # 一份公文 review ~12min
    "knowledge_curation": 3,       # 知识策展一次 ~3min
    "staleness_check": 2,          # staleness 检查 ~2min
    "cell_episode": 3,             # AGE-v2 Cell 一次 Episode 执行 ~3min
}


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _read_jsonl_events(path: Path, since_days: int = 30) -> int:
    """Count events in a JSONL file with ts/ts_iso within since_days."""
    if not path.is_file():
        return 0
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    count = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = rec.get("ts") or rec.get("ts_iso") or rec.get("timestamp") or ""
            if not ts_str:
                count += 1  # no ts: count it anyway
                continue
            try:
                ts = dt.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.UTC)
                if ts >= cutoff:
                    count += 1
            except (ValueError, TypeError):
                count += 1
    except OSError:
        pass
    return count


def _count_health_runs(since_days: int = 30) -> int:
    """compass_radar run count from health.jsonl history."""
    if not HEALTH_HISTORY.is_file():
        return 0
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    count = 0
    try:
        for line in HEALTH_HISTORY.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                ts_str = rec.get("ts") or ""
                if not ts_str:
                    continue
                ts = dt.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.UTC)
                if ts >= cutoff:
                    count += 1
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    except OSError:
        pass
    return count


def _count_cell_episodes(since_days: int = 30) -> int:
    """Count AGE-v2 Cell episodes from state file."""
    if not CELL_STATE_FILE.is_file():
        return 0
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    count = 0
    try:
        data = json.loads(CELL_STATE_FILE.read_text(encoding="utf-8"))
        for state in data.values():
            saved = state.get("saved_at", "")
            if saved:
                try:
                    ts = dt.datetime.fromisoformat(str(saved).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=dt.UTC)
                    if ts >= cutoff:
                        count += 1
                except (ValueError, TypeError):
                    pass
    except (OSError, json.JSONDecodeError):
        pass
    return count


def _count_decision_inbox(since_days: int = 30) -> int:
    """Count decision-inbox entries (markdown headers with [YYYY-MM-DD] timestamps)."""
    if not DECISIONS_LOG.is_file():
        return 0
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    pattern = re.compile(r"^##\s*\[(\d{4}-\d{2}-\d{2})\]", re.MULTILINE)
    count = 0
    try:
        text = DECISIONS_LOG.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            try:
                ts = dt.datetime.fromisoformat(m.group(1) + "T00:00:00+00:00")
                if ts >= cutoff:
                    count += 1
            except ValueError:
                count += 1
    except OSError:
        pass
    return count


def _cadence_label(events_per_month: float) -> str:
    if events_per_month >= 12:
        return "high"
    if events_per_month >= 4:
        return "medium"
    if events_per_month >= 1:
        return "low"
    return "none"


def compute_axes(since_days: int = 30) -> dict[str, Any]:
    """Compute the 3 axes with their scores and supporting data."""
    # A-axis: time saved
    counts = {
        "compass_radar_run": _count_health_runs(since_days),
        "drift_sweep_run": 0,  # No telemetry file (drift-sweep doesn't write history)
        "signal_poll": _read_jsonl_events(DUCK_LOG, since_days),  # agent-tick proxy
        "agent_tick": _read_jsonl_events(AUDIT_TICK, since_days),
        "maturity_scorecard_run": 0,
        "document_review_sample": 0,
        "knowledge_curation": 0,
        "staleness_check": 0,
        "cell_episode": _count_cell_episodes(since_days),
    }
    total_minutes = sum(
        TIME_PER_EVENT_MIN[k] * v for k, v in counts.items()
    )
    # Scale: 0-100 score. Reference: 60 min/day × 30 days = 1800 min = 100
    a_score = min(100, round(100 * total_minutes / 1800))
    a_hours = total_minutes / 60

    # B-axis: decision throughput
    decision_count = _count_decision_inbox(since_days)
    decisions_per_month = decision_count * (30 / since_days) if since_days else decision_count
    b_score = min(100, round(10 * decisions_per_month))  # 10 decisions/month = 100
    b_cadence = _cadence_label(decisions_per_month)

    # C-axis: BET done rate (佐证, 不计入 composite)
    c_pct = None
    res = subprocess.run(
        [sys.executable, str(WS_ROOT / "bin" / "plan" / "bet-ledger.py"), "status"],
        cwd=WS_ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    m = re.search(r"done\s+(\d+)", res.stdout or "")
    t = re.search(r"总 bet:\s*(\d+)", res.stdout or "")
    if m and t:
        c_pct = round(100 * int(m.group(1)) / int(t.group(1)), 1)

    # Composite (weighted average, 0 weights redistribute to A)
    weights = {"A": 0.70, "B": 0.30, "C": 0.0}
    score = round(a_score * 0.70 + b_score * 0.30)

    # Status (D5 防腐: 双重阻断 — read-only 永远 unprovable if not enough data)
    if total_minutes == 0 and decision_count == 0:
        status = "unprovable"
    elif a_score < 30 or b_score < 20:
        status = "low"
    elif a_score < 60 or b_score < 50:
        status = "partial"
    else:
        status = "provable"

    return {
        "axes": {
            "A": {
                "name": "时间账本 (主, 70%)",
                "score": a_score,
                "weight": 0.70,
                "data": counts,
                "total_minutes_saved": total_minutes,
                "total_hours_saved": round(a_hours, 1),
                "window_days": since_days,
            },
            "B": {
                "name": "决策吞吐 (30%)",
                "score": b_score,
                "weight": 0.30,
                "data": {"decisions_30d": decision_count},
                "decisions_per_month": round(decisions_per_month, 1),
                "cadence": b_cadence,
            },
            "C": {
                "name": "项目推进力 (佐证, 0%)",
                "score": c_pct if c_pct is not None else 0,
                "weight": 0.0,
                "data": {"bet_done_pct": c_pct},
            },
        },
        "composite": {
            "score": score,
            "weights": weights,
        },
        "status": status,
        "snapshot_at": _utc_now().isoformat().replace("+00:00", "Z"),
    }


def render_text(d: dict[str, Any]) -> str:
    lines = ["=" * 72, "north_star_meter_v3 — 复合制价值证明", "=" * 72]
    lines.append(f"snapshot_at: {d['snapshot_at']}")
    lines.append(f"status:      {d['status'].upper()}")
    lines.append(f"composite:   {d['composite']['score']}/100")
    lines.append("")
    for label, axis in d["axes"].items():
        lines.append(f"  Axis {label} (w={axis['weight']}, {axis['name']}): {axis['score']}/100")
        if label == "A":
            lines.append(f"    time saved (30d): {axis['total_hours_saved']}h = {axis['total_minutes_saved']}min")
            for k, v in axis["data"].items():
                lines.append(f"    - {k:<28} {v}")
        elif label == "B":
            lines.append(f"    decisions: {axis['data']['decisions_30d']} (cadence: {axis['cadence']}, ~{axis['decisions_per_month']}/mo)")
        else:
            lines.append(f"    BET done pct: {axis['data']['bet_done_pct']}%")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="north_star v3 复合制价值证明")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--window", type=int, default=30, help="统计窗口 (天)")
    args = parser.parse_args()
    d = compute_axes(args.window)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(render_text(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())