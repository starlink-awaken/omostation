#!/usr/bin/env python3
"""gac-coverage-lint — 声明即执行覆盖率 (P3 治根, ADR-0227 原则2 衍生).

治 GaC 192 rule 声明面膨胀执行面休眠 (decl-exec-gap): 声明的 executor 有没有真跑.
扫 governance-checks.yaml rule, 对**有静态 evidence 的 executor**检查 evidence 新鲜度.

executor → 标准 evidence 映射 (executor 机制的标准产出, 非 ad-hoc):
  omo_audit      → .omo/_knowledge/governance-history.jsonl (omo CLI 审计落盘)
  evidence_smoke → .omo/_delivery/evidence-smoke/ (evidence-smoke 多源校验)
  foundry_cron   → runtime/cron/operating-rhythm-daily.log (foundry cron daily)
无静态 evidence (事件/CI 驱动, 跳过): ci_gate/hook_pre_edit/mcp_tool/gac_local_gate/radar_cron

用法:
  python3 bin/gac/gac-coverage-lint.py           # 检测休眠 executor, 有则返回 1
  python3 bin/gac/gac-coverage-lint.py --json    # JSON 输出

退出码: 0 = 全静态 evidence executor 活, 1 = 有休眠
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# executor → 标准 evidence 路径 (executor 机制产出, 声明面驱动非 ad-hoc)
EXECUTOR_EVIDENCE = {
    "omo_audit": ".omo/_knowledge/governance-history.jsonl",
    "evidence_smoke": ".omo/_delivery/evidence-smoke/",
    "foundry_cron": "runtime/cron/operating-rhythm-daily.log",
}
MAX_STALE_HOURS = 48  # evidence 过期阈值 (omo_audit/foundry daily, evidence_smoke gha daily)

# 无静态 evidence (事件/CI/MCP 驱动) - 不检查 (无标准 evidence 文件)
NO_STATIC_EVIDENCE = {"ci_gate", "hook_pre_edit", "hook_post", "mcp_tool", "gac_local_gate", "radar_cron"}


def _evidence_age_hours(path: Path) -> float | None:
    """evidence 文件/目录最新 mtime 距今小时数. None = 不存在."""
    if not path.exists():
        return None
    if path.is_dir():
        files = [p for p in path.glob("*") if p.is_file()]
        if not files:
            return None
        latest = max(p.stat().st_mtime for p in files)
    else:
        latest = path.stat().st_mtime
    return (datetime.now(timezone.utc).timestamp() - latest) / 3600


def main() -> int:
    as_json = "--json" in sys.argv
    if not REGISTRY.is_file():
        print(json.dumps({"error": "governance-checks.yaml missing"}) if as_json else "❌ registry missing")
        return 1

    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    rules = docs[-1].get("gac", {}).get("rules", []) if docs else []

    # executor evidence 健康
    evidence_health = {}
    for executor, rel in EXECUTOR_EVIDENCE.items():
        age = _evidence_age_hours(WORKSPACE / rel)
        evidence_health[executor] = {
            "path": rel,
            "age_hours": round(age, 1) if age is not None else None,
            "alive": age is not None and age <= MAX_STALE_HOURS,
        }

    # rule executor 覆盖统计
    executor_rule_count: dict[str, int] = {}
    for r in rules:
        for e in r.get("executor", []):
            executor_rule_count[e] = executor_rule_count.get(e, 0) + 1

    # 用休眠 executor 的 rule (有静态 evidence 但休眠)
    rules_with_stale = []
    for r in rules:
        for e in r.get("executor", []):
            if e in evidence_health and not evidence_health[e]["alive"]:
                rules_with_stale.append({"rule": r.get("id", "?"), "executor": e})
                break

    report = {
        "rules_total": len(rules),
        "evidence_health": evidence_health,
        "executor_rule_count": dict(sorted(executor_rule_count.items(), key=lambda x: -x[1])),
        "rules_with_stale_executor": rules_with_stale,
        "ok": len(rules_with_stale) == 0,
        "no_static_evidence_skipped": sorted(NO_STATIC_EVIDENCE),
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("═══ 声明即执行覆盖率 (P3: 治声明面膨胀执行面休眠) ═══")
    print(f"▶ 规则总数: {report['rules_total']}")
    print("\nexecutor evidence 健康:")
    for e, h in evidence_health.items():
        status = "✅活" if h["alive"] else "💀休眠"
        age = f"{h['age_hours']}h" if h['age_hours'] is not None else "缺失"
        print(f"  {status} {e} (规则={executor_rule_count.get(e, 0)}): {age} ≤{MAX_STALE_HOURS}h  {h['path']}")
    print(f"\n无静态 evidence (跳过): {', '.join(sorted(NO_STATIC_EVIDENCE))}")
    if rules_with_stale:
        print(f"\n❌ 用休眠 executor 的规则 ({len(rules_with_stale)}):")
        for r in rules_with_stale[:5]:
            print(f"  - {r['rule']} (executor={r['executor']})")
    print(f"\n═══ 总体: {'✅ 全静态 evidence executor 活' if report['ok'] else '❌ 有休眠 executor'} ═══")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
