"""Tests for pipeline_models dataclass invariants (slots + __post_init__)."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import pytest
from ontoderive.pipeline_models import (
    BatchItem,
    BatchResult,
    ProgressInfo,
    StepResult,
    StepStatus,
)

# ── ProgressInfo ───────────────────────────────────────────────


def test_progress_info_accepts_zero_state():
    p = ProgressInfo(step_name="x", current=0, total=0)
    assert p.message == ""


def test_progress_info_rejects_negative_current():
    with pytest.raises(ValueError, match="current must be >= 0"):
        ProgressInfo(step_name="x", current=-1, total=0)


def test_progress_info_rejects_current_above_total():
    with pytest.raises(ValueError, match="cannot exceed total"):
        ProgressInfo(step_name="x", current=5, total=2)


# ── StepResult ──────────────────────────────────────────────────


def test_step_result_defaults_have_counters():
    r = StepResult(step_name="x")
    assert r.items_processed == 0
    assert r.items_failed == 0


def test_step_result_rejects_items_failed_above_processed():
    with pytest.raises(ValueError, match="cannot exceed"):
        StepResult(step_name="x", items_processed=2, items_failed=3)


def test_step_result_rejects_negative_items_processed():
    with pytest.raises(ValueError, match="items_processed must be >= 0"):
        StepResult(step_name="x", items_processed=-1)


def test_step_result_rejects_end_before_start():
    with pytest.raises(ValueError, match="cannot precede"):
        StepResult(step_name="x", start_time=10.0, end_time=5.0)


def test_step_result_accepts_valid_counters():
    r = StepResult(step_name="x", items_processed=5, items_failed=2)
    assert r.items_failed <= r.items_processed


# ── BatchItem ──────────────────────────────────────────────────


def test_batch_item_requires_non_empty_id():
    with pytest.raises(ValueError, match="id must be a non-empty string"):
        BatchItem(id="", data={})


def test_batch_item_rejects_non_dict_data():
    with pytest.raises(ValueError, match="data must be a dict"):
        BatchItem(id="x", data=["not", "dict"])  # type: ignore[arg-type]


def test_batch_item_rejects_non_dict_metadata():
    with pytest.raises(ValueError, match="metadata must be a dict"):
        BatchItem(id="x", data={}, metadata="nope")  # type: ignore[arg-type]


def test_batch_item_slots_forbid_arbitrary_attributes():
    item = BatchItem(id="x", data={})
    with pytest.raises(AttributeError):
        item.not_a_field = "nope"  # type: ignore[attr-defined]


# ── BatchResult ────────────────────────────────────────────────


def test_batch_result_default_state_is_consistent():
    r = BatchResult()
    assert r.completed == 0
    assert r.failed == 0


def test_batch_result_rejects_negative_counters():
    with pytest.raises(ValueError, match="counters must be non-negative"):
        BatchResult(succeeded=-1)


def test_batch_result_rejects_completed_above_total():
    with pytest.raises(ValueError, match="cannot exceed item count"):
        BatchResult(total=1, completed=2, items=[])


def test_batch_result_rejects_duration_negative():
    with pytest.raises(ValueError, match="duration must be >= 0"):
        BatchResult(duration=-1.0)


def test_batch_result_accepts_consistent_counters():
    items = [BatchItem(id=f"x{i}", data={}) for i in range(3)]
    r = BatchResult(total=3, completed=3, items=items, duration=0.5)
    assert r.completed == 3
    assert r.duration == 0.5


# ── StepStatus ─────────────────────────────────────────────────


def test_step_status_enum_is_str_subclass():
    # str-based enums are JSON-friendly.
    assert StepStatus.COMPLETED == "completed"
    assert str(StepStatus.FAILED) == "StepStatus.FAILED"
