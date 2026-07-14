#!/usr/bin/env python3
"""debt-closed-per-feature.py — P76 Phase 3 指标

每交付 1 个 feature, 必须关闭 ≥ 0.5 个 debt (issued-pending tasks).
governance score 真正与开发节奏挂钩.

数据来源:
  - .omo/_truth/registry/debt.yaml    (debt items, status: active/resolved)
  - .omo/_knowledge/audits/*.md       (closeout evidence)
  - 近期 git log commits               (feature deliveries)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def load_debt_items() -> dict[str, list[dict]]:
    """从 .omo/debt/items/*.yaml 加载 debt items, 按 lifecycle_state 分组."""
    import yaml

    items_dir = WORKSPACE / ".omo" / "debt" / "items"
    by_status: dict[str, list[dict]] = defaultdict(list)
    if not items_dir.exists():
        return {"active": [], "resolved": [], "other": []}
    for f in items_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as exc:
            print(f"⚠️ {f.name} parse error: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        # debt v2 schema: lifecycle_state (active/resolved/partial)
        state = data.get("lifecycle_state") or data.get("status") or "other"
        by_status[state].append(data)
    return by_status


def debt_count_in_dir(items_dir: Path, state: str) -> int:
    import yaml
    n = 0
    if not items_dir.exists():
        return 0
    for f in items_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            continue
        s = (data.get("lifecycle_state") or data.get("status") or "") if isinstance(data, dict) else ""
        if s == state:
            n += 1
    return n


def feature_count(days: int = 30) -> int:
    """过去 N 天 feature delivery 数 (conventionally commits with 'feat:' prefix)."""
    since_arg = f"--since={days} days ago"
    try:
        result = subprocess.run(
            ["git", "log", since_arg, "--oneline", "--pretty=format:%s"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return 0
    feat_re = re.compile(r"^\s*(feat|Feat|FEAT):")
    return sum(1 for line in result.stdout.splitlines() if feat_re.match(line))


def debt_closed_count(days: int = 30) -> int:
    """过去 N 天 debt closed (resolved) 数. 通过 git log .omo/debt/items/ 监测."""
    items_dir_rel = ".omo/debt/items"
    since_arg = f"--since={days} days ago"
    try:
        result = subprocess.run(
            ["git", "log", since_arg, "--diff-filter=AM", "--pretty=format:", "--name-only",
             "--", items_dir_rel],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return 0
    debt_changes = set(filter(lambda p: p.endswith(".yaml") and "/items/" in p,
                              filter(None, result.stdout.splitlines())))
    return len(debt_changes)


def main() -> int:
    days = 30
    items = load_debt_items()
    active = items.get("active", [])
    resolved = items.get("resolved", [])
    feat = feature_count(days)
    closed = debt_closed_count(days)
    ratio = closed / feat if feat else 0.0
    threshold = 0.5

    print(f"=== debt-closed-per-feature ({days} 天窗口) ===")
    print(f"active debt:    {len(active)}")
    print(f"resolved debt:  {len(resolved)}")
    print(f"feature commits: {feat}")
    print(f"debt closed:    {closed}")
    print(f"ratio:          {ratio:.3f} (threshold {threshold})")
    print(f"verdict:        {'✅ ABOVE threshold' if ratio >= threshold else '❌ BELOW threshold'}")
    return 0 if ratio >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
