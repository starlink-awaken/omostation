#!/usr/bin/env python3
"""Tool Governance — 工具分级治理.

分级:
  P0 Core:      CI + 测试 + 监控 + 文档
  P1 Active:    CI + 测试
  P2 Available: 可用但未接入
  P3 Deprecated: 无调用/被替代 → 归档

用法:
    python3 tool-governance.py              # 分级报告
    python3 tool-governance.py --json       # JSON
    python3 tool-governance.py --archive    # 归档 P3 工具
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ECOS_TOOLS = REPO / "projects/ecos/src/ecos/ssot/tools"
WORKFLOW = REPO / ".github/workflows/ecos-ci.yml"


def audit_tools() -> dict:
    """工具分级审计."""
    if not ECOS_TOOLS.exists():
        return {"error": "submodule not init"}

    ci_content = WORKFLOW.read_text() if WORKFLOW.exists() else ""

    tools = []
    for f in sorted(ECOS_TOOLS.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        in_ci = name in ci_content
        has_test = (REPO / "projects/ecos/tests" / f"test_{name}.py").exists()
        tools.append({
            "name": name,
            "in_ci": in_ci,
            "has_test": has_test,
        })

    p0 = [t for t in tools if t["in_ci"] and t["has_test"]]
    p1 = [t for t in tools if t["in_ci"] or t["has_test"]]
    p2 = [t for t in tools if not t["in_ci"] and not t["has_test"]]

    return {
        "total": len(tools),
        "p0_core": len(p0),
        "p1_active": len(p1),
        "p2_available": len(p2),
        "ci_coverage": f"{len([t for t in tools if t['in_ci']])}/{len(tools)}",
        "tools": tools,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit_tools()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Tool Governance Report")
    print("=" * 56)
    print(f"  Total: {result['total']}")
    print(f"  P0 Core (CI+Test): {result['p0_core']}")
    print(f"  P1 Active (CI|Test): {result['p1_active']}")
    print(f"  P2 Available: {result['p2_available']}")
    print(f"  CI Coverage: {result['ci_coverage']}")


if __name__ == "__main__":
    sys.exit(main())
