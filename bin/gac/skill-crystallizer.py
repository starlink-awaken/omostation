#!/usr/bin/env python3
"""skill-crystallizer.py — SEMA 技能自动结晶引擎 CLI (BET-Y1Q2-T6-06)

扫描 .omo/state/agent-beliefs/index.yaml 中的踩坑信念。
当同 topic 累积 >= 2 条信念时, 自动萃取为 .agents/skills/<topic>/SKILL.md。

Usage:
    python bin/gac/skill-crystallizer.py              # 执行结晶
    python bin/gac/skill-crystallizer.py --check       # dry-run: 仅报告, 不写文件
    python bin/gac/skill-crystallizer.py --json        # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BELIEFS_PATH = WORKSPACE_ROOT / ".omo" / "state" / "agent-beliefs" / "index.yaml"


def _load_state() -> dict:
    if not BELIEFS_PATH.exists():
        return {"beliefs": [], "lessons": [], "contexts": []}
    with open(BELIEFS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "beliefs": data.get("beliefs", []),
        "lessons": data.get("lessons", []),
        "contexts": data.get("contexts", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SEMA 技能自动结晶引擎 (BET-Y1Q2-T6-06)"
    )
    parser.add_argument(
        "--check", action="store_true", help="Dry-run: report only, no writes"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="JSON output"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    omo_src = script_dir.parents[1] / "projects" / "omo" / "src"
    if str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    from omo.omo_crystallizer import SkillCrystallizer

    state = _load_state()

    if args.check:
        from collections import defaultdict

        grouped: dict[str, list] = defaultdict(list)
        for b in state["beliefs"]:
            grouped[b.get("topic", "general")].append(b)

        ready = {t: len(bl) for t, bl in grouped.items() if len(bl) >= 2}
        waiting = {t: len(bl) for t, bl in grouped.items() if len(bl) < 2}

        if args.json_output:
            print(
                json.dumps(
                    {
                        "total_beliefs": len(state["beliefs"]),
                        "ready_to_crystallize": ready,
                        "waiting": waiting,
                    },
                    indent=2,
                )
            )
        else:
            print("=" * 65)
            print("  SEMA Skill Crystallizer — CHECK MODE (dry-run)")
            print("=" * 65)
            print(f"  Total beliefs: {len(state['beliefs'])}")
            if ready:
                print(f"\n  Ready to crystallize ({len(ready)} topics):")
                for t, c in ready.items():
                    print(f"    [{c} beliefs] {t}")
            if waiting:
                print(f"\n  Below threshold ({len(waiting)} topics):")
                for t, c in waiting.items():
                    print(f"    [{c} belief(s)] {t}")
            print()
        return 0

    crystallizer = SkillCrystallizer()
    result = crystallizer.check_and_crystallize(
        beliefs=state["beliefs"],
        lessons=state.get("lessons", []),
        contexts=state.get("contexts", []),
    )

    if args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print("  SEMA Skill Crystallizer (BET-Y1Q2-T6-06)")
        print("=" * 65)
        print(f"  Beliefs scanned: {result['total_beliefs']}")
        print(f"  Crystallized:    {result['crystallized_count']}")
        for sk in result.get("crystallized", []):
            print(
                f"    [OK] {sk['topic']} -> {sk['file']} "
                f"({sk['count']} beliefs, {sk['lessons']} lessons)"
            )
        for sk in result.get("skipped", []):
            print(f"    [--] {sk['topic']}: {sk['reason']} ({sk['count']})")
        print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
