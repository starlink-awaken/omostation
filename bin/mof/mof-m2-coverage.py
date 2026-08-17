#!/usr/bin/env python3
"""P84 R1: M2 schema coverage tool (修正 mof-schema-validate type coverage 噪音).

`projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py --type-coverage` 当前报告
"M2 孤儿: 69" 但其中 67 是 case-mismatch 噪音 (alias 计算包含 m2_type.lower(),
把 PascalCase 的 Action 也加上了 'action', 然后 M1 只用 Action, 'action' 算孤儿).

正确做法: 比较 M2 schema 的 m2_type 字段 (PascalCase) vs M1 node 的 type 字段.
只报告真正的孤儿 (m2_type 存在但 M1 任何节点都没用).

使用:
  python3 bin/mof/mof-m2-coverage.py
  python3 bin/mof/mof-m2-coverage.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml


def load_m2_types(m2_dir: Path) -> dict[str, str]:
    """加载 M2 schema 的 m2_type 字段, 返回 m2_type -> filename."""
    m2_map: dict[str, str] = {}
    if not m2_dir.exists():
        return m2_map
    for f in sorted(m2_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        mt = data.get("m2_type")
        if mt:
            m2_map[mt] = f.name
    return m2_map


def load_m1_types(m1_dir: Path) -> Counter:
    """加载 M1 node 的 type 字段使用统计."""
    type_counter: Counter = Counter()
    if not m1_dir.exists():
        return type_counter
    for d in sorted(m1_dir.iterdir()):
        if not d.is_dir():
            continue
        for f in d.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                t = data.get("type")
                if t:
                    type_counter[t] += 1
    return type_counter


def analyze(m2_dir: Path, m1_dir: Path) -> dict:
    """分析 M2 vs M1 type 覆盖."""
    m2_map = load_m2_types(m2_dir)
    m1_types = load_m1_types(m1_dir)

    m2_set = set(m2_map.keys())
    used = set(m1_types.keys())
    # 真正的孤儿: M2 m2_type 在 M1 中无任何节点使用
    true_orphans = sorted(m2_set - used)
    # 漂移: M1 用了但 M2 没有 (即 type drift)
    drift = sorted(used - m2_set)

    return {
        "m2_total": len(m2_map),
        "m1_unique_types": len(m1_types),
        "m1_total_nodes": sum(m1_types.values()),
        "used_count": len(used & m2_set),
        "coverage_pct": round(100 * len(used & m2_set) / len(m2_set), 1) if m2_set else 0.0,
        "true_orphans": true_orphans,
        "true_orphans_with_file": [(mt, m2_map[mt]) for mt in true_orphans],
        "drift": drift,
        "top_used": m1_types.most_common(20),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P84: M2 schema coverage tool (修正版)")
    parser.add_argument(
        "--m2-dir",
        default="projects/ecos/src/ecos/ssot/mof/m2",
        help="M2 schema dir",
    )
    parser.add_argument(
        "--m1-dir",
        default="projects/ecos/src/ecos/ssot/mof/m1",
        help="M1 node dir",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    m2_dir = Path(args.m2_dir)
    m1_dir = Path(args.m1_dir)

    if not m2_dir.exists():
        print(f"❌ M2 dir 不存在: {m2_dir}")
        return 1
    if not m1_dir.exists():
        print(f"❌ M1 dir 不存在: {m1_dir}")
        return 1

    result = analyze(m2_dir, m1_dir)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("📊 P84 M2 schema coverage (修正版)")
    print("=" * 60)
    print(f"📁 M2 schemas: {result['m2_total']}")
    print(f"📁 M1 nodes: {result['m1_total_nodes']} ({result['m1_unique_types']} unique types)")
    print(f"✅ M1 引用 M2: {result['used_count']} / {result['m2_total']} = {result['coverage_pct']}%")
    print(f"❌ 真正孤儿 (M2 m2_type 在 M1 未用): {len(result['true_orphans'])}")
    print(f"⚠️  Type drift (M1 用了但 M2 没有): {len(result['drift'])}")
    print()
    if result["true_orphans"]:
        print("🔍 真正孤儿 (M2 存在但无 M1 引用):")
        for mt, fn in result["true_orphans_with_file"]:
            print(f"   {mt:<30s}  ({fn})")
    if result["drift"]:
        print("\n⚠️  Type drift (M1 用了 M2 没声明):")
        for t in result["drift"][:10]:
            print(f"   {t}")
    if not result["true_orphans"] and not result["drift"]:
        print("\n🎉 100% 覆盖, 0 孤儿, 0 drift!")
    print()
    print("📈 Top 20 M1 type 使用:")
    for t, c in result["top_used"]:
        in_m2 = "✓" if t in {x[0] for x in result["true_orphans_with_file"]} or _is_m2_type(t, m2_dir) else "✗"
        print(f"   {t:<30s} {c:>4d}x  [{in_m2}]")

    return 0


def _is_m2_type(t: str, m2_dir: Path) -> bool:
    """检查 t 是否为 M2 m2_type."""
    for f in m2_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("m2_type") == t:
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    sys.exit(main())
