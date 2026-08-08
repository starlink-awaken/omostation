#!/usr/bin/env python3
"""Governance Scanner — 异步深度扫描引擎.

独立于 agent tick 的周期性全面扫描, 产出 alerts + metrics.
与 agent-tick-daemon 互补:
  - tick = 快速心跳 (5min, 每个 agent 自检)
  - scan = 深度审计 (30min, 跨 agent 跨维度综合分析)

扫描维度:
  1. Debt/Gap 台账健康度 (数量趋势, 过期项, 高风险项)
  2. Agent 心跳趋势 (从 heartbeat jsonl 分析 success_rate, action 分布)
  3. MOS 记忆健康度 (calibration 积累率, skill/experience 增长)
  4. A2A 消息积压 (未处理的 governor dispatch)
  5. Autonomy 评分趋势 (5维度变化)
  6. Journey 卡点 (human_hold 时长)

产出:
  - alerts.jsonl  (发现的问题, 按严重度分级)
  - metrics-store.jsonl (量化指标快照)

Usage:
  python3 bin/ssot/governance-scanner.py              # 跑一次扫描
  python3 bin/ssot/governance-scanner.py --watch       # 持续运行 (30min间隔)
  python3 bin/ssot/governance-scanner.py --json        # JSON输出
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl

ALERTS_FILE = ROOT / ".omo" / "_log" / "alerts.jsonl"
METRICS_FILE = ROOT / ".omo" / "_log" / "metrics-store.jsonl"
HEARTBEAT_FILE = ROOT / ".omo" / "state" / "agent-tick-daemon.jsonl"
A2A_FILE = ROOT / ".omo" / "state" / "a2a-messages.jsonl"
DEBT_DIR = ROOT / ".omo" / "debt" / "items"
GAP_DIR = ROOT / ".omo" / "debt" / "gap-items"

OMO_SRC = ROOT / "projects" / "omo" / "src"


def _ts() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items


def _emit_alert(severity: str, category: str, message: str, details: dict | None = None) -> None:
    """写一条 alert 到 alerts.jsonl."""
    alert = {
        "ts": _ts(),
        "severity": severity,  # critical / high / medium / low
        "category": category,  # debt / agent_health / mos / a2a / autonomy / journey
        "message": message,
        "details": details or {},
    }
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(ALERTS_FILE, alert)


def _emit_metric(name: str, value: float, tags: dict | None = None) -> None:
    """写一条 metric 到 metrics-store.jsonl."""
    metric = {
        "ts": _ts(),
        "metric": name,
        "value": value,
        "tags": tags or {},
    }
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(METRICS_FILE, metric)


def scan_debt() -> dict[str, Any]:
    """扫描 debt/gap 台账健康度."""
    debt_files = list(DEBT_DIR.glob("*.yaml")) if DEBT_DIR.exists() else []
    gap_files = list(GAP_DIR.glob("*.yaml")) if GAP_DIR.exists() else []
    total = len(debt_files) + len(gap_files)

    _emit_metric("debt.total_count", total)
    _emit_metric("debt.items_count", len(debt_files))
    _emit_metric("debt.gap_count", len(gap_files))

    if total > 50:
        _emit_alert("high", "debt", f"Debt volume critical: {total} items (debt={len(debt_files)}, gap={len(gap_files)})")

    return {"debt_items": len(debt_files), "gap_items": len(gap_files), "total": total}


def scan_agent_heartbeat() -> dict[str, Any]:
    """从心跳 jsonl 分析 agent tick 趋势."""
    beats = _read_jsonl(HEARTBEAT_FILE)
    if not beats:
        _emit_alert("medium", "agent_health", "No agent heartbeat recorded — daemon may not be running")
        return {"total_ticks": 0}

    recent = beats[-20:]  # 最近20次tick
    total = len(beats)
    ok_rate = sum(b.get("ok_count", 0) for b in recent) / max(
        sum(b.get("agent_count", 1) for b in recent), 1
    )
    action_dist = Counter()
    for b in recent:
        for a in b.get("actions", []):
            action_dist[a] += 1

    _emit_metric("agent.tick_total", total)
    _emit_metric("agent.ok_rate_recent", round(ok_rate, 3))
    _emit_metric("agent.non_noop_recent", sum(v for k, v in action_dist.items() if k != "noop"))

    if ok_rate < 0.8:
        _emit_alert("high", "agent_health", f"Agent success rate degraded: {ok_rate:.1%}")

    return {
        "total_ticks": total,
        "recent_ok_rate": round(ok_rate, 3),
        "action_distribution": dict(action_dist.most_common(5)),
    }


def scan_mos_health() -> dict[str, Any]:
    """扫描 MOS 记忆健康度."""
    try:
        if str(OMO_SRC) not in sys.path:
            sys.path.insert(0, str(OMO_SRC))
        from omo.omo_belief import MOSBeliefManager

        manager = MOSBeliefManager(root=ROOT)
        state = manager._load_state()
        calibrations = state.get("capability_calibrations", [])
        skills = state.get("agent_skills", [])
        experiences = state.get("agent_experiences", [])
        beliefs = state.get("beliefs", [])
        decisions = state.get("decision_outcomes", [])

        _emit_metric("mos.calibrations", len(calibrations))
        _emit_metric("mos.skills", len(skills))
        _emit_metric("mos.experiences", len(experiences))
        _emit_metric("mos.beliefs", len(beliefs))
        _emit_metric("mos.decisions", len(decisions))

        if len(calibrations) < 5:
            _emit_alert(
                "medium", "mos",
                f"MOS calibrations low ({len(calibrations)}) — learning loop may not be active",
            )

        return {
            "calibrations": len(calibrations),
            "skills": len(skills),
            "experiences": len(experiences),
            "beliefs": len(beliefs),
            "decisions": len(decisions),
        }
    except Exception as e:
        _emit_alert("high", "mos", f"MOS health check failed: {e}")
        return {"error": str(e)}


def scan_a2a_backlog() -> dict[str, Any]:
    """扫描 A2A 消息积压."""
    messages = _read_jsonl(A2A_FILE)
    if not messages:
        _emit_metric("a2a.total_messages", 0)
        return {"total": 0}

    # 统计最近的未处理消息 (没有对应 reply 的 task 消息)
    recent = messages[-50:]
    task_msgs = [m for m in recent if m.get("type") == "task"]
    reply_msgs = {m.get("in_reply_to") for m in recent if m.get("type") == "reply"}
    unresolved = [m for m in task_msgs if m.get("ts") not in reply_msgs]

    _emit_metric("a2a.total_messages", len(messages))
    _emit_metric("a2a.unresolved_tasks", len(unresolved))

    if len(unresolved) > 10:
        _emit_alert("medium", "a2a", f"A2A backlog growing: {len(unresolved)} unresolved task messages")

    return {"total": len(messages), "unresolved": len(unresolved)}


def scan_autonomy() -> dict[str, Any]:
    """扫描自主度评分趋势."""
    try:
        if str(OMO_SRC) not in sys.path:
            sys.path.insert(0, str(OMO_SRC))
        from omo.omo_agent_host import AutonomyAssessmentAgent

        agent = AutonomyAssessmentAgent()
        result = agent.tick()
        details = result.get("details", {})
        score = details.get("autonomy_score", 0)
        dims = details.get("dimensions", {})

        _emit_metric("autonomy.score", score)
        for dim, val in dims.items():
            _emit_metric(f"autonomy.{dim}", val)

        if score < 40:
            _emit_alert("high", "autonomy", f"Autonomy score critical: {score}/100 — system not self-sustaining")

        return {"score": score, "dimensions": dims}
    except Exception as e:
        return {"error": str(e)}


def scan_journeys() -> dict[str, Any]:
    """扫描 journey 卡点."""
    states_dir = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "journey-states"
    if not states_dir.exists():
        return {"journey_dirs": 0}

    human_holds = 0
    journey_count = 0
    for jd in states_dir.iterdir():
        if not jd.is_dir():
            continue
        journey_count += 1
        for rf in jd.glob("*.jsonl"):
            try:
                lines = rf.read_text(encoding="utf-8").strip().split("\n")
                if lines and lines[-1].strip():
                    last = json.loads(lines[-1])
                    if last.get("status") in ("human_hold", "awaiting_human"):
                        human_holds += 1
            except Exception:
                continue

    _emit_metric("journey.total_dirs", journey_count)
    _emit_metric("journey.human_holds", human_holds)

    if human_holds > 0:
        _emit_alert("medium", "journey", f"{human_holds} journey runs awaiting human action")

    return {"journey_dirs": journey_count, "human_holds": human_holds}


def run_scan() -> dict[str, Any]:
    """执行全面扫描, 返回汇总结果."""
    ts = _ts()
    results = {
        "timestamp": ts,
        "debt": scan_debt(),
        "agent_health": scan_agent_heartbeat(),
        "mos": scan_mos_health(),
        "a2a": scan_a2a_backlog(),
        "autonomy": scan_autonomy(),
        "journeys": scan_journeys(),
    }
    _emit_metric("scan.completed", 1, {"ts": ts})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true", help="continuous mode (30min interval)")
    mode.add_argument("--once", action="store_true", help="single scan (default)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--interval", type=int, default=1800, help="watch interval seconds")
    args = parser.parse_args(argv)

    if args.watch:
        print(f"Governance Scanner running (interval={args.interval}s). Ctrl+C to stop.", flush=True)
        import time

        try:
            while True:
                result = run_scan()
                print(f"  [{_ts()[:19]}] scan done — debt={result['debt']['total']}, "
                      f"autonomy={result['autonomy'].get('score', '?')}", flush=True)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nScanner stopped.")
    else:
        result = run_scan()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"=== Governance Scan {_ts()} ===")
            print(f"  Debt:     {result['debt']['total']} items ({result['debt']['debt_items']} debt + {result['debt']['gap_items']} gap)")
            ah = result['agent_health']
            print(f"  Agents:   {ah.get('total_ticks', 0)} ticks, ok_rate={ah.get('recent_ok_rate', '?')}")
            print(f"  MOS:      calib={result['mos'].get('calibrations', '?')}, skills={result['mos'].get('skills', '?')}, beliefs={result['mos'].get('beliefs', '?')}")
            print(f"  A2A:      {result['a2a']['total']} messages, {result['a2a']['unresolved']} unresolved")
            print(f"  Autonomy: {result['autonomy'].get('score', '?')}/100")
            print(f"  Journeys: {result['journeys'].get('human_holds', 0)} human holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
