#!/usr/bin/env python3
"""north_star_meter_v3: 复合制价值证明 (project-strategy-v1 §5.2 落地).

4 轴复合 (D4 混合数据源策略):
  A 时间账本 (主, 3-axis 0.70): 系统自动化事件数 × 估时/事件 → 月可证时间节省
  B 决策吞吐 (3-axis 0.30): 决策收件箱条目数 + cadence (0/低/中/高)
  C 项目推进力 (3-axis 0.00, advisory): BET done rate (无成本导出)
  D 知识消费深度 (advisory, 4-axis 0.20): EvidenceRecorded + WorkflowSucceeded
    拉平 compass_radar(55) ↔ bet_ledger(95) 的口径差距 — 两者都能讲同一个故事.

+ Journey Completion Rate (BET-Y1Q4-T4-02): 有效工作旅程完成率北极星基线
  - 分母: 进入工作旅程的真实外部信号实例
  - 分子: 到达人类裁决终态且非 discard-only 的旅程
  - 缺数据时显式 unmeasured, 禁止填 0 伪装

输出: provable / partial / unprovable + 主 3 轴得分 + 4-axis advisory + journey baseline.

用法:
  python3 bin/bc-os/north_star_meter_v3.py --json
  python3 bin/bc-os/north_star_meter_v3.py
  python3 bin/bc-os/north_star_meter_v3.py --json --since-days 7
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
WORKFLOW_MESH_EVENTS = WS_ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"

# ---------------------------------------------------------------------------
# Journey Completion Rate (BET-Y1Q4-T4-02)
# ---------------------------------------------------------------------------

JOURNEY_BASELINE_SCHEMA = "journey-baseline/v1"
DEFAULT_EVENT_LEDGER = WS_ROOT / "runtime" / "omo" / "event-ledger.sqlite3"
MIN_JOURNEY_WINDOW_DAYS = 7


def _query_journey_completion(
    db_path: Path,
    window_start: str,
    window_end: str,
) -> tuple[int, int, list[str]]:
    """Query event ledger for journey completion data.

    Returns (denominator, numerator, gap_inventory).

    Denominator = work journeys triggered by real external signals.
    Numerator = journeys reaching human-adjudication terminal state
    (accepted/edited/rejected, not discard-only).
    """
    gaps: list[str] = []
    if not db_path.is_file():
        gaps.append("event-ledger-missing")
        return 0, 0, gaps

    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        gaps.append(f"ledger-open-failed:{exc}")
        return 0, 0, gaps

    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        denominator = 0
        if "signal_event" in tables and "journey_instance" in tables:
            cur.execute(
                """
                SELECT COUNT(DISTINCT se.id)
                FROM signal_event se
                JOIN journey_instance ji ON ji.trigger_signal_id = se.id
                WHERE se.domain = 'work'
                  AND se.timestamp >= ? AND se.timestamp < ?
                """,
                (window_start, window_end),
            )
            denominator = cur.fetchone()[0] or 0
        elif "events" in tables:
            cur.execute(
                """
                SELECT COUNT(DISTINCT e.id) FROM events e
                WHERE e.type = 'signal.ingested' AND e.domain = 'work'
                  AND e.timestamp >= ? AND e.timestamp < ?
                """,
                (window_start, window_end),
            )
            denominator = cur.fetchone()[0] or 0
        else:
            gaps.append("ledger-no-signal-table")

        numerator = 0
        if "outcome_event" in tables and "journey_instance" in tables:
            cur.execute(
                """
                SELECT COUNT(DISTINCT oe.journey_id)
                FROM outcome_event oe
                JOIN journey_instance ji ON ji.id = oe.journey_id
                WHERE oe.verdict IN ('accepted', 'edited', 'rejected')
                  AND (oe.review_type IS NULL OR oe.review_type != 'discard_only')
                  AND oe.timestamp >= ? AND oe.timestamp < ?
                """,
                (window_start, window_end),
            )
            numerator = cur.fetchone()[0] or 0
        elif "events" in tables:
            cur.execute(
                """
                SELECT COUNT(DISTINCT e.journey_id) FROM events e
                WHERE e.type = 'outcome.resolved'
                  AND e.verdict IN ('accepted', 'edited', 'rejected')
                  AND (e.review_type IS NULL OR e.review_type != 'discard_only')
                  AND e.timestamp >= ? AND e.timestamp < ?
                """,
                (window_start, window_end),
            )
            numerator = cur.fetchone()[0] or 0
        else:
            gaps.append("ledger-no-outcome-table")

        conn.close()
    except sqlite3.Error as exc:
        gaps.append(f"ledger-query-failed:{exc}")
        conn.close()
        return 0, 0, gaps

    return denominator, numerator, gaps


def measure_journey_completion(
    *,
    db_path: Path | str = DEFAULT_EVENT_LEDGER,
    window_days: int = MIN_JOURNEY_WINDOW_DAYS,
) -> dict[str, Any]:
    """Compute journey completion baseline. Projection only, never writes.

    Metric: completed_work_journeys / entered_work_journeys
    Circuit breaker: returns unmeasured + gap inventory when data insufficient.
    """
    path = Path(db_path)
    end = dt.datetime.now(dt.UTC)
    start = end - dt.timedelta(days=window_days)
    start_str = start.isoformat().replace("+00:00", "Z")
    end_str = end.isoformat().replace("+00:00", "Z")

    denominator, numerator, gaps = _query_journey_completion(path, start_str, end_str)

    result: dict[str, Any] = {
        "schema_version": JOURNEY_BASELINE_SCHEMA,
        "observed_at": _utc_now().isoformat().replace("+00:00", "Z"),
        "window": {"start": start_str, "end": end_str, "days": window_days},
        "metric": "journey_completion_rate",
        "denominator": denominator,
        "numerator": numerator,
        "evidence_refs": [],
        "gap_inventory": gaps,
    }

    if not path.is_file():
        result["status"] = "unmeasured"
        result["reason"] = "event-ledger-not-available"
        return result

    if window_days < MIN_JOURNEY_WINDOW_DAYS:
        result["status"] = "unmeasured"
        result["reason"] = f"window-too-short (minimum {MIN_JOURNEY_WINDOW_DAYS}d)"
        gaps.append(f"need-{MIN_JOURNEY_WINDOW_DAYS}d-window")
        return result

    if denominator < 1:
        result["status"] = "unmeasured"
        result["reason"] = "insufficient-journey-data"
        gaps.append("need-at-least-1-work-journey")
        return result

    rate = numerator / denominator if denominator > 0 else 0.0
    result["status"] = "measured"
    result["value"] = round(rate, 4)
    result["evidence_refs"] = [f"repo://{path.relative_to(WS_ROOT).as_posix()}"]
    return result

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


def _count_knowledge_consumption(since_days: int = 30) -> dict[str, int]:
    """D-axis: knowledge consumption via workflow-mesh evidence + success events.

    Both compass_radar (governance health) and bet_ledger (delivery %) can verify
    these events because they are recorded by the central workflow-mesh writer.
    """
    if not WORKFLOW_MESH_EVENTS.is_file():
        return {"evidence_recorded": 0, "workflow_succeeded": 0, "total": 0}
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    counts = {"evidence_recorded": 0, "workflow_succeeded": 0, "total": 0}
    try:
        for line in WORKFLOW_MESH_EVENTS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = rec.get("occurred_at") or rec.get("ts") or rec.get("ts_iso") or ""
            if not ts_str:
                continue
            try:
                ts = dt.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.UTC)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                continue
            et = rec.get("event_type") or ""
            if et == "EvidenceRecorded":
                counts["evidence_recorded"] += 1
                counts["total"] += 1
            elif et == "WorkflowSucceeded":
                counts["workflow_succeeded"] += 1
                counts["total"] += 1
    except OSError:
        pass
    return counts
def _count_decision_quality(since_days: int = 30) -> dict:
    """Count P0/P1 decisions and adoption ratio from decisions.md."""
    decisions_path = WS_ROOT / ".omo" / "notepads" / "delegation-guardrails" / "decisions.md"
    if not decisions_path.exists():
        return {"p0_p1_count": 0, "p2_count": 0, "total": 0, "adopted_count": 0, "adoption_ratio": 0.0}

    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=since_days)

    try:
        text = decisions_path.read_text(encoding="utf-8")
    except OSError:
        return {"p0_p1_count": 0, "p2_count": 0, "total": 0, "adopted_count": 0, "adoption_ratio": 0.0}

    # Split into decision blocks
    blocks = re.split(r"## \[", text)

    p0_p1_count = 0
    p2_count = 0
    total = 0
    adopted_count = 0
    p0_p1_adoption = 0

    for block in blocks[1:]:  # Skip first empty part
        # Extract date
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", block)
        if not date_match:
            continue

        try:
            block_date = dt.datetime.fromisoformat(date_match.group(1) + "T00:00:00+00:00")
            if block_date < cutoff:
                continue
        except ValueError:
            continue

        total += 1

        # Check priority
        if re.search(r"P0:", block):
            p0_p1_count += 1
        elif re.search(r"P1:", block):
            p0_p1_count += 1
        elif re.search(r"P2:", block):
            p2_count += 1

        # Check adoption (has verification section)
        if re.search(r"验证|已实施|已合并|已部署|已上线", block):
            adopted_count += 1
            if re.search(r"P0:|P1:", block):
                p0_p1_adoption += 1

    adoption_ratio = adopted_count / total if total > 0 else 0.0

    return {
        "p0_p1_count": p0_p1_count,
        "p2_count": p2_count,
        "total": total,
        "adopted_count": adopted_count,
        "adoption_ratio": round(adoption_ratio, 2),
        "p0_p1_adoption_rate": round(p0_p1_adoption / p0_p1_count if p0_p1_count > 0 else 0.0, 2),
    }



def _read_kv_cache_stats() -> dict:
    """Read KV cache statistics from omlxc persistence for A2 axis."""
    cache_stats_path = Path.home() / ".omlxc" / "cache_stats.json"
    if not cache_stats_path.exists():
        return {"hit_rate": 0.0, "total_queries": 0, "available": False}

    try:
        import json
        stats = json.loads(cache_stats_path.read_text())
        total = stats.get("l1_hits", 0) + stats.get("l2_hits", 0) + stats.get("misses", 0)
        hit_rate = stats.get("l1_hits", 0) / total if total > 0 else 0.0
        return {
            "hit_rate": hit_rate,
            "total_queries": total,
            "l1_hits": stats.get("l1_hits", 0),
            "l2_hits": stats.get("l2_hits", 0),
            "available": True,
        }
    except Exception:
        return {"hit_rate": 0.0, "total_queries": 0, "available": False}

def compute_axes(since_days: int = 30) -> dict[str, Any]:
    """Compute the 4 axes with their scores and supporting data."""
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

    # D-axis: knowledge consumption (advisory, 4-axis composite)
    d_counts = _count_knowledge_consumption(since_days)
    d_total = d_counts["total"]
    # Scale: 30 evidence+success events per 30d = 100 (1/day = full credit)
    d_events_per_month = d_total * (30 / since_days) if since_days else d_total
    d_score = min(100, round(100 * d_events_per_month / 30))
    d_cadence = _cadence_label(d_events_per_month)

    # E-axis: Decision Quality (advisory, 5-axis composite)
    e_quality = _count_decision_quality(since_days)
    # Scale: 5 P0/P1 decisions with 100% adoption = 100
    e_score = min(100, round(20 * e_quality["p0_p1_count"] * e_quality["adoption_ratio"]))

    # A2-axis: KV Cache Hit Rate (advisory)
    a2_stats = _read_kv_cache_stats()
    # Scale: 50% hit rate = 50, 100% hit rate = 100
    a2_score = min(100, round(a2_stats["hit_rate"] * 100)) if a2_stats["available"] else 0

    # 3-axis composite (BC — main score, backward compat for strategy-check)
    weights_3axis = {"A": 0.70, "B": 0.30, "C": 0.0}
    score_3axis = round(a_score * 0.70 + b_score * 0.30)

    # 4-axis advisory composite (D pulls 0.10 from A and 0.10 from B)
    weights_4axis = {"A": 0.60, "B": 0.20, "C": 0.0, "D": 0.20}
    score_4axis = round(a_score * 0.60 + b_score * 0.20 + d_score * 0.20)

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
                "name": "时间账本 (主, 3-axis 0.70)",
                "score": a_score,
                "weight": 0.70,
                "data": counts,
                "total_minutes_saved": total_minutes,
                "total_hours_saved": round(a_hours, 1),
                "window_days": since_days,
            },
            "B": {
                "name": "决策吞吐 (3-axis 0.30)",
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
            "D": {
                "name": "知识消费深度 (advisory, 4-axis 0.20)",
                "score": d_score,
                "weight": 0.20,
                "data": d_counts,
                "events_per_month": round(d_events_per_month, 1),
                "cadence": d_cadence,
            },
            "E": {
                "name": "决策质量 (advisory, 5-axis 0.15)",
                "score": e_score,
                "weight": 0.15,
                "data": e_quality,
            },
            "A2": {
                "name": "KV Cache Hit Rate (advisory)",
                "score": a2_score,
                "weight": 0.0,
                "data": a2_stats,
            },
        },
        "composite": {
            "score": score_3axis,
            "weights": weights_3axis,
        },
        "composite_4axis": {
            "score": score_4axis,
            "weights": weights_4axis,
            "advisory": True,
            "note": "A60+B20+D20; pulls 0.10 from A and 0.10 from B; aligns compass_radar↔bet_ledger.",
        },
        "composite_6axis": {
            "score": round(a_score * 0.45 + b_score * 0.08 + d_score * 0.18 + e_score * 0.14 + a2_score * 0.15),
            "weights": {"A": 0.45, "B": 0.08, "C": 0.0, "D": 0.18, "E": 0.14, "A2": 0.15},
            "advisory": True,
            "note": "A45+B8+D18+E14+A215; A2 adds KV cache efficiency dimension.",
            "signpost": {
                "5axis_vs_6axis": "6-axis adds A2 (KV cache) at 0.15 weight. When cache is cold (hit_rate=0), score drops significantly.",
                "axis_contributions": {
                    "A": round(a_score * 0.45, 1),
                    "B": round(b_score * 0.08, 1),
                    "D": round(d_score * 0.18, 1),
                    "E": round(e_score * 0.14, 1),
                    "A2": round(a2_score * 0.15, 1),
                }
            },
        },
        "composite_5axis": {
            "score": round(a_score * 0.50 + b_score * 0.10 + d_score * 0.20 + e_score * 0.15),
            "weights": {"A": 0.50, "B": 0.10, "C": 0.0, "D": 0.20, "E": 0.15},
            "advisory": True,
            "note": "A50+B10+D20+E15; E adds decision quality dimension.",
            "signpost": {
                "4axis_vs_5axis": "5-axis is 3pts lower because B weight dropped from 0.20 to 0.10 (-8pts) while A dropped from 0.60 to 0.50 (-10pts), offset by E adding 15pts.",
                "axis_contributions": {
                    "A": round(a_score * 0.50, 1),
                    "B": round(b_score * 0.10, 1),
                    "D": round(d_score * 0.20, 1),
                    "E": round(e_score * 0.15, 1),
                }
            },
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
        elif label == "D":
            lines.append(
                f"    knowledge events: {axis['data']['total']} (evidence={axis['data']['evidence_recorded']}, succeeded={axis['data']['workflow_succeeded']}, cadence: {axis['cadence']}, ~{axis['events_per_month']}/mo)"
            )
        elif label == "E":
            lines.append(
                f"    P0/P1 decisions: {axis['data']['p0_p1_count']}/{axis['data']['total']} (adopted: {axis['data']['adopted_count']}, ratio: {axis['data']['adoption_ratio']:.0%})"
            )
        elif label == "A2":
            hit_rate = axis["data"].get("hit_rate", 0)
            total = axis["data"].get("total_queries", 0)
            lines.append(f"    hit_rate: {hit_rate:.1%} ({total} queries)")
        else:
            lines.append(f"    BET done pct: {axis['data']['bet_done_pct']}%")
    lines.append("")
    lines.append(f"  composite (3-axis, BC):    {d['composite']['score']}/100  weights={d['composite']['weights']}")
    lines.append(f"  composite (4-axis, advisory): {d['composite_4axis']['score']}/100  weights={d['composite_4axis']['weights']}")
    lines.append(f"  composite (5-axis, advisory): {d['composite_5axis']['score']}/100  weights={d['composite_5axis']['weights']}")

    # Journey Completion Rate (BET-Y1Q4-T4-02)
    journey = d.get("journey_completion")
    if journey:
        lines.append("")
        lines.append(f"  journey_completion_rate: {journey.get('status', 'unknown')}")
        if journey.get("status") == "measured":
            lines.append(f"    value: {journey['value']:.2%} ({journey['numerator']}/{journey['denominator']})")
            lines.append(f"    window: {journey['window']['days']}d ({journey['window']['start'][:10]} .. {journey['window']['end'][:10]})")
        else:
            lines.append(f"    reason: {journey.get('reason', 'unknown')}")
            if journey.get("gap_inventory"):
                lines.append(f"    gaps: {', '.join(journey['gap_inventory'])}")

    lines.append(f"  status: {d['status']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="north_star v3 复合制价值证明")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--window", type=int, default=30, help="统计窗口 (天)")
    parser.add_argument("--journey", action="store_true", help="仅输出旅程完成率基线 (journey-baseline/v1)")
    parser.add_argument("--journey-window", type=int, default=MIN_JOURNEY_WINDOW_DAYS, help=f"旅程基线窗口天数 (默认 {MIN_JOURNEY_WINDOW_DAYS})")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_EVENT_LEDGER), help="事件台账 SQLite 路径")
    args = parser.parse_args()

    if args.journey:
        result = measure_journey_completion(db_path=args.db_path, window_days=args.journey_window)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            status = result["status"]
            if status == "measured":
                print(f"journey_completion_rate: {result['value']:.2%} ({result['numerator']}/{result['denominator']})")
            else:
                print(f"journey_completion_rate: {status} ({result.get('reason', 'unknown')})")
                if result.get("gap_inventory"):
                    print(f"  gaps: {', '.join(result['gap_inventory'])}")
        return 0

    d = compute_axes(args.window)
    d["journey_completion"] = measure_journey_completion(db_path=args.db_path, window_days=args.journey_window)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(render_text(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
