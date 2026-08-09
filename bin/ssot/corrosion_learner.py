#!/usr/bin/env python3
"""corrosion_learner.py — 腐化学习（Wave 2）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2:
腐化率驱动的 ontology 自动修正建议——消费 m0_feedback/semantic_diff 的漂移
输出，给出优先级排序的修正动作。

用法:
    python3 bin/ssot/corrosion_learner.py --drifts <drifts.json>
"""

import argparse
import json
import sys
from pathlib import Path


def analyze_drifts(drifts: list[dict]) -> dict:
    """按类型归类漂移，返回计数汇总。"""
    summary = {}
    for d in drifts:
        t = d.get("type", "unknown")
        summary[t] = summary.get(t, 0) + 1
    summary["total"] = len(drifts)
    return summary


def rank_corrections(drifts: list[dict]) -> list[dict]:
    """漂移 → 优先级排序的修正建议。

    规则:
    - constraint_count_mismatch: high — 需重新生成派生面
    - stage_missing: medium — 需补 M0 快照 stage
    - 其他: low — 记录待审
    """
    if not drifts:
        return []
    corrections = []
    for d in drifts:
        t = d.get("type", "unknown")
        if t == "constraint_count_mismatch":
            corrections.append({"priority": "high", "type": t, "constraint": d.get("constraint"),
                                "action": "重新生成派生面（gen-l0-constraints.py）"})
        elif t == "stage_missing":
            corrections.append({"priority": "medium", "type": t, "constraint": d.get("constraint"),
                                "action": f"补 M0 快照 stage {d.get('constraint')}"})
        else:
            corrections.append({"priority": "low", "type": t, "constraint": d.get("constraint"),
                                "action": "记录待审（人工确认）"})
    order = {"high": 0, "medium": 1, "low": 2}
    corrections.sort(key=lambda c: order.get(c["priority"], 3))
    return corrections


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drifts", required=True, help="漂移 JSON 文件路径")
    args = ap.parse_args()
    path = Path(args.drifts)
    if not path.exists():
        print(f"[FAIL] 漂移文件不存在: {path}", file=sys.stderr)
        return 1
    drifts = json.loads(path.read_text(encoding="utf-8"))
    summary = analyze_drifts(drifts)
    corrections = rank_corrections(drifts)
    print(json.dumps({"summary": summary, "corrections": corrections},
                     ensure_ascii=False, indent=1))
    return 1 if corrections else 0


if __name__ == "__main__":
    raise SystemExit(main())
