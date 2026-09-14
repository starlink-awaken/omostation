#!/usr/bin/env python3
"""round-milestone-tracker — Round 里程碑追踪。

追踪 R0-R5 历史 milestone，自动对比当前 Round 与历史。

Usage:
    python3 bin/plan/round-milestone-tracker.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 历史 milestone (从 AGENTS.md §10.3 提取)
HISTORICAL_MILESTONES = [
    {"round": "R0", "adr_count": 5, "description": "主决策 + L0↔M2 桥接"},
    {"round": "R2", "adr_count": 3, "description": "派生落点 + MetaElement 提升"},
    {"round": "R3", "adr_count": 2, "description": "Health Score 量化"},
    {"round": "R4", "adr_count": 4, "description": "速查 + 45 m2 datetime"},
    {"round": "R5", "adr_count": 3, "description": "8 阶段稳定性"},
]


def get_current_round() -> dict:
    """从 git tag 或 branch 推断当前 Round。"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=REPO,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            return {"tag": tag, "source": "git_tag"}
    except Exception:
        pass
    return {"tag": "unknown", "source": "none"}


def main():
    parser = argparse.ArgumentParser(description="Round 里程碑追踪")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    current = get_current_round()

    results = {
        "current": current,
        "historical": HISTORICAL_MILESTONES,
        "total_adr": sum(m["adr_count"] for m in HISTORICAL_MILESTONES),
        "total_rounds": len(HISTORICAL_MILESTONES),
    }

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"Current: {current['tag']}")
        print(f"Historical Milestones ({results['total_rounds']} rounds, {results['total_adr']} ADRs):")
        for m in HISTORICAL_MILESTONES:
            print(f"  {m['round']}: {m['adr_count']} ADR — {m['description']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
