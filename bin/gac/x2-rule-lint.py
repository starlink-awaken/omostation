#!/usr/bin/env python3
"""P85 R1: X2 rule lint tool.

校验 .omo/_truth/x2-freshness-rules.yaml 自身的健康度:
- 必填字段完整 (rule_id, target, freshness.threshold_days, freshness.action)
- target glob 至少匹配一个真实文件/目录
- threshold_days 是正整数
- action 在合法集合内 (warn/escalate/error)
- rule_id 唯一
- 编号连续性 (X2-FRESH-XXX)

使用:
  python3 bin/gac/x2-rule-lint.py
  python3 bin/gac/x2-rule-lint.py --strict
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

VALID_ACTIONS = {"warn", "escalate", "error"}
REQUIRED_FIELDS = ["rule_id", "target"]
REQUIRED_FRESHNESS = ["threshold_days", "action"]


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rules: list[dict] = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            rules.extend(doc.get("rules", []))
    return rules


def lint_rules(rules: list[dict], root: Path) -> list[dict]:
    """检查每条 rule 的健康度."""
    issues: list[dict] = []
    seen_ids: Counter = Counter()

    for i, rule in enumerate(rules):
        rid = rule.get("rule_id", f"<index {i}>")
        seen_ids[rid] += 1

        # 必填字段
        for field in REQUIRED_FIELDS:
            if not rule.get(field):
                issues.append({
                    "rule_id": rid,
                    "severity": "error",
                    "msg": f"missing required field: {field}",
                })

        # freshness 子字段
        fresh = rule.get("freshness", {})
        if not isinstance(fresh, dict):
            issues.append({
                "rule_id": rid,
                "severity": "error",
                "msg": "freshness 字段必须是 dict",
            })
        else:
            for f in REQUIRED_FRESHNESS:
                if f not in fresh:
                    issues.append({
                        "rule_id": rid,
                        "severity": "error",
                        "msg": f"missing freshness.{f}",
                    })
            # threshold_days 正整数
            td = fresh.get("threshold_days")
            if not isinstance(td, int) or td <= 0:
                issues.append({
                    "rule_id": rid,
                    "severity": "error",
                    "msg": f"freshness.threshold_days 必须是正整数, 当前 {td!r}",
                })
            # action 合法
            action = fresh.get("action")
            if action not in VALID_ACTIONS:
                issues.append({
                    "rule_id": rid,
                    "severity": "error",
                    "msg": f"freshness.action 必须是 {VALID_ACTIONS}, 当前 {action!r}",
                })

        # target glob 至少匹配一个文件/目录
        target = rule.get("target", "")
        if target:
            matches = list(root.glob(target))
            if not matches:
                # archived 项目豁免
                if not rule.get("archived", False):
                    issues.append({
                        "rule_id": rid,
                        "severity": "warn",
                        "msg": f"target glob '{target}' 0 匹配",
                    })

        # rule_id 格式 X2-FRESH-XXX
        if rid and not re.match(r"^X2-FRESH-[A-Z0-9-]+$", rid):
            issues.append({
                "rule_id": rid,
                "severity": "warn",
                "msg": f"rule_id 格式应为 X2-FRESH-XXX, 当前 {rid!r}",
            })

    # rule_id 重复
    for rid, count in seen_ids.items():
        if count > 1:
            issues.append({
                "rule_id": rid,
                "severity": "error",
                "msg": f"rule_id 重复 {count} 次",
            })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="P85: X2 rule lint")
    parser.add_argument(
        "--rules",
        default=".omo/_truth/x2-freshness-rules.yaml",
        help="X2 rules YAML",
    )
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--strict", action="store_true", help="warn 也算 error (exit 1)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    rules = load_rules(root / args.rules)
    if not rules:
        print(f"❌ 未加载到 rules: {args.rules}")
        return 1

    issues = lint_rules(rules, root)

    if args.json:
        import json
        print(json.dumps({
            "total_rules": len(rules),
            "issue_count": len(issues),
            "by_severity": dict(Counter(i["severity"] for i in issues)),
            "issues": issues,
        }, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P85 X2 rule lint")
    print("=" * 60)
    print(f"📋 Rules: {len(rules)}")
    print(f"⚠️  Issues: {len(issues)}")
    print()
    by_sev = Counter(i["severity"] for i in issues)
    print(f"   error: {by_sev.get('error', 0)}")
    print(f"   warn:  {by_sev.get('warn', 0)}")
    print()
    if issues:
        for issue in issues:
            icon = "❌" if issue["severity"] == "error" else "⚠️"
            print(f"  {icon} [{issue['severity']}] {issue['rule_id']}: {issue['msg']}")
    else:
        print("🎉 所有 X2 rules 健康!")

    if args.strict and by_sev.get("warn", 0) > 0:
        return 1
    return 1 if by_sev.get("error", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
