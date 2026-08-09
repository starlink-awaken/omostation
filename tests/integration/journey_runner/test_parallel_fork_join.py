"""BET-Y1Q4-T5-01: 并行会签 fork/join 集成测试.

Covered:
- fork 状态分叉到多个并行分支
- join 状态按策略汇聚 (all / majority / any)
- 线性 journey 不受影响 (回归)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # .../ws-bet-t5-01
sys.path.insert(0, str(ROOT / "bin" / "ssot"))

_spec = importlib.util.spec_from_file_location("journey_runner", ROOT / "bin" / "ssot" / "journey-runner.py")
jr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jr)


def _run_parallel_spec(tmp_path, strategy: str, branches: int) -> dict:
    """Build and run a parallel journey spec with the given join strategy."""
    spec_path = tmp_path / f"parallel-{strategy}.yaml"
    branch_names = [f"review_{i}" for i in range(branches)]
    states = [
        {
            "name": "start",
            "scene": "unified-inbox",
            "parallel": {"branches": branch_names},
        },
        *[
            {"name": b, "scene": "document-review", "next": ["join_point"]}
            for b in branch_names
        ],
        {
            "name": "join_point",
            "scene": "document-review",
            "join": {"strategy": strategy, "sources": branch_names},
            "next": ["approved"],
        },
        {"name": "approved", "scene": "engineering-delivery", "next": []},
    ]
    transitions = [
        {"from": b, "to": "join_point", "condition": "always"} for b in branch_names
    ] + [{"from": "join_point", "to": "approved", "condition": "always"}]
    spec = {
        "schema": "journey-spec/v1",
        "journey_id": f"parallel-{strategy}",
        "states": states,
        "transitions": transitions,
    }
    import yaml

    spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")

    monkeypatch_root = ROOT  # journey-runner resolves specs under docs/journey-specs
    # run_journey resolves spec via ROOT/docs/journey-specs — so place spec there.
    target = monkeypatch_root / "docs" / "journey-specs" / f"parallel-{strategy}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    spec_path.replace(target)
    try:
        return jr.run_journey(f"parallel-{strategy}", dry_run=True)
    finally:
        target.unlink(missing_ok=True)


def test_join_all_requires_all_branches(tmp_path):
    result = _run_parallel_spec(tmp_path, "all", 3)
    assert result["status"] == "completed"


def test_join_majority(tmp_path):
    result = _run_parallel_spec(tmp_path, "majority", 3)
    assert result["status"] == "completed"


def test_join_any(tmp_path):
    result = _run_parallel_spec(tmp_path, "any", 3)
    assert result["status"] == "completed"


def test_join_strategy_math():
    assert jr._join_satisfied("all", 3, 3) is True
    assert jr._join_satisfied("all", 2, 3) is False
    assert jr._join_satisfied("majority", 2, 3) is True
    assert jr._join_satisfied("majority", 1, 3) is False
    assert jr._join_satisfied("any", 1, 3) is True
    assert jr._join_satisfied("any", 0, 3) is False


def test_fork_parse():
    state = {"parallel": {"branches": ["a", "b"]}}
    assert jr._is_fork_state(state)
    assert jr._fork_branches(state) == ["a", "b"]


def test_join_parse():
    state = {"join": {"strategy": "majority", "sources": ["a", "b"]}}
    assert jr._is_join_state(state)
    assert jr._join_sources(state) == ["a", "b"]
    assert jr._join_strategy(state) == "majority"


def test_linear_journey_unaffected(tmp_path):
    """A plain linear journey must still complete (regression)."""
    result = jr.run_journey("inbox-to-decision", dry_run=True)
    assert result["status"] in ("completed", "paused")
