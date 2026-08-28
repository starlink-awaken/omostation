#!/usr/bin/env python3
"""rules-lifecycle — L4 约束层规则生命周期治理 (ADR-0431 D2, 2026-08-28).

Lehman 定律 7 (质量递减) 工程化: 规则不主动评审必然腐化。
本工具扫描 governance-checks.yaml 的规则生命周期字段, 产出减法候选报告。

三层输出:
  expired  — review_before 已过 → 减法候选 (需人工 keep/kill 决定)
  due-soon — 30 天内到期 → 提醒续期或纳入减法
  healthy  — 未到期

规则字段契约 (ADR-0431 D2):
  added_at:       上线日期 (缺失视为 legacy, 按 2026-08-28 起算 90 天)
  review_before:  下次评审截止 (过期进减法候选)
  justification:  存在理由 (减法评审依据)

用法:
  python3 rules-lifecycle.py              # 人读报告
  python3 rules-lifecycle.py --json       # 机读 (cron/MCP 消费)
  python3 rules-lifecycle.py --stale-days N  # legacy 规则的假想到期天数 (默认 90)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CHECKS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
LEGACY_EPOCH = date(2026, 8, 28)  # 本工具上线日; 无 added_at 的规则从此起算
DEFAULT_STALE_DAYS = 90
DUE_SOON_DAYS = 30


def _parse_date(value: object) -> date | None:
    s = str(value or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def load_rules() -> list[dict]:
    import yaml

    data = yaml.safe_load(CHECKS_YAML.read_text(encoding="utf-8")) or {}
    # 规则在 gac.rules (governance-checks.yaml schema: rules 嵌在 gac 段)
    gac = data.get("gac") or {}
    rules = gac.get("rules")
    if isinstance(rules, list):
        return rules
    # 顶层 rules 兼容 (schema 演进预留)
    top = data.get("rules")
    return [r for r in (top or {}).values() if isinstance(r, dict)] if isinstance(top, dict) else []


def classify(stale_days: int) -> dict[str, list[dict]]:
    rules = load_rules()
    today = date.today()
    out: dict[str, list[dict]] = {"expired": [], "due-soon": [], "healthy": [], "legacy": []}
    for rule in rules:
        rid = str(rule.get("id") or "?")
        review = _parse_date(rule.get("review_before"))
        if review is None:
            added = _parse_date(rule.get("added_at"))
            base = added or LEGACY_EPOCH
            review = date.fromordinal(base.toordinal() + (stale_days if added else DEFAULT_STALE_DAYS))
            out["legacy"].append(rid)  # 只记 id (标记, 不重复入桶)
        entry = {**rule, "_review_before": review.isoformat(), "_days_left": (review - today).days}
        bucket = "expired" if entry["_days_left"] < 0 else ("due-soon" if entry["_days_left"] <= DUE_SOON_DAYS else "healthy")
        out[bucket].append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="机读输出")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS, help="legacy 规则假想周期")
    args = parser.parse_args(argv)

    result = classify(args.stale_days)
    counts = {k: len(v) for k, v in result.items() if k != "legacy"}

    if args.json:
        print(json.dumps({"generated_at": datetime.utcnow().isoformat() + "Z", "counts": {**counts, "legacy": len(result["legacy"])}, **result}, ensure_ascii=False, indent=1, default=str))
        return 0

    print("═══ 规则生命周期报告 (ADR-0431 D2) ═══")
    total = len(load_rules())
    print(f"  总规则: {total} | 过期: {counts['expired']} | 即将到期: {counts['due-soon']} | 健康: {counts['healthy']} | 其中无日期 legacy: {len(result['legacy'])}")
    if result["expired"]:
        print("\n🔴 过期 — 减法候选 (keep 需续 review_before, kill 归档):")
        for r in result["expired"]:
            print(f"  {r['id']}  过期 {-r['_days_left']} 天  理由: {str(r.get('justification', '(无)'))[:60]}")
    if result["due-soon"]:
        print("\n🟡 30 天内到期:")
        for r in result["due-soon"]:
            print(f"  {r['id']}  剩 {r['_days_left']} 天")
    # 退出码: 有过期=1 (cron 可感知), 无过期=0
    return 1 if result["expired"] else 0


if __name__ == "__main__":
    sys.exit(main())
