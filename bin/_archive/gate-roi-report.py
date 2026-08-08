#!/usr/bin/env python3
"""Gate ROI report (ADR-0389, M5/C3): 季度治理价值报告.

目标: 回答"每个 gate 抓了多少、省了多少时间、下轮砍谁" —
     用治理历史数据量化 gate 价值, 为减法决策提供依据.

数据源: `.omo/_knowledge/governance-history.jsonl` (每次 audit 的 per-check
severity 快照). severity ∈ {ok, warn, error, critical}.

指标:
  - fires / fire_rate: 非 ok 的事件占比 (gate 活跃度)
  - fail_fires: error+critical 次数 (真拦截: CI 阻断级)
  - trend: 近 30 天 fire_rate vs 全历史 fire_rate (↑活跃 / ↓衰减 / →持平)
  - est_hours: 估算人工处理时间 = warn_fires×warn_min + fail_fires×fail_min
    (cost_model 提供每 gate 的分钟数, 均为经验估计, 非精确计量)

决策建议 (减法导向):
  - RETIRE   0 fires 且样本 ≥ threshold → 装饰性 gate, 删除
  - PRUNE    30d fire_rate < 全历史 50% 且 < 10% → 衰减, 考虑降级/合并
  - KEEP     活跃且有 fail 拦截 → 保留 (真价值)
  - NOISY    活跃但 warn-only 且 warn ≥ 30 → 降级 warn→info 或聚合
  - NEW      样本不足 (< 20), 待观察

用法:
  python3 bin/gac/gate-roi-report.py              # 人类表格 + 建议
  python3 bin/gac/gate-roi-report.py --json       # 结构化 JSON
  python3 bin/gac/gate-roi-report.py --markdown   # markdown 报告 (季度报告用)
  python3 bin/gac/gate-roi-report.py --since 30d  # 窗口过滤
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY = Path(".omo/_knowledge/governance-history.jsonl")

# 每 gate 的人工处理成本估计 (分钟). warn = 提醒后人工确认/修复时间,
# fail = CI 阻断后的紧急处理时间. 经验值, 可按季校准.
COST_MODEL: dict[str, dict[str, float]] = {
    "agora health": {"warn_min": 15, "fail_min": 60},
    "ruff lint": {"warn_min": 8, "fail_min": 30},
    "test coverage": {"warn_min": 15, "fail_min": 45},
    "debt integrity": {"warn_min": 20, "fail_min": 60},
    "task consistency": {"warn_min": 10, "fail_min": 30},
    "adr links": {"warn_min": 5, "fail_min": 20},
    "doc lifecycle": {"warn_min": 10, "fail_min": 30},
}
DEFAULT_WARN_MIN = 10
DEFAULT_FAIL_MIN = 30

RETIRE_SAMPLE_THRESHOLD = 20
TREND_WINDOW = 30  # days


def load_events(history: Path, since: str | None = None) -> list[dict]:
    if not history.exists():
        return []
    cutoff = None
    if since:
        unit = since[-1]
        n = int(since[:-1])
        now = datetime.now(timezone.utc)
        cutoff = now - (timedelta(days=n) if unit == "d" else timedelta(hours=n))
    events = []
    for line in history.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = e.get("timestamp")
        if cutoff and ts:
            try:
                if datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                pass
        events.append(e)
    return events


def build_report(events: list[dict], trend_days: int = TREND_WINDOW) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=trend_days)).isoformat()

    by_check: dict[str, dict] = {}
    for e in events:
        ts = e.get("timestamp", "")
        is_recent = bool(ts and ts >= cutoff)
        for c in (e.get("checks") or []):
            name = c.get("name", "?")
            sev = c.get("severity", "ok")
            st = by_check.setdefault(
                name,
                {
                    "name": name,
                    "category": c.get("category", ""),
                    "total": 0,
                    "recent_total": 0,
                    "fires": 0,
                    "recent_fires": 0,
                    "fail_fires": 0,
                    "recent_fail_fires": 0,
                    "severity_counts": Counter(),
                },
            )
            st["total"] += 1
            st["severity_counts"][sev] += 1
            if sev != "ok":
                st["fires"] += 1
                if sev in ("error", "critical"):
                    st["fail_fires"] += 1
            if is_recent:
                st["recent_total"] += 1
                if sev != "ok":
                    st["recent_fires"] += 1
                    if sev in ("error", "critical"):
                        st["recent_fail_fires"] += 1

    out = []
    for st in by_check.values():
        name = st["name"]
        total = st["total"]
        fires = st["fires"]
        recent_total = st["recent_total"]
        recent_fires = st["recent_fires"]
        all_rate = fires / total if total else 0
        recent_rate = recent_fires / recent_total if recent_total else 0

        cost = COST_MODEL.get(name, {})
        warn_min = cost.get("warn_min", DEFAULT_WARN_MIN)
        fail_min = cost.get("fail_min", DEFAULT_FAIL_MIN)
        warn_fires = fires - st["fail_fires"]
        est_hours = round((warn_fires * warn_min + st["fail_fires"] * fail_min) / 60, 1)

        # trend: 近 30d vs 全历史
        if recent_total >= 5:
            if recent_rate > all_rate * 1.5 and recent_rate >= 0.05:
                trend = "up"
            elif recent_rate < all_rate * 0.5 or recent_rate == 0:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "flat"  # 样本不足, 不判趋势

        # 决策建议
        if total >= RETIRE_SAMPLE_THRESHOLD and fires == 0:
            verdict = "RETIRE"
        elif st["fail_fires"] > 0 and recent_total >= 5 and recent_rate >= 0.05:
            verdict = "KEEP"
        elif warn_fires >= 30 and recent_rate >= 0.1:
            verdict = "NOISY"
        elif recent_total >= 5 and recent_rate < all_rate * 0.5 and all_rate >= 0.05:
            verdict = "PRUNE"
        elif total < RETIRE_SAMPLE_THRESHOLD:
            verdict = "NEW"
        else:
            verdict = "KEEP"

        out.append(
            {
                **st,
                "severity_counts": dict(st["severity_counts"]),
                "fire_rate_all": round(all_rate, 4),
                "fire_rate_30d": round(recent_rate, 4),
                "trend": trend,
                "est_hours_saved": est_hours,
                "verdict": verdict,
            }
        )
    out.sort(key=lambda x: (-x["est_hours_saved"], -x["fire_rate_all"]))
    return {
        "events_loaded": len(events),
        "trend_window_days": trend_days,
        "total_est_hours_saved": round(sum(x["est_hours_saved"] for x in out), 1),
        "gates": out,
    }


def render_markdown(report: dict) -> str:
    L = []
    L.append("# Gate ROI 季度治理价值报告")
    L.append("")
    L.append(f"> 数据源: governance-history.jsonl | 事件数: {report['events_loaded']} | "
             f"趋势窗口: 近 {report['trend_window_days']} 天 | "
             f"估算总节省: **{report['total_est_hours_saved']} 小时**")
    L.append("")
    L.append("## 各 Gate 价值表")
    L.append("")
    L.append("| gate | verdict | total | fires | fail | rate(30d) | trend | est_hours |")
    L.append("|------|---------|-------|-------|------|-----------|-------|-----------|")
    for g in report["gates"]:
        L.append(
            f"| {g['name']} | {g['verdict']} | {g['total']} | {g['fires']} | "
            f"{g['fail_fires']} | {g['fire_rate_30d']:.0%} | {g['trend']} | {g['est_hours_saved']} |"
        )
    L.append("")
    L.append("## 减法建议 (下轮候选)")
    L.append("")
    for g in report["gates"]:
        if g["verdict"] == "RETIRE":
            L.append(f"- **RETIRE {g['name']}**: {g['total']} 样本 0 次拦截 → 装饰性 gate, 删除或并入其它 gate")
        elif g["verdict"] == "NOISY":
            L.append(f"- **NOISY {g['name']}**: {g['fires']} warn / 0 fail, 30d fire {g['fire_rate_30d']:.0%} → 降级 warn→info 或聚合去噪")
        elif g["verdict"] == "PRUNE":
            L.append(f"- **PRUNE {g['name']}**: 30d fire {g['fire_rate_30d']:.0%} < 全期 {g['fire_rate_all']:.0%} → 衰减, 降频或合并")
        elif g["verdict"] == "KEEP" and g["fail_fires"] > 0:
            L.append(f"- **KEEP {g['name']}**: {g['fail_fires']} 次 fail 拦截 (真价值) → 保留并纳入决策看板")
    L.append("")
    L.append("> 注: est_hours 为经验估计 (warn/fail 人工处理分钟数), 非精确计量, 用于相对排序。")
    return "\n".join(L)


def print_table(report: dict) -> None:
    print(f"loaded {report['events_loaded']} events; 估算总节省 {report['total_est_hours_saved']}h "
          f"(近{report['trend_window_days']}d 窗口)\n")
    print(f"{'gate':22} {'verdict':7} {'n':>4} {'fires':>5} {'fail':>4} {'rate30d':>7} {'trend':>5} {'est_h':>5}")
    print("-" * 72)
    for g in report["gates"]:
        print(
            f"{g['name']:22} {g['verdict']:7} {g['total']:>4} {g['fires']:>5} {g['fail_fires']:>4} "
            f"{g['fire_rate_30d']:>7.0%} {g['trend']:>5} {g['est_hours_saved']:>5}"
        )
    # 建议
    recs = [g for g in report["gates"] if g["verdict"] in ("RETIRE", "NOISY", "PRUNE", "KEEP")]
    if recs:
        print("\n减法建议 (下轮候选):")
        for g in recs:
            if g["verdict"] == "RETIRE":
                print(f"  - RETIRE {g['name']}: {g['total']} 样本 0 拦截 → 删除")
            elif g["verdict"] == "NOISY":
                print(f"  - NOISY  {g['name']}: {g['fires']} warn/0 fail → 降级去噪")
            elif g["verdict"] == "PRUNE":
                print(f"  - PRUNE  {g['name']}: 30d {g['fire_rate_30d']:.0%} < 全期 {g['fire_rate_all']:.0%} → 降频/合并")
            elif g["verdict"] == "KEEP" and g["fail_fires"] > 0:
                print(f"  - KEEP   {g['name']}: {g['fail_fires']} fail 拦截 → 保留")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--markdown", action="store_true", help="emit markdown report")
    parser.add_argument("--since", type=str, default="", help="window: 30d/24h (default: all-time)")
    parser.add_argument("--trend-days", type=int, default=TREND_WINDOW, help="trend window days")
    args = parser.parse_args()

    events = load_events(HISTORY, since=args.since)
    report = build_report(events, trend_days=args.trend_days)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(render_markdown(report))
    else:
        print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
