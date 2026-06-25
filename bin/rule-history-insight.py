#!/usr/bin/env python3
"""P89 R1: X2 rule 历史与命中情况洞察工具.

读取 .omo/_truth/x2-freshness-rules.yaml + .omo/_control/evolution/drift/*.json,
输出每条 rule 的:
- target 路径最新修改时间
- 是否在 threshold_days 内 (fresh / stale)
- 关联 drift reports 提及次数 (按 path/keyword)
- 治理建议 (从未修改 + 已超期 → 触发 X2 freshness)

使用:
  python3 bin/rule-history-insight.py
  python3 bin/rule-history-insight.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rules: list[dict] = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            rules.extend(doc.get("rules", []))
    return rules


def parse_drift_files(drift_dir: Path) -> list[dict]:
    """读取 drift 报告."""
    reports: list[dict] = []
    if not drift_dir.exists():
        return reports
    for f in sorted(drift_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = f.name
            reports.append(data)
        except Exception:
            continue
    return reports


def target_age_days(target: str, root: Path) -> tuple[int | None, datetime | None]:
    """返回 target 路径距今的天数和最后修改时间. 支持 glob 模式."""
    full = root / target.lstrip("/")
    if full.exists():
        try:
            mtime = full.stat().st_mtime
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            days = (datetime.now(tz=timezone.utc) - dt).days
            return (days, dt)
        except Exception:
            return (None, None)
    # glob 模式: 找最近修改的文件
    matches = list(root.glob(target))
    if not matches:
        return (None, None)
    latest = max((m.stat().st_mtime for m in matches if m.exists()), default=None)
    if latest is None:
        return (None, None)
    dt = datetime.fromtimestamp(latest, tz=timezone.utc)
    days = (datetime.now(tz=timezone.utc) - dt).days
    return (days, dt)


def correlate(rules: list[dict], drift_reports: list[dict], root: Path, now: datetime) -> dict:
    """分析每条 X2 rule 的状态 + drift 关联."""
    now = now or datetime.now(tz=timezone.utc)
    rule_analyses = []

    # 全 drift 提及计数 (按关键词匹配)
    drift_text = " ".join(
        json.dumps(r, ensure_ascii=False) for r in drift_reports
    )

    for rule in rules:
        rid = rule.get("rule_id", "")
        target = rule.get("target", "")
        threshold = rule.get("freshness", {}).get("threshold_days", 30)
        action = rule.get("freshness", {}).get("action", "warn")
        archived = rule.get("archived", False)

        days, mtime = target_age_days(target, root)

        # 关键词提取 (target 去掉 glob 段)
        keywords = [s for s in target.replace("*", "").split("/") if s and len(s) > 3]
        # 排除公共词
        keywords = [k for k in keywords if k not in ("src", "lib", "docs", "test", "tests")]

        # drift 关键词命中次数
        drift_hits = sum(drift_text.count(k) for k in keywords)

        # 状态判断
        if days is None:
            status = "missing"  # target 不存在
        elif archived:
            status = "archived"
        elif days > threshold:
            status = "stale"  # 触发 freshness
        else:
            status = "fresh"

        rule_analyses.append({
            "rule_id": rid,
            "target": target,
            "threshold_days": threshold,
            "action": action,
            "age_days": days,
            "mtime": mtime.isoformat() if mtime else None,
            "status": status,
            "drift_keyword_hits": drift_hits,
        })

    # 状态统计
    by_status = Counter(a["status"] for a in rule_analyses)
    stale_rules = [a for a in rule_analyses if a["status"] == "stale"]
    missing_rules = [a for a in rule_analyses if a["status"] == "missing"]

    return {
        "total_rules": len(rule_analyses),
        "by_status": dict(by_status),
        "stale_count": len(stale_rules),
        "missing_count": len(missing_rules),
        "rules": rule_analyses,
        "drift_reports_analyzed": len(drift_reports),
        "checked_at": now.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P89: X2 rule history insight")
    parser.add_argument("--rules", default=".omo/_truth/x2-freshness-rules.yaml")
    parser.add_argument("--drift-dir", default=".omo/_control/evolution/drift")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    rules = load_rules(root / args.rules)
    drift = parse_drift_files(root / args.drift_dir)
    now = datetime.now(tz=timezone.utc)
    result = correlate(rules, drift, root, now)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P89 X2 rule status insight")
    print("=" * 60)
    print(f"📋 Rules: {result['total_rules']}")
    print(f"📁 Drift 报告分析: {result['drift_reports_analyzed']}")
    print(f"📅 检查时间: {now.isoformat()[:19]}")
    print()
    print("状态分布:")
    for status, count in result["by_status"].items():
        icon = {"fresh": "🟢", "stale": "⚠️", "missing": "❌", "archived": "📦"}.get(status, "?")
        print(f"  {icon} {status:<10s} {count:>3d}")
    print()

    # 详细列表
    print("Rule 详情:")
    print(f"  {'rule_id':<40s} {'status':<10s} {'age':>5s} {'threshold':>9s} {'drift':>5s}")
    for a in result["rules"]:
        age = f"{a['age_days']}d" if a["age_days"] is not None else "?"
        print(f"  {a['rule_id']:<40s} {a['status']:<10s} {age:>5s} "
              f"{a['threshold_days']:>8d}d {a['drift_keyword_hits']:>5d}")

    # 建议
    print()
    if result["stale_count"] > 0:
        print(f"⚠️  {result['stale_count']} rules 已超期 (stale), 触发对应 action")
    if result["missing_count"] > 0:
        print(f"❌  {result['missing_count']} rules target 不存在, 需修复")
    if result["stale_count"] == 0 and result["missing_count"] == 0:
        print("🎉 所有 rules 状态 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
