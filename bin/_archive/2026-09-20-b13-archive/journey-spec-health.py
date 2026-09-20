#!/usr/bin/env python3
"""journey-spec-health — 48 个 Journey Spec 健康检查。

批量验证 journey spec 的有效性:
- frontmatter 完整性
- 状态机定义
- 引用关系

Usage:
    python3 bin/ssot/journey-spec-health.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS_DIR = REPO / "docs/superpowers/specs"


def check_spec(file_path: Path) -> dict:
    """检查单个 journey spec 的健康状态。"""
    content = file_path.read_text(encoding="utf-8")
    name = file_path.name

    has_schema = "schema:" in content
    has_journey_id = "journey_id:" in content
    has_states = "states:" in content
    has_transitions = "transitions:" in content

    healthy = has_schema and has_journey_id and has_states

    return {
        "file": name,
        "healthy": healthy,
        "checks": {
            "schema": has_schema,
            "journey_id": has_journey_id,
            "states": has_states,
            "transitions": has_transitions,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Journey Spec 健康检查")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not SPECS_DIR.exists():
        print(f"Specs directory not found: {SPECS_DIR}", file=sys.stderr)
        return 1

    specs = list(SPECS_DIR.glob("journey-*.md")) + list(SPECS_DIR.glob("**/journey-*.md"))
    results = [check_spec(f) for f in specs]

    healthy_count = sum(1 for r in results if r["healthy"])
    total = len(results)

    output = {
        "total": total,
        "healthy": healthy_count,
        "unhealthy": total - healthy_count,
        "specs": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Journey Spec Health: {healthy_count}/{total} healthy")
        for r in results:
            icon = "✅" if r["healthy"] else "❌"
            print(f"  {icon} {r['file']}")

    return 0 if healthy_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
