#!/usr/bin/env python3
"""P87 R2: X2 rule interactive add tool.

交互式添加新的 X2 freshness rule, 自动:
- 分配下一个 rule_id (X2-FRESH-XXX 顺序)
- 验证必填字段 (target, freshness.threshold_days, freshness.action)
- 验证 target glob 命中至少一个文件 (archived 豁免)
- 追加到 .omo/_truth/x2-freshness-rules.yaml
- 跑 x2-rule-lint 验证 (新规则必须 0 issues)

使用:
  python3 bin/x2-rule-add.py                  # 交互式
  python3 bin/x2-rule-add.py --template      # 打印 YAML 模板
  python3 bin/x2-rule-add.py --check         # 仅检查现有规则 (不添加)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

VALID_ACTIONS = {"warn", "escalate", "error"}
REQUIRED_FIELDS = ["rule_id", "target", "freshness.threshold_days", "freshness.action"]


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rules: list[dict] = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            rules.extend(doc.get("rules", []))
    return rules


def next_rule_id(existing: list[dict], prefix: str = "X2-FRESH") -> str:
    """分配下一个 rule_id (X2-FRESH-NEW-001, NEW-002 ...)."""
    used: set[str] = set()
    for r in existing:
        rid = r.get("rule_id", "")
        m = re.match(rf"^{re.escape(prefix)}-([A-Z0-9]+)-(\d+)$", rid)
        if m:
            used.add(f"{m.group(1)}-{int(m.group(2))}")
    # 找下一个可用
    for n in range(1, 1000):
        candidate = f"{prefix}-NEW-{n:03d}"
        if candidate not in {r.get("rule_id", "") for r in existing}:
            return candidate
    return f"{prefix}-NEW-{len(existing)+1:03d}"


def validate_rule(rule: dict, root: Path) -> list[str]:
    """验证单条 rule, 返回 errors 列表."""
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        parts = field.split(".")
        cur = rule
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                errors.append(f"missing required field: {field}")
                break
            cur = cur[p]
    fresh = rule.get("freshness", {})
    if isinstance(fresh, dict):
        td = fresh.get("threshold_days")
        if not isinstance(td, int) or td <= 0:
            errors.append(f"freshness.threshold_days must be positive int, got {td!r}")
        action = fresh.get("action")
        if action not in VALID_ACTIONS:
            errors.append(f"freshness.action must be one of {VALID_ACTIONS}, got {action!r}")
    target = rule.get("target", "")
    if target:
        matches = list(root.glob(target))
        if not matches and not rule.get("archived", False):
            errors.append(f"target glob '{target}' matches 0 files (archived 豁免)")
    rid = rule.get("rule_id", "")
    if rid and not re.match(r"^X2-FRESH-[A-Z0-9-]+$", rid):
        errors.append(f"rule_id format must be X2-FRESH-XXX, got {rid!r}")
    return errors


def add_rule_to_yaml(yaml_path: Path, new_rule: dict) -> int:
    """追加 rule 到 YAML 文件末尾. 简单策略: 追加到文件末尾."""
    if not yaml_path.exists():
        yaml_path.write_text(
            "---\nstatus: active\nlifecycle: ssot\nowner: governance-team\n"
            "last-reviewed: 2026-06-25\n---\n\nrules:\n",
            encoding="utf-8",
        )

    # 新 rule YAML 块 (title 用引号包裹防 YAML 解析问题, e.g. 含 ":" 时)
    rid = new_rule["rule_id"]
    target = new_rule["target"]
    fresh = new_rule["freshness"]
    title = new_rule.get("title", rid).replace('"', '\\"')
    new_yaml = (
        f'  - rule_id: {rid}\n'
        f'    title: "{title}"\n'
        f"    type: {new_rule.get('type', 'governance_loop_freshness')}\n"
        f"    status: active\n"
        f"    target: {target}\n"
        f"    freshness:\n"
        f"      mechanism: {new_rule.get('mechanism', 'manual-review')}\n"
        f"      threshold_days: {fresh['threshold_days']}\n"
        f"      action: {fresh['action']}\n"
        f"    owner: {new_rule.get('owner', 'governance-team')}\n"
        f"    notes: >\n"
        f"      P90 R2 新增 rule (omo_lint.py 抗 god-module 监控).\n\n"
    )

    # 追加到文件末尾 (YAML 允许多 document, 用 --- 分隔)
    with yaml_path.open("a", encoding="utf-8") as f:
        f.write(new_yaml)
    return len(new_yaml)


def interactive_prompt() -> dict:
    """交互式提示用户输入 rule 字段."""
    print("🆕 P87 X2 rule 交互式添加")
    print()
    rule: dict = {}
    rule["title"] = input("  标题 (e.g. 'My new rule'): ").strip() or "Untitled rule"
    rule["type"] = input("  类型 [governance_loop_freshness]: ").strip() or "governance_loop_freshness"
    rule["target"] = input("  target glob (e.g. '.omo/_truth/*.yaml'): ").strip()
    if not rule["target"]:
        print("❌ target 必填")
        return {}
    rule["mechanism"] = input("  mechanism [manual-review]: ").strip() or "manual-review"
    try:
        td = int(input("  threshold_days (正整数): ").strip() or "14")
        if td <= 0:
            raise ValueError
    except ValueError:
        print("❌ threshold_days 必须是正整数")
        return {}
    action = input("  action [warn/escalate/error]: ").strip() or "warn"
    if action not in VALID_ACTIONS:
        print(f"❌ action 必须是 {VALID_ACTIONS}")
        return {}
    rule["owner"] = input("  owner [governance-team]: ").strip() or "governance-team"
    rule["freshness"] = {"threshold_days": td, "action": action}
    return rule


def main() -> int:
    parser = argparse.ArgumentParser(description="P87: X2 rule interactive add")
    parser.add_argument(
        "--rules",
        default=".omo/_truth/x2-freshness-rules.yaml",
        help="X2 rules YAML",
    )
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--template", action="store_true", help="打印 YAML 模板")
    parser.add_argument("--check", action="store_true", help="仅检查现有规则")
    parser.add_argument("--non-interactive", action="store_true",
                        help="非交互 (从 stdin 读 rule_id/title/target/threshold/action)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    yaml_path = root / args.rules
    rules = load_rules(yaml_path)

    if args.template:
        print("""X2 rule YAML 模板:

  - rule_id: X2-FRESH-NEW-001
    title: <short description>
    type: governance_loop_freshness  # 或 governance_surface_freshness / compatibility_alias_watch / ...
    status: active
    target: <path or glob>
    freshness:
      mechanism: manual-review  # 或 registry-review / governance-audit / git-commit-staleness
      threshold_days: 14
      action: warn  # 或 escalate / error
    owner: governance-team
    notes: >
      解释为什么需要这条 rule.
