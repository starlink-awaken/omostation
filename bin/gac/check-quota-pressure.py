#!/usr/bin/env python3
"""check-quota-pressure.py — 治理配额压力检查.

监控治理规则/脚本配额使用率:
  1. 统计 governance-checks.yaml 活跃规则数
  2. 统计 bin/gac/ 脚本数
  3. 计算各维度剩余空间
  4. 任一维度剩余 < 5 → exit 1
  5. 总规则 > 80% max (120) → 告警

rule_id: CR-X4-QUOTA-PRESSURE

用法:
    python3 bin/gac/check-quota-pressure.py        # 全量扫
    python3 bin/gac/check-quota-pressure.py --json  # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CHECKS_YAML = REPO / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
GAC_DIR = REPO / "bin" / "gac"

# freeze limits from plan context
DIMENSION_LIMITS = {
    "X1": 38,
    "X2": 35,
    "X3": 38,
    "X4": 55,
}
MAX_RULES = 150
SCRIPT_BASELINE = 556


def count_active_rules() -> dict[str, int]:
    """Count active rules per dimension from governance-checks.yaml."""
    if not CHECKS_YAML.exists():
        return {}
    try:
        data = yaml.safe_load(CHECKS_YAML.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    rules = data.get("rules") or data.get("checkers") or []
    counts: dict[str, int] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        dim = rule.get("dimension", "unknown")
        lifecycle = rule.get("lifecycle", "active")
        if lifecycle == "active" or rule.get("enabled", True):
            counts[dim] = counts.get(dim, 0) + 1
    return counts


def count_gac_scripts() -> int:
    """Count scripts in bin/gac/."""
    if not GAC_DIR.exists():
        return 0
    return sum(1 for f in GAC_DIR.iterdir() if f.suffix == ".py")


def main() -> int:
    parser = argparse.ArgumentParser(description="治理配额压力检查")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    rule_counts = count_active_rules()
    total_rules = sum(rule_counts.values())
    script_count = count_gac_scripts()

    dimension_pressure: dict[str, dict] = {}
    alerts: list[str] = []
    failures: list[str] = []

    for dim, limit in DIMENSION_LIMITS.items():
        used = rule_counts.get(dim, 0)
        headroom = limit - used
        pct = (used / limit * 100) if limit > 0 else 0
        dimension_pressure[dim] = {
            "used": used,
            "limit": limit,
            "headroom": headroom,
            "utilization_pct": round(pct, 1),
        }
        if headroom < 5:
            failures.append(f"{dim}: headroom={headroom} < 5")
        elif headroom < 10:
            alerts.append(f"{dim}: headroom={headroom} < 10")

    rule_pct = (total_rules / MAX_RULES * 100) if MAX_RULES > 0 else 0
    if total_rules > MAX_RULES * 0.8:
        alerts.append(f"Total rules {total_rules}/{MAX_RULES} ({rule_pct:.0f}%) > 80%")
    if total_rules > MAX_RULES:
        failures.append(f"Total rules {total_rules} exceeds max {MAX_RULES}")

    result = {
        "total_rules": total_rules,
        "max_rules": MAX_RULES,
        "rule_utilization_pct": round(rule_pct, 1),
        "script_count": script_count,
        "script_baseline": SCRIPT_BASELINE,
        "dimension_pressure": dimension_pressure,
        "alerts": alerts,
        "failures": failures,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== 治理配额压力检查 ===\n")
        print(f"规则: {total_rules}/{MAX_RULES} ({rule_pct:.0f}%)")
        print(f"脚本: {script_count} (baseline: {SCRIPT_BASELINE})")
        print()
        for dim, p in dimension_pressure.items():
            status = "OK" if p["headroom"] >= 10 else "WARN" if p["headroom"] >= 5 else "FAIL"
            print(f"  {dim}: {p['used']}/{p['limit']} (headroom: {p['headroom']}) [{status}]")

        if alerts:
            print(f"\n告警 ({len(alerts)}):")
            for a in alerts:
                print(f"  {a}")
        if failures:
            print(f"\n失败 ({len(failures)}):")
            for f in failures:
                print(f"  {f}")

        print(f"\nTotal: {len(failures)} failures, {len(alerts)} alerts")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
