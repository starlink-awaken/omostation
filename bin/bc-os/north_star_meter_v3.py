#!/usr/bin/env python3
"""north_star_meter_v3: 复合制价值证明 (project-strategy-v1 §5.2 落地).

4 轴复合 (D4 混合数据源策略):
  A 时间账本 (主, 3-axis 0.70): 系统自动化事件数 × 估时/事件 → 月可证时间节省
  B 决策吞吐 (3-axis 0.30): 决策收件箱条目数 + cadence (0/低/中/高)
  C 项目推进力 (3-axis 0.00, advisory): BET done rate (无成本导出)
  D 知识消费深度 (advisory, 4-axis 0.20): EvidenceRecorded + WorkflowSucceeded
    拉平 compass_radar(55) ↔ bet_ledger(95) 的口径差距 — 两者都能讲同一个故事.

输出: provable / partial / unprovable + 主 3 轴得分 + 4-axis advisory.

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

# A-axis: 系统自动化事件估时 (分钟/事件) — 这些值是经验估值, 后续可校准
TIME_PER_EVENT_MIN = {
    "compass_radar_run": 5,  # 一次健康巡检手动跑 ~5min
    "drift_sweep_run": 8,  # 漂移扫描 ~8min
    "signal_poll": 1,  # 信号轮询 ~1min
    "agent_tick": 2,  # 一次 agent 后台 tick ~2min
    "maturity_scorecard_run": 4,  # 成熟度扫描 ~4min
    "document_review_sample": 12,  # 一份公文 review ~12min
    "knowledge_curation": 3,  # 知识策展一次 ~3min
    "staleness_check": 2,  # staleness 检查 ~2min
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


_P_RE = re.compile(r"^##\s*\[\d{4}-\d{2}-\d{2}\]\s*P([0-2])\b", re.MULTILINE)
_ADOPT_RE = re.compile(r"^-\s+\*\*(验证|实施)\*\*", re.MULTILINE)


def _analyze_decisions(since_days: int = 30) -> dict[str, Any]:
    """E-axis: per-decision P-level + adoption analysis.

    Each `## [DATE] P{0-2}: TITLE` block counts as one decision. A decision is
    'adopted' if its body contains at least one 验证/实施/决策/方案 marker, which
    is the convention in delegation-guardrails/decisions.md.

    Returns counts + the global adoption ratio so callers can compute
    weighted quality scores.
    """
    out: dict[str, Any] = {
        "p0_p1_count": 0,
        "p2_count": 0,
        "adopted_count": 0,
        "total": 0,
        "adoption_ratio": 0.0,
    }
    if not DECISIONS_LOG.is_file():
        return out
    cutoff = _utc_now() - dt.timedelta(days=since_days)
    try:
        text = DECISIONS_LOG.read_text(encoding="utf-8")
    except OSError:
        return out
    blocks = re.split(r"(?=^##\s*\[)", text, flags=re.MULTILINE)
    for blk in blocks:
        head_m = re.match(r"^##\s*\[(\d{4}-\d{2}-\d{2})\]", blk)
        if not head_m:
            continue
        try:
            ts = dt.datetime.fromisoformat(head_m.group(1) + "T00:00:00+00:00")
            if ts < cutoff:
                continue
        except ValueError:
            pass
        p_m = _P_RE.search(blk)
        level = int(p_m.group(1)) if p_m else -1  # -1 = unprioritized
        adopted = bool(_ADOPT_RE.search(blk))
        out["total"] += 1
        if level in (0, 1):
            out["p0_p1_count"] += 1
        elif level == 2:
            out["p2_count"] += 1
        if adopted:
            out["adopted_count"] += 1
    ratio: float = round(out["adopted_count"] / out["total"], 2) if out["total"] else 0.0
    out["adoption_ratio"] = ratio
    return out


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


def _read_kv_cache_stats(timeout: int = 5) -> dict[str, Any]:
    """A2-axis: live KV-cache efficiency from omlxc fabric inspect.

    Reads omlxc/dataplane/SemanticCacheRegistry state via the JSON CLI. Returns
    `{hit_rate, l1_hits, l2_hits, total_queries, total_entries, available}`.
    If omlxc isn't installed or times out, returns `available=False` so the
    composite treats it as 0 without failing the whole meter.
    """
    omlxc_cli = WS_ROOT / "projects" / "omlxc"
    if not omlxc_cli.is_dir():
        return {
            "available": False,
            "hit_rate": 0.0,
            "l1_hits": 0,
            "l2_hits": 0,
            "total_queries": 0,
            "total_entries": 0,
            "note": "omlxc not installed",
        }
    try:
        res = subprocess.run(
            ["uv", "run", "--directory", str(omlxc_cli), "omlxc", "fabric", "inspect", "--json"],
            cwd=WS_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {
            "available": False,
            "hit_rate": 0.0,
            "l1_hits": 0,
            "l2_hits": 0,
            "total_queries": 0,
            "total_entries": 0,
            "note": f"timeout or os error: {type(e).__name__}",
        }
    if res.returncode != 0:
        return {
            "available": False,
            "hit_rate": 0.0,
            "l1_hits": 0,
            "l2_hits": 0,
            "total_queries": 0,
            "total_entries": 0,
            "note": f"omlxc inspect exit {res.returncode}",
        }
    try:
        payload = json.loads(res.stdout)
        cs = payload.get("data", {}).get("cache_stats", {})
    except (json.JSONDecodeError, AttributeError):
        return {
            "available": False,
            "hit_rate": 0.0,
            "l1_hits": 0,
            "l2_hits": 0,
            "total_queries": 0,
            "total_entries": 0,
            "note": "parse error",
        }
    return {
        "available": True,
        "hit_rate": float(cs.get("hit_rate", 0.0)),
        "l1_hits": int(cs.get("l1_exact_hits", 0)),
        "l2_hits": int(cs.get("l2_semantic_hits", 0)),
        "total_queries": int(cs.get("total_queries", 0)),
        "total_entries": int(cs.get("total_entries", 0)),
    }


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
    total_minutes = sum(TIME_PER_EVENT_MIN[k] * v for k, v in counts.items())
    # Scale: 0-100 score. Reference: 60 min/day × 30 days = 1800 min = 100
    a_score = min(100, round(100 * total_minutes / 1800))
    a_hours = total_minutes / 60

    # A2-axis: KV-cache accelerated inference (omlxc two-tier cache).
    # Score is the cache hit_rate × 100, capped at 100. When the in-memory
    # cache is empty (no live omlxc queries yet) the honest reading is 0 —
    # the value is real only when the cache is actively serving inference.
    a2_stats = _read_kv_cache_stats()
    a2_score = min(100, round(100 * a2_stats["hit_rate"])) if a2_stats["available"] else 0

    # B-axis: decision throughput
    decision_count = _count_decision_inbox(since_days)
    decisions_per_month = decision_count * (30 / since_days) if since_days else decision_count
    b_score = min(100, round(10 * decisions_per_month))  # 10 decisions/month = 100
    b_cadence = _cadence_label(decisions_per_month)

    # C-axis: BET done rate (佐证, 不计入 composite)
    c_pct = None
    res = subprocess.run(
        [sys.executable, str(WS_ROOT / "bin" / "plan" / "bet-ledger.py"), "status"],
        cwd=WS_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
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

    # E-axis: decision quality (advisory, 5-axis composite).
    # Quality = P0/P1 decisions × adoption_ratio. Reference: 5 P0/P1 adopted
    # decisions per 30d = 100 (≈ 1 high-value adopted decision per week).
    e_analysis = _analyze_decisions(since_days)
    e_p0_p1_per_month = e_analysis["p0_p1_count"] * (30 / since_days) if since_days else e_analysis["p0_p1_count"]
    e_quality_score = e_p0_p1_per_month * e_analysis["adoption_ratio"]
    e_score = min(100, round(20 * e_quality_score))

    # 3-axis composite (BC — main score, backward compat for strategy-check)
    weights_3axis = {"A": 0.70, "B": 0.30, "C": 0.0}
    score_3axis = round(a_score * 0.70 + b_score * 0.30)

    # 4-axis advisory composite (D pulls 0.10 from A and 0.10 from B)
    weights_4axis = {"A": 0.60, "B": 0.20, "C": 0.0, "D": 0.20}
    score_4axis = round(a_score * 0.60 + b_score * 0.20 + d_score * 0.20)

    # 5-axis advisory composite (E pulls 0.10 from B; B becomes advisory)
    weights_5axis = {"A": 0.55, "B": 0.10, "C": 0.0, "D": 0.20, "E": 0.15}
    score_5axis = round(a_score * 0.55 + b_score * 0.10 + d_score * 0.20 + e_score * 0.15)

    # 6-axis advisory composite (A2 added; pulls 0.10 from A; A1 = A)
    # A1 = event-driven time savings (B-series); A2 = inference-time KV cache.
    weights_6axis = {"A1": 0.45, "A2": 0.10, "B": 0.10, "C": 0.0, "D": 0.20, "E": 0.15}
    score_6axis = round(a_score * 0.45 + a2_score * 0.10 + b_score * 0.10 + d_score * 0.20 + e_score * 0.15)

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
            "A1": {
                "name": "时间账本 A1 (主, 3-axis 0.70)",
                "score": a_score,
                "weight": 0.70,
                "data": counts,
                "total_minutes_saved": total_minutes,
                "total_hours_saved": round(a_hours, 1),
                "window_days": since_days,
            },
            "A2": {
                "name": "KV 缓存加速 A2 (advisory, 6-axis 0.10)",
                "score": a2_score,
                "weight": 0.10,
                "data": a2_stats,
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
                "data": e_analysis,
                "p0_p1_per_month": round(e_p0_p1_per_month, 1),
                "adoption_ratio": e_analysis["adoption_ratio"],
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
        "composite_5axis": {
            "score": score_5axis,
            "weights": weights_5axis,
            "advisory": True,
            "note": "A55+B10+D20+E15; E pulls 0.10 from B; weights decision quality (P0/P1 × adoption).",
        },
        "composite_6axis": {
            "score": score_6axis,
            "weights": weights_6axis,
            "advisory": True,
            "note": "A1=0.45 + A2=0.10 + B=0.10 + D=0.20 + E=0.15; A1 (events) split from A; A2 (KV cache) added; A1 weight drops 0.55->0.45.",
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
        if label == "A1":
            lines.append(f"    time saved (30d): {axis['total_hours_saved']}h = {axis['total_minutes_saved']}min")
            for k, v in axis["data"].items():
                lines.append(f"    - {k:<28} {v}")
        elif label == "A2":
            cs = axis["data"]
            note = f" ({cs['note']})" if cs.get("note") else ""
            lines.append(
                f"    KV cache hit_rate: {cs['hit_rate']:.2%} (l1={cs['l1_hits']}, l2={cs['l2_hits']}, queries={cs['total_queries']}, entries={cs['total_entries']}, available={cs['available']}){note}"
            )
        elif label == "B":
            lines.append(
                f"    decisions: {axis['data']['decisions_30d']} (cadence: {axis['cadence']}, ~{axis['decisions_per_month']}/mo)"
            )
        elif label == "D":
            lines.append(
                f"    knowledge events: {axis['data']['total']} (evidence={axis['data']['evidence_recorded']}, succeeded={axis['data']['workflow_succeeded']}, cadence: {axis['cadence']}, ~{axis['events_per_month']}/mo)"
            )
        elif label == "E":
            ed = axis["data"]
            lines.append(
                f"    P0/P1 decisions: {ed['p0_p1_count']} (P2: {ed['p2_count']}, adopted: {ed['adopted_count']}/{ed['total']} ratio={ed['adoption_ratio']}, ~{axis['p0_p1_per_month']}/mo)"
            )
        else:
            lines.append(f"    BET done pct: {axis['data']['bet_done_pct']}%")
    lines.append("")
    lines.append(f"  composite (3-axis, BC):       {d['composite']['score']}/100  weights={d['composite']['weights']}")
    lines.append(
        f"  composite (4-axis, advisory): {d['composite_4axis']['score']}/100  weights={d['composite_4axis']['weights']}"
    )
    if "composite_5axis" in d:
        lines.append(
            f"  composite (5-axis, advisory): {d['composite_5axis']['score']}/100  weights={d['composite_5axis']['weights']}"
        )
    if "composite_6axis" in d:
        lines.append(
            f"  composite (6-axis, advisory): {d['composite_6axis']['score']}/100  weights={d['composite_6axis']['weights']}"
        )
    lines.append(f"  status: {d['status']}")
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
