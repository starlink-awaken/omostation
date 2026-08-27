from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "bin" / "ssot"))

from corrosion_learner import analyze_drifts, rank_corrections


def test_analyze_drifts_classifies() -> None:
    drifts = [
        {"type": "stage_missing", "constraint": "stage7", "detail": "M0 缺 stage7"},
        {
            "type": "constraint_count_mismatch",
            "constraint": "count",
            "detail": "M0=100 vs derived=137",
        },
    ]
    result = analyze_drifts(drifts)
    assert result["stage_missing"] == 1
    assert result["constraint_count_mismatch"] == 1
    assert result["total"] == 2


def test_rank_corrections_prioritizes() -> None:
    drifts = [
        {
            "type": "constraint_count_mismatch",
            "constraint": "count",
            "detail": "M0=100 vs derived=137",
        },
        {"type": "stage_missing", "constraint": "stage3", "detail": "M0 缺 stage3"},
        {"type": "stage_missing", "constraint": "stage7", "detail": "M0 缺 stage7"},
    ]
    corrections = rank_corrections(drifts)
    assert corrections[0]["priority"] == "high"
    assert any("重新生成派生面" in correction["action"] for correction in corrections)


def test_no_drifts_no_corrections() -> None:
    assert rank_corrections([]) == []
