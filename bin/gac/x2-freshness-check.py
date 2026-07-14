#!/usr/bin/env python3
"""P84 R2: X2 freshness check tool.

读取 .omo/_truth/x2-freshness-rules.yaml, 对每条规则:
- 解析 target/threshold_days/action
- 检查 target 路径的最后修改时间 vs 当前时间
- 如果超 threshold_days, 触发对应 action (warn / escalate / error)

使用:
  python3 bin/gac/x2-freshness-check.py
  python3 bin/gac/x2-freshness-check.py --json
  python3 bin/gac/x2-freshness-check.py --days 7  # 阈值天数 (覆盖)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_rules(path: Path) -> list[dict]:
    """加载 X2 rules (兼容多文档 YAML)."""
    if not path.exists():
        return []
    rules: list[dict] = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            rules.extend(doc.get("rules", []))
    return rules


def path_last_modified(root: Path, target: str) -> datetime | None:
    """获取 target 路径最后修改时间 (支持 glob 模式)."""
    # target 可以是文件/目录/glob
    full = root / target
    # 先尝试直接路径
    if full.exists():
        try:
            mtime = full.stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc)
        except Exception:
            return None
    # glob 模式
    matches = list(root.glob(target))
    if not matches:
        return None
    # 取最近修改时间
    latest = max((m.stat().st_mtime for m in matches if m.exists()), default=None)
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc)


def check_rule(rule: dict, root: Path, now: datetime, override_days: int | None) -> dict:
    """检查单条 rule 的新鲜度."""
    target = rule.get("target", "")
    threshold = override_days or rule.get("freshness", {}).get("threshold_days", 30)
    action = rule.get("freshness", {}).get("action", "warn")
    status = rule.get("status", "active")
    archived = rule.get("archived", False)

    mtime = path_last_modified(root, target)
    days_since = None
    triggered = False
    severity = "ok"

    if mtime:
        days_since = (now - mtime).days
        if archived:
            # 归档项目不算超期, 它的 freshness 是另一回事
            severity = "info"
        elif status == "active" and days_since > threshold:
            triggered = True
            if action == "escalate":
                severity = "fail"
            elif action == "error":
                severity = "fail"
            else:
                severity = "warn"
    else:
        if status == "active" and not archived:
            triggered = True
            severity = "warn"  # target 不存在但 rule active

    return {
        "rule_id": rule.get("rule_id", "?"),
        "title": rule.get("title", ""),
        "target": target,
        "status": status,
        "archived": archived,
        "threshold_days": threshold,
        "action": action,
        "mtime": mtime.isoformat() if mtime else None,
        "days_since": days_since,
        "triggered": triggered,
        "severity": severity,
    }


def analyze(rules: list[dict], root: Path, override_days: int | None) -> dict:
    """分析所有 rules."""
    now = datetime.now(tz=timezone.utc)
    results = [check_rule(r, root, now, override_days) for r in rules]
    triggered = [r for r in results if r["triggered"]]
    by_severity: dict[str, int] = {}
    for r in results:
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1

    return {
        "total_rules": len(results),
        "triggered_count": len(triggered),
        "by_severity": by_severity,
        "results": results,
        "checked_at": now.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P84: X2 freshness check")
    parser.add_argument(
        "--rules",
        default=".omo/_truth/x2-freshness-rules.yaml",
        help="X2 rules YAML path",
    )
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--days", type=int, default=None, help="覆盖阈值天数")
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

    result = analyze(rules, root, args.days)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("📊 P84 X2 freshness check")
    print("=" * 60)
    print(f"📋 Rules 总数: {result['total_rules']}")
    print(f"⚠️  触发: {result['triggered_count']}")
    print(f"📊 严重度: {result['by_severity']}")
    print()
    for r in result["results"]:
        sev_icon = {"ok": "✓", "info": "ℹ", "warn": "⚠️", "fail": "❌"}.get(r["severity"], "?")
        target_short = r["target"][:50] if r["target"] else "(无 target)"
        days_str = f"{r['days_since']}d" if r["days_since"] is not None else "?"
        print(f"  {sev_icon} {r['rule_id']:<40s}  threshold={r['threshold_days']:>3d}d  "
              f"age={days_str:>5s}  action={r['action']}")
        print(f"      {r['title']}")
        print(f"      target: {target_short}")
    print()
    if result["triggered_count"] == 0:
        print("OK 所有 X2 rules 保鲜状态 OK")
    else:
        print(f"WARN {result['triggered_count']} rules 触发, 需处理 (informational, not blocking)")

    # P111 修复: warnings are informational, do NOT block dashboard / cron
    # Old behavior: return 1 if any rule triggered (blocked dashboard even for warnings)
    # New behavior: always return 0, warnings are reported in output for human review
    return 0


if __name__ == "__main__":
    sys.exit(main())
