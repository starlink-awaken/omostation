#!/usr/bin/env python3
"""auto-merge-lane-policy — lane → auto/manual 映射 (F3, auto-PR ISA D1).

复用 change-lane-check.classify (DRY, 不重写分类). 给定 PR 文件 paths, 判定
auto-merge 候选 (auto-PR ISA F3 lane 白名单):
  auto:    docs / code / config / submodule_pointer / governance_code / other
  manual:  governance_state (.omo/) / runtime_snapshot + 架构文件 (ARCHITECTURE.md/LAYER-INDEX.md)
  mixed:   含 manual → 整 PR manual (保守, 任一 manual 不 auto)

用法:
  python3 bin/auto-merge-lane-policy.py <path1> <path2> ...   # 判定 paths
  python3 bin/auto-merge-lane-policy.py --staged               # 判定 staged 文件
  python3 bin/auto-merge-lane-policy.py --json <paths>         # 机器可读

退出码: 0 = auto (可 auto-merge) / 1 = manual (需人工)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# 复用 change-lane-check.classify (文件名含连字符, 用 importlib 加载)
_CLC_PATH = Path(__file__).parent / "change-lane-check.py"
_spec = importlib.util.spec_from_file_location("_change_lane_check", _CLC_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
classify = _mod.classify
submodule_paths = _mod.submodule_paths

# lane → auto/manual (auto-PR ISA F3 定义, ISC-13..21)
LANE_POLICY: dict[str, str] = {
    "docs": "auto",
    "code": "auto",
    "config": "auto",
    "submodule_pointer": "auto",
    "governance_code": "auto",
    "other": "auto",
    "governance_state": "manual",   # .omo/ 治理状态, 不可逆, 人工
    "runtime_snapshot": "manual",   # runtime/ 运行时快照, 敏感, 人工
}

# 架构文件强制 manual (即使 docs lane, 5+4+1 架构变更 ISC-20 不可 auto)
ARCHITECTURE_FILES = {"ARCHITECTURE.md", "LAYER-INDEX.md"}


def lane_for(path: str, submods: set[str]) -> tuple[str, str]:
    """返回 (lane, policy). 架构文件强制 manual (ISC-20)."""
    if Path(path).name in ARCHITECTURE_FILES:
        return ("docs", "manual")  # lane 仍是 docs, 但 policy 强制 manual
    lane = classify(path, submods)
    return (lane, LANE_POLICY.get(lane, "manual"))


def decide(paths: list[str]) -> dict:
    submods = submodule_paths()
    entries: list[dict] = []
    policies: set[str] = set()
    lanes: set[str] = set()
    for p in paths:
        lane, policy = lane_for(p, submods)
        entries.append({"path": p, "lane": lane, "policy": policy})
        policies.add(policy)
        lanes.add(lane)
    # mixed: 含 manual → 整体 manual (保守, Anti: 治理/架构不 auto)
    decision = "manual" if (not entries or "manual" in policies) else "auto"
    return {
        "decision": decision,
        "lanes": sorted(lanes),
        "policies": sorted(policies),
        "entry_count": len(entries),
        "entries": entries,
        "reason": (
            "含 manual lane/架构文件 → manual (保守, ISC-22 Anti)"
            if decision == "manual"
            else "全 auto lane → auto-merge 候选"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="auto-merge lane policy (F3, auto-PR ISA D1)")
    parser.add_argument("paths", nargs="*", help="文件 paths 判定")
    parser.add_argument("--staged", action="store_true", help="判定 staged 文件")
    parser.add_argument("--json", action="store_true", help="机器可读 JSON")
    args = parser.parse_args(argv)

    if args.staged:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=False
        )
        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    else:
        paths = args.paths
    if not paths:
        parser.error("需 paths 或 --staged")

    outcome = decide(paths)
    if args.json:
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
    else:
        print(f"decision: {outcome['decision']}")
        print(f"lanes: {outcome['lanes']}")
        print(f"reason: {outcome['reason']}")
        for e in outcome["entries"]:
            print(f"  [{e['policy']:6}] {e['lane']:20} {e['path']}")
    return 0 if outcome["decision"] == "auto" else 1


if __name__ == "__main__":
    sys.exit(main())
