#!/usr/bin/env python3
"""m0_feedback.py — M0 运行时快照 → 模型反向反馈漂移检测

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 1 步 1:
运行时快照 (M0EngineSnapshot) 与 M1 模型 (ConstraintL0 实例) 的一致性检测,
实现"运行时 → 模型"反向闭环。

输入:  projects/ecos/.omo/_derived/m0-driven.yaml (M0EngineSnapshot)
        projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-CONSTRAINT-L0-INDEX.yaml (M1)
输出:  漂移列表 [{"type","constraint","detail"}] — stage_missing / constraint_count_mismatch

用法:
    python3 bin/ssot/m0_feedback.py
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
M0_SNAP = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "m0-driven.yaml"
DERIVED = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.v2.yaml"

EXPECTED_STAGES = ("stage1", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7")


def m0_drift(snapshot: dict, derived_count: int, expected_stages: tuple = EXPECTED_STAGES) -> list[dict]:
    """检测 M0 快照与派生面的漂移。

    规则:
    1. M0 缺失声明的 stage → stage_missing
    2. M0 约束计数与派生面不符 → constraint_count_mismatch
    """
    drifts: list[dict] = []
    stages = snapshot.get("snapshot", {}).get("stages", [])
    stage_ids = {s.get("id") for s in stages if isinstance(s, dict)}
    for s in expected_stages:
        if s not in stage_ids:
            drifts.append({"type": "stage_missing", "constraint": s,
                           "detail": f"M0 缺 stage {s}（声明存在）"})
    snap_count = snapshot.get("snapshot", {}).get("constraint_count")
    if snap_count is not None and snap_count != derived_count:
        drifts.append({"type": "constraint_count_mismatch", "constraint": "constraint_count",
                       "detail": f"M0={snap_count} vs derived={derived_count}"})
    return drifts


def main() -> int:
    if not M0_SNAP.exists():
        print("[WARN] M0 snapshot 未生成，先跑: cd projects/ecos && uv run python3 -m ecos.ssot.mof.m0.mof_driven --emit")
        return 1
    snap = yaml.safe_load(M0_SNAP.read_text(encoding="utf-8"))
    derived_count = len(yaml.safe_load(DERIVED.read_text(encoding="utf-8")).get("constraints", []))
    drifts = m0_drift(snap, derived_count)
    for d in drifts:
        print(f"[DRIFT] {d['type']}: {d['constraint']} — {d['detail']}")
    if not drifts:
        print("[OK] M0 ↔ 派生面无漂移")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