""")
        return 0

    if args.check:
        all_errors = []
        for r in rules:
            errs = validate_rule(r, root)
            for e in errs:
                all_errors.append((r.get("rule_id", "?"), e))
        if not all_errors:
            print(f"✅ {len(rules)} rules 全部健康")
            return 0
        for rid, e in all_errors:
            print(f"  ❌ {rid}: {e}")
        return 1

    if args.non_interactive:
        # 读 stdin 多行
        print("📝 非交互模式: 5 行 (rule_id, title, target, threshold_days, action)")
        try:
            rid = input().strip()
            title = input().strip() or rid
            target = input().strip()
            if not target:
                print("❌ target 必填")
                return 1
            threshold_str = input().strip() or "14"
            action = input().strip() or "warn"
            try:
                threshold = int(threshold_str)
            except ValueError:
                print(f"❌ threshold_days 必须是整数, got {threshold_str!r}")
                return 1
            rule = {
                "rule_id": rid,
                "title": title,
                "target": target,
                "freshness": {
                    "threshold_days": threshold,
                    "action": action,
                },
                "type": "governance_loop_freshness",
                "mechanism": "manual-review",
                "owner": "governance-team",
            }
        except (EOFError, KeyboardInterrupt):
            return 1
    else:
        rule = interactive_prompt()
        if not rule:
            return 1

    # 分配 rule_id
    if "rule_id" not in rule:
        rule["rule_id"] = next_rule_id(rules)

    # 验证
    errs = validate_rule(rule, root)
    if errs:
        for e in errs:
            print(f"  ❌ {e}")
        return 1

    # 写入
    written = add_rule_to_yaml(yaml_path, rule)
    print(f"✅ 追加 rule {rule['rule_id']} ({written} bytes) 到 {yaml_path}")

    # 跑 x2-rule-lint 验证
    print()
    print("🔍 跑 x2-rule-lint 验证...")
    import subprocess
    result = subprocess.run(
        ["python3", str(root / "bin/x2-rule-lint.py")],
        cwd=str(root), capture_output=True, text=True, timeout=30,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ x2-rule-lint 失败 (exit {result.returncode})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
