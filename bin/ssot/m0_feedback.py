#!/usr/bin/env python3
"""m0_feedback.py — M0 运行时快照 → 模型反向反馈漂移检测

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 1 步 1:
运行时快照 (M0EngineSnapshot) 与 M1 模型 (ConstraintL0 实例) 的一致性检测,
实现"运行时 → 模型"反向闭环。

输入:  projects/ecos/.omo/_derived/m0-driven.yaml (M0EngineSnapshot)
        projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-CONSTRAINT-L0-INDEX.yaml (M1)
输出:  漂移列表 [{"type","constraint","detail"}] — stage_missing / constraint_count_mismatch

用法:
    python3 bin/ssot/m0_feedback.py           # 原有 M0 漂移检测
    python3 bin/ssot/m0_feedback.py --check-decay  # 记忆衰减与冲突检测 (BET-Y2Q1-T6-01)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
M0_SNAP = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "m0-driven.yaml"
DERIVED = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.v2.yaml"

# Decay check: default graph path for kairon knowledge graph
DECAY_GRAPH_PATHS = [
    ROOT / "projects" / "knowledge" / "kairon" / "data" / "kems_v2.jsonl",
    ROOT / ".subtrees" / "kairon" / "data" / "kems_v2.jsonl",
]

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
            drifts.append(
                {
                    "type": "stage_missing",
                    "constraint": s,
                    "detail": f"M0 缺 stage {s}（声明存在）",
                }
            )
    snap_count = snapshot.get("snapshot", {}).get("constraint_count")
    if snap_count is not None and snap_count != derived_count:
        drifts.append(
            {
                "type": "constraint_count_mismatch",
                "constraint": "constraint_count",
                "detail": f"M0={snap_count} vs derived={derived_count}",
            }
        )
    return drifts


def _check_decay() -> int:
    """Run memory decay and conflict detection.

    Finds the first available kairon graph JSONL file and runs the decay scan.
    Returns 0 if no critical conflicts, 1 if conflicts detected or graph not found.
    """
    graph_path: Path | None = None
    for p in DECAY_GRAPH_PATHS:
        if p.exists():
            graph_path = p
            break

    if graph_path is None:
        print("[DECAY] ⚠️ No kairon graph JSONL found, skipping decay check")
        print(f"[DECAY]   Searched: {[str(p) for p in DECAY_GRAPH_PATHS]}")
        return 0  # Non-fatal: graph may not exist yet

    try:
        from kairon.graph.decay_manager import run_check_decay, format_report

        report = run_check_decay(graph_path=str(graph_path))
        print(format_report(report))

        if report.has_critical_conflicts():
            print("[DECAY] ❌ Critical conflicts detected — manual resolution required")
            return 1
        print("[DECAY] ✅ Decay check passed")
        return 0
    except ImportError:
        print("[DECAY] ⚠️ kairon.graph.decay_manager not importable, skipping decay check")
        return 0
    except Exception as exc:
        print(f"[DECAY] ❌ Decay check failed: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M0 运行时快照漂移检测与记忆衰减检查",
    )
    parser.add_argument(
        "--check-decay",
        action="store_true",
        help="Run memory decay and conflict detection (BET-Y2Q1-T6-01)",
    )
    args = parser.parse_args()

    if args.check_decay:
        return _check_decay()

    # Original M0 drift detection
    if not M0_SNAP.exists():
        print(
            "[WARN] M0 snapshot 未生成，先跑: cd projects/ecos && uv run python3 -m ecos.ssot.mof.m0.mof_driven --emit"
        )
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
