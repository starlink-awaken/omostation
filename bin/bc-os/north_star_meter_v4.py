#!/usr/bin/env python3
"""north_star_meter_v4: 复合制价值证明 V4 — 实时投影 + 认知杠杆率 (BET-Y1Q3-T10-121).

继承 v3 的 5 轴 + KV cache 框架, V4 新增:
  - realtime 投影: 自当日 0:00 至今的信号增量, 用于 cockpit 实时面板
  - 认知杠杆率 (D2-axis): 主人 D 事件 / 主人 A 事件 = 主人每次"自己跑 A 自动化"
    触发的下游 D 事件数. > 1 = 杠杆放大, < 1 = 单点忙.
  - monthly/quarterly 报告: 增量写入 .omo/_knowledge/reports/

用法:
  python3 bin/bc-os/north_star_meter_v4.py --realtime
  python3 bin/bc-os/north_star_meter_v4.py --report monthly
  python3 bin/bc-os/north_star_meter_v4.py --json
  python3 -m cockpit.cli north-star realtime
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
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
WORKFLOW_MESH_EVENTS = WS_ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
REPORTS_DIR = WS_ROOT / ".omo" / "_knowledge" / "reports"

# A-axis: 系统自动化事件估时 (分钟/事件) — 经验估值, 后续可校准
TIME_PER_EVENT_MIN = {
    "compass_radar_run": 5,
    "drift_sweep_run": 8,
    "signal_poll": 1,
    "agent_tick": 2,
    "maturity_scorecard_run": 4,
    "document_review_sample": 12,
    "knowledge_curation": 3,
    "staleness_check": 2,
}


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _today_start_utc() -> dt.datetime:
    now = _utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _read_jsonl_events(path: Path, since: dt.datetime) -> list[dict]:
    """Read events from JSONL file with timestamp > since.

    Each line is a JSON object. Skips malformed lines. Returns parsed events.
    """
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("ts") or obj.get("timestamp") or obj.get("time")
                if not ts:
                    continue
                try:
                    event_dt = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=dt.timezone.utc)
                if event_dt >= since:
                    out.append(obj)
    except OSError:
        pass
    return out


def _count_health_runs(since: dt.datetime) -> int:
    events = _read_jsonl_events(HEALTH_HISTORY, since)
    return sum(1 for e in events if "compass_radar" in str(e.get("event", "")) or
               "drift_sweep" in str(e.get("event", "")))


def _count_decision_inbox(since: dt.datetime) -> int:
    """Count decision entries in delegation-guardrails/decisions.md since <since>."""
    if not DECISIONS_LOG.is_file():
        return 0
    try:
        text = DECISIONS_LOG.read_text(encoding="utf-8")
    except OSError:
        return 0
    since_date = since.date()
    count = 0
    for match in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})\]", text, re.MULTILINE):
        try:
            d = dt.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if d >= since_date:
            count += 1
    return count


def _cadence_label(events_per_month: float) -> str:
    if events_per_month <= 0:
        return "zero"
    if events_per_month < 3:
        return "low"
    if events_per_month < 10:
        return "medium"
    return "high"


def _count_knowledge_consumption(since: dt.datetime) -> dict[str, int]:
    """Count evidence-recorded + workflow-succeeded events in workflow-mesh/events.jsonl."""
    events = _read_jsonl_events(WORKFLOW_MESH_EVENTS, since)
    counts = {"evidence": 0, "workflow_succeeded": 0, "total": 0}
    for e in events:
        et = str(e.get("event_type", "")).lower()
        if "evidence" in et or e.get("evidence_id"):
            counts["evidence"] += 1
        if "workflow" in et and "succeed" in et:
            counts["workflow_succeeded"] += 1
        counts["total"] += 1
    return counts


def _count_decision_quality(since: dt.datetime) -> dict:
    """Count P0/P1 decisions with adoption."""
    events = _read_jsonl_events(WORKFLOW_MESH_EVENTS, since)
    p0_p1 = sum(1 for e in events if str(e.get("priority", "")) in ("P0", "P1"))
    adopted = sum(1 for e in events if e.get("adopted") or e.get("status") == "adopted")
    ratio = adopted / p0_p1 if p0_p1 else 0.0
    return {"p0_p1_count": p0_p1, "adoption_ratio": ratio}


def _read_kv_cache_stats() -> dict:
    """Read KV cache hit rate from .omo/_control state (best-effort)."""
    stats = {"available": False, "hit_rate": 0.0}
    candidates = [
        WS_ROOT / ".omo" / "_control" / "kv_cache_stats.json",
        WS_ROOT / "runtime" / "kv_cache_stats.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                obj = json.loads(c.read_text(encoding="utf-8"))
                stats["hit_rate"] = float(obj.get("hit_rate", 0.0))
                stats["available"] = True
                break
            except (OSError, ValueError, TypeError):
                pass
    return stats


def compute_axes(since_days: int = 30) -> dict[str, Any]:
    """Compute the 5 axes + KV cache + D2 cognitive leverage.

    Backward compat with v3. Adds D2 cognitive leverage = D / A ratio.
    """
    since = _utc_now() - dt.timedelta(days=since_days)

    # A-axis: time saved
    counts = {
        "compass_radar_run": _count_health_runs(since),
        "drift_sweep_run": 0,
        "signal_poll": len(_read_jsonl_events(DUCK_LOG, since)),
        "agent_tick": len(_read_jsonl_events(AUDIT_TICK, since)),
        "maturity_scorecard_run": 0,
        "document_review_sample": 0,
        "knowledge_curation": 0,
        "staleness_check": 0,
    }
    total_minutes = sum(TIME_PER_EVENT_MIN[k] * v for k, v in counts.items())
    a_score = min(100, round(100 * total_minutes / 1800))

    # B-axis: decision throughput
    decision_count = _count_decision_inbox(since)
    days = max(since_days, 1)
    decisions_per_month = decision_count * (30 / days)
    b_score = min(100, round(10 * decisions_per_month))
    b_cadence = _cadence_label(decisions_per_month)

    # C-axis: BET done rate (advisory)
    c_pct = None
    try:
        res = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin" / "plan" / "bet-ledger.py"), "status"],
            cwd=WS_ROOT, capture_output=True, text=True, check=False, timeout=30,
        )
        m = re.search(r"done\s+(\d+)", res.stdout or "")
        t = re.search(r"总 bet:\s*(\d+)", res.stdout or "")
        if m and t:
            c_pct = round(100 * int(m.group(1)) / int(t.group(1)), 1)
    except (subprocess.TimeoutExpired, OSError):
        pass

    # D-axis: knowledge consumption
    d_counts = _count_knowledge_consumption(since)
    d_total = d_counts["total"]
    d_events_per_month = d_total * (30 / days)
    d_score = min(100, round(100 * d_events_per_month / 30))
    d_cadence = _cadence_label(d_events_per_month)

    # E-axis: decision quality
    e_quality = _count_decision_quality(since)
    e_score = min(100, round(20 * e_quality["p0_p1_count"] * e_quality["adoption_ratio"]))

    # A2-axis: KV cache
    a2_stats = _read_kv_cache_stats()
    a2_score = min(100, round(a2_stats["hit_rate"] * 100)) if a2_stats["available"] else 0

    # 3-axis composite (backward compat)
    weights_3axis = {"A": 0.70, "B": 0.30, "C": 0.0}
    score_3axis = round(a_score * 0.70 + b_score * 0.30)

    # 4-axis advisory
    weights_4axis = {"A": 0.60, "B": 0.20, "C": 0.0, "D": 0.20}
    score_4axis = round(a_score * 0.60 + b_score * 0.20 + d_score * 0.20)

    # D2-axis: cognitive leverage (V4 新增) = D events per A event
    # 高 D2 (>1) = 每次 A 自动化触发多次 D 事件 (杠杆放大)
    # 低 D2 (<1) = 主人单点忙, 无下游
    a_total_events = sum(counts.values())
    if a_total_events > 0:
        d2_leverage = round(d_events_per_month / max(a_total_events, 1), 2)
    else:
        d2_leverage = 0.0
    d2_score = min(100, round(50 + 50 * (1 - abs(1.0 - d2_leverage) / max(1.0, d2_leverage))))
    # D2 score: 1.0 leverage = 100, 0.5/2.0 = ~50

    # Status
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
                "name": "时间账本 (3-axis 0.70)",
                "score": a_score, "weight": 0.70,
                "data": counts, "total_minutes_saved": total_minutes,
            },
            "B": {
                "name": "决策吞吐 (3-axis 0.30)",
                "score": b_score, "weight": 0.30,
                "decisions_in_window": decision_count,
                "decisions_per_month": round(decisions_per_month, 2),
                "cadence": b_cadence,
            },
            "C": {
                "name": "BET done rate (advisory, 0.00)",
                "score": c_pct if c_pct is not None else 0,
                "weight": 0.0, "pct": c_pct,
            },
            "D": {
                "name": "知识消费 (4-axis 0.20)",
                "score": d_score, "weight": 0.20,
                "data": d_counts,
                "events_per_month": round(d_events_per_month, 2),
                "cadence": d_cadence,
            },
            "E": {
                "name": "决策质量 (5-axis advisory)",
                "score": e_score,
                "data": e_quality,
            },
            "A2": {
                "name": "KV cache hit rate (advisory)",
                "score": a2_score,
                "available": a2_stats["available"],
            },
            "D2": {
                "name": "认知杠杆率 (V4 新增, advisory)",
                "score": d2_score,
                "leverage_ratio": d2_leverage,
                "explanation": "D events / A events, 1.0=balanced, >1=杠杆放大, <1=单点忙",
            },
        },
        "weights_3axis": weights_3axis,
        "weights_4axis": weights_4axis,
        "score_3axis": score_3axis,
        "score_4axis": score_4axis,
        "status": status,
        "window_days": since_days,
        "generated_at": _utc_now().isoformat(),
    }


def compute_realtime() -> dict[str, Any]:
    """Realtime projection since today 0:00 UTC. V4 新增."""
    today = _today_start_utc()
    counts = {
        "compass_radar_run": _count_health_runs(today),
        "signal_poll": len(_read_jsonl_events(DUCK_LOG, today)),
        "agent_tick": len(_read_jsonl_events(AUDIT_TICK, today)),
    }
    total_minutes = sum(TIME_PER_EVENT_MIN[k] * v for k, v in counts.items() if k in TIME_PER_EVENT_MIN)
    decisions_today = _count_decision_inbox(today)
    knowledge_today = _count_knowledge_consumption(today)["total"]
    return {
        "scope": "realtime",
        "since": today.isoformat(),
        "until": _utc_now().isoformat(),
        "axes_realtime": {
            "A_minutes_today": total_minutes,
            "B_decisions_today": decisions_today,
            "D_knowledge_today": knowledge_today,
            "counts": counts,
        },
        "status": "live",
    }


def _report_path(period: str) -> Path:
    """Compute report file path with date suffix. Idempotent — same date = same path."""
    today = _utc_now().strftime("%Y-%m")
    if period == "monthly":
        name = f"north-star-monthly-{today}.md"
    elif period == "quarterly":
        # Quarter = (month-1)//3 + 1
        m = _utc_now().month
        q = (m - 1) // 3 + 1
        y = _utc_now().year
        name = f"north-star-quarterly-{y}-Q{q}.md"
    else:
        raise ValueError(f"unknown period: {period}")
    return REPORTS_DIR / name


def render_report(axes: dict[str, Any], realtime: dict[str, Any], period: str) -> str:
    """Render monthly/quarterly report as Markdown."""
    today = _utc_now().strftime("%Y-%m-%d")
    axes_a = axes["axes"]["A"]
    axes_b = axes["axes"]["B"]
    axes_d = axes["axes"]["D"]
    axes_d2 = axes["axes"]["D2"]
    a_min = axes_a["total_minutes_saved"]
    a_hours = a_min / 60
    lines = [
        f"# 北极星价值报告 ({period}) — {today}",
        "",
        f"> 状态: **{axes['status']}** | 3-axis composite: {axes['score_3axis']} | 4-axis: {axes['score_4axis']}",
        "",
        "## A 时间账本",
        f"- 节省工时: {a_min} 分钟 ({a_hours:.1f} 小时) / {axes['window_days']} 天",
        f"- Score: {axes_a['score']}/100",
        "",
        "## B 决策吞吐",
        f"- 决策数: {axes_b['decisions_in_window']} / {axes['window_days']} 天",
        f"- 月均: {axes_b['decisions_per_month']} 条",
        f"- Cadence: {axes_b['cadence']}",
        f"- Score: {axes_b['score']}/100",
        "",
        "## D 知识消费 (V4 新增: 认知杠杆率)",
        f"- 知识事件: {axes_d['data']['total']} / {axes['window_days']} 天",
        f"- D2 杠杆率: {axes_d2['leverage_ratio']} (D / A 事件比)",
        f"- D2 Score: {axes_d2['score']}/100",
        f"- 解读: {axes_d2['explanation']}",
        "",
        "## 实时投影 (今日 0:00 至今)",
        f"- A 节省工时: {realtime['axes_realtime']['A_minutes_today']} 分钟",
        f"- B 今日决策: {realtime['axes_realtime']['B_decisions_today']}",
        f"- D 今日知识: {realtime['axes_realtime']['D_knowledge_today']}",
        "",
        f"_Generated: {_utc_now().isoformat()}_",
    ]
    return "\n".join(lines) + "\n"


def write_report_atomic(path: Path, content: str) -> None:
    """Write report atomically with file lock for idempotency."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            path.write_text(content, encoding="utf-8")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def main() -> int:
    parser = argparse.ArgumentParser(description="north_star v4 复合制价值证明 + 实时投影")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--window", type=int, default=30, help="统计窗口 (天, 默认 30)")
    parser.add_argument("--realtime", action="store_true", help="输出今日 0:00 至今的实时投影")
    parser.add_argument("--report", choices=["monthly", "quarterly"],
                        help="生成月度/季度 Markdown 报告")
    args = parser.parse_args()

    axes = compute_axes(args.window)
    payload: dict[str, Any] = {"axes": axes}

    if args.realtime:
        payload["realtime"] = compute_realtime()

    if args.report:
        if "realtime" not in payload:
            payload["realtime"] = compute_realtime()
        content = render_report(axes, payload["realtime"], args.report)
        path = _report_path(args.report)
        write_report_atomic(path, content)
        payload["report_written"] = str(path)
        if not args.json:
            print(f"报告已写入: {path}")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        # Compact text output
        a = axes["axes"]["A"]
        b = axes["axes"]["B"]
        d = axes["axes"]["D"]
        d2 = axes["axes"]["D2"]
        print(f"=== north-star v4 — {axes['status']} ===")
        print(f"  A 时间账本: {a['score']}/100 ({a['total_minutes_saved']} min)")
        print(f"  B 决策吞吐: {b['score']}/100 ({b['decisions_in_window']} in {args.window}d)")
        print(f"  D 知识消费: {d['score']}/100 ({d['data']['total']} events)")
        print(f"  D2 认知杠杆率: {d2['score']}/100 (ratio={d2['leverage_ratio']})")
        print(f"  composite (3-axis): {axes['score_3axis']}")
        if "realtime" in payload:
            rt = payload["realtime"]["axes_realtime"]
            print(f"  realtime (今日): A={rt['A_minutes_today']}min, B={rt['B_decisions_today']}dec, D={rt['D_knowledge_today']}ev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
