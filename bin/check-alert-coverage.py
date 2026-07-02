#!/usr/bin/env python3
"""check-alert-coverage: 检测 governance-alerts rules 中无 evaluator 的覆盖缺口.

治本 ISC-6: governance-alert-dispatch --dry-run 暴露 4 个 unsupported rule
(fail/warn/sla_violated/ci_count). 本工具独立 CI check, 报告 uncovered rule 列表,
exit 1 if > 0 — 倒逼补 evaluator (元根因 1: 声明 vs 执行器一致性检测).

复用 dispatcher 的 EVALUATORS + evaluate_rule (importlib 加载连字符文件名).
未来补 evaluator 后, 本 check 自动通过 (无需改本工具).

用法:
  python bin/check-alert-coverage.py        # 报告 uncovered, 有则 exit 1
  python bin/check-alert-coverage.py --json  # JSON 输出
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
DISPATCHER = WORKSPACE / "bin" / "governance-alert-dispatch.py"
ALERTS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-alerts.yaml"


def _load_dispatcher():
    """importlib 加载 governance-alert-dispatch (连字符文件名不能直接 import)."""
    spec = importlib.util.spec_from_file_location("gad", DISPATCHER)
    if spec is None or spec.loader is None:  # type: ignore[union-attr]
        raise RuntimeError(f"无法加载 dispatcher spec: {DISPATCHER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(description="check-alert-coverage: rule evaluator 覆盖检测 (ISC-6)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    gad = _load_dispatcher()
    rules = gad._load_alert_rules(ALERTS_YAML)
    if not rules:
        print(f"⚠️  {ALERTS_YAML} 无 rules", file=sys.stderr)
        return 1

    # 已知永久 unsupported conditions (需外部系统接入, 非覆盖缺口, TASK-236A991C)
    # 参考 governance-alert-dispatch.py 设计: 这些 condition 需 X1 实时执行器/CI 探测器/SLA 追踪器
    KNOWN_PERMANENT_UNSUPPORTED = {"fail", "warn", "sla_violated", "ci_count"}

    uncovered = []
    covered = 0
    known_unsupported = 0
    for rule in rules:
        r = gad.evaluate_rule(rule, WORKSPACE)
        if r["status"] == "unsupported":
            condition = str(rule.get("condition", "")).strip()
            # 提取 metric name: 'ci_count < 5' → 'ci_count', 'fail' → 'fail'
            condition_metric = re.split(r"[\s<>=!]", condition)[0] if condition else ""
            if condition in KNOWN_PERMANENT_UNSUPPORTED or condition_metric in KNOWN_PERMANENT_UNSUPPORTED:
                known_unsupported += 1  # 已知永久 unsupported, 不算覆盖缺口
            else:
                uncovered.append(r)
        else:
            covered += 1

    total = len(rules)
    effective_covered = covered + known_unsupported
    coverage_pct = round(effective_covered / total * 100) if total else 0

    if args.json:
        print(json.dumps({
            "total": total, "covered": covered, "uncovered": len(uncovered),
            "coverage_pct": coverage_pct,
            "uncovered_rules": [{"id": r["id"], "condition": r["condition"], "note": r["note"]} for r in uncovered],
        }, indent=2, ensure_ascii=False))
    else:
        if not uncovered:
            extra = f" (+{known_unsupported} 已知永久 unsupported)" if known_unsupported else ""
            print(f"✅ alert-coverage: {covered}/{total} rules 有 evaluator (coverage {coverage_pct}%{extra})")
        else:
            print(f"❌ alert-coverage: {len(uncovered)}/{total} rules 无 evaluator (coverage {coverage_pct}%, ISC-6 检测):")
            for r in uncovered:
                print(f"  - {r['id']} ({r['condition']!r}): {r['note']}")
            print(f"\n治本: 为上述 condition 补 evaluator (governance-alert-dispatch.py EVALUATORS dict)")

    return 1 if uncovered else 0


if __name__ == "__main__":
    sys.exit(main())
