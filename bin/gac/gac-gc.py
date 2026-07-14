#!/usr/bin/env python3
"""GaC 治理即代码 — lifecycle gc (ADR-0106, 机制 6, c2g gc 原语).

清理过时规则 (lifecycle: deprecated → removed):

  - 扫描 governance-checks.yaml::gac.rules
  - 找 lifecycle=deprecated 规则
  - deprecated_at 超 deprecated_to_removed_days (28天) → gc 候选
  - --dry-run: 显示将清理 (不改)
  - 实际清理: 提示手动改 lifecycle=removed (未来 --apply 自动)

c2g gc 原语 = GaC lifecycle 清理 (机制 6 完整闭环).
当前 7 规则全 active, gc 无清理 (逻辑就绪, 未来 deprecated 规则生效).

用法:
  python3 bin/gac/gac-gc.py              # 扫描 + 报告
  python3 bin/gac/gac-gc.py --dry-run    # 显示 gc 候选 (不改)
  python3 bin/gac/gac-gc.py --json       # JSON (cron/仪表盘)

CI 可移植: Path(__file__).resolve().parents[2]. 对标 gac-validate/gac-drift/gac-healthcheck.
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
DEPRECATED_TO_REMOVED_DAYS = 28  # gac.lifecycle.deprecated_to_removed_days


def load_rules() -> list[dict]:
    """加载 governance-checks.yaml::gac.rules (多文档 strip frontmatter)."""
    import yaml

    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def find_gc_candidates(
    rules: list[dict], max_days: int = DEPRECATED_TO_REMOVED_DAYS
) -> list[dict]:
    """找 deprecated 超 max_days 的规则 (待 gc 清理 removed).

    deprecated 无 deprecated_at → 标记 (待补字段).
    """
    candidates: list[dict] = []
    today = datetime.date.today()
    for r in rules:
        if r.get("lifecycle") != "deprecated":
            continue
        dep_at = r.get("deprecated_at")
        if not dep_at:
            candidates.append(
                {
                    **r,
                    "age_days": None,
                    "reason": "deprecated 无 deprecated_at (待补字段)",
                }
            )
            continue
        try:
            dd = datetime.date.fromisoformat(dep_at)
        except (ValueError, TypeError):
            continue
        age = (today - dd).days
        if age > max_days:
            candidates.append(
                {**r, "age_days": age, "reason": f"deprecated {age} 天 > {max_days} 天"}
            )
    return candidates


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    json_mode = "--json" in args

    rules = load_rules()
    lc = Counter(r.get("lifecycle", "?") for r in rules)
    candidates = find_gc_candidates(rules)

    report = {
        "rules": len(rules),
        "lifecycle": dict(lc),
        "deprecated_total": lc.get("deprecated", 0),
        "gc_candidates": len(candidates),
        "candidates": [
            {"id": c["id"], "age_days": c.get("age_days"), "reason": c.get("reason")}
            for c in candidates
        ],
        "dry_run": dry_run,
        "threshold_days": DEPRECATED_TO_REMOVED_DAYS,
    }

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=== GaC gc (lifecycle 清理, 机制6, c2g gc 原语) ===")
    print(f"规则数: {len(rules)} | lifecycle: {dict(lc)}")
    print(
        f"deprecated: {lc.get('deprecated', 0)} | "
        f"gc 候选 (超 {DEPRECATED_TO_REMOVED_DAYS} 天): {len(candidates)}"
    )

    if candidates:
        label = "[dry-run] 待清理" if dry_run else "待清理"
        print(f"\n⚠️  {label}:")
        for c in candidates:
            age = f"{c.get('age_days')}天" if c.get("age_days") is not None else "?"
            print(f"  - {c['id']} (deprecated {age}): {c.get('reason')}")
        if not dry_run:
            print(
                "\n实际清理: 手动改 governance-checks.yaml lifecycle=removed "
                "(未来 --apply 自动, 需 omo MCP write)"
            )
    else:
        print("\n✅ 无 gc 候选 (全 active 或 deprecated 未超期)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
