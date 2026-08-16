"""Tests for ForgettingCurveEngine — Ebbinghaus spaced-repetition engine."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalMemberAccess=false

import math
import time

import pytest
from eidos.forgetting_curve_engine import ForgettingCurveEngine, MemoryItem


def test_store_and_get():
    engine = ForgettingCurveEngine()
    engine.store("mem-1", "Some knowledge", importance=0.8)
    item = engine.get_item("mem-1")
    assert item is not None
    assert item.item_id == "mem-1"
    assert item.content == "Some knowledge"
    assert item.strength == 1.0
    assert item.review_count == 1
    assert item.importance == 0.8


def test_store_and_get_nonexistent():
    engine = ForgettingCurveEngine()
    assert engine.get_item("nonexistent") is None


def test_review_increases_strength():
    engine = ForgettingCurveEngine()
    engine.store("mem-1", "Test", importance=1.0)
    item = engine.get_item("mem-1")
    original_strength = item.strength

    engine.review("mem-1")
    assert item.review_count == 2
    assert item.strength > original_strength


def test_review_unknown_item_noop():
    engine = ForgettingCurveEngine()
    engine.review("does-not-exist")  # should not raise


def test_retention_nonexistent_is_zero():
    engine = ForgettingCurveEngine()
    assert engine.get_retention("ghost") == 0.0


def test_retention_at_creation_is_one():
    engine = ForgettingCurveEngine()
    engine.store("mem-1", "Fresh knowledge")
    retention = engine.get_retention("mem-1", current_time=time.time())
    assert retention == pytest.approx(1.0, abs=0.01)


def test_retention_decays_over_time():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("mem-1", "Decaying knowledge")
    # set last_reviewed to NOW
    item = engine.get_item("mem-1")
    item.last_reviewed = now

    # After t = stability (strength*review_count=1.0*1=1 second), retention = e^{-1}
    later = now + 1.0
    r = engine.get_retention("mem-1", current_time=later)
    assert r == pytest.approx(math.exp(-1.0), abs=0.01)


def test_retention_never_below_zero():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("mem-1", "Old knowledge")
    item = engine.get_item("mem-1")
    item.last_reviewed = now
    item.strength = 0.01  # minimal strength

    far_future = now + 999999.0
    r = engine.get_retention("mem-1", current_time=far_future)
    assert r >= 0.0


def test_due_for_review():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("mem-1", "Strong", importance=1.0)
    engine.store("mem-2", "Weak", importance=0.1)
    item = engine.get_item("mem-2")
    item.last_reviewed = now - 9999  # very old

    due = engine.get_due_for_review(threshold=0.5, current_time=now)
    assert "mem-2" in due
    assert "mem-1" not in due


def test_decay_all_reduces_strength():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("mem-1", "Test", importance=0.5)
    item = engine.get_item("mem-1")
    item.last_reviewed = now - 10  # 10 seconds ago
    original_strength = item.strength

    engine.decay_all(current_time=now)
    assert item.strength < original_strength


def test_decay_all_floor():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("mem-1", "Minimal", importance=0.01)
    item = engine.get_item("mem-1")
    item.strength = 0.01
    item.last_reviewed = now - 99999

    engine.decay_all(current_time=now)
    assert item.strength >= 0.01


def test_prune_forgotten():
    engine = ForgettingCurveEngine()
    now = time.time()
    engine.store("keep", "Good", importance=1.0)
    engine.store("forget", "Bad", importance=0.01)
    item = engine.get_item("forget")
    item.last_reviewed = now - 99999

    pruned = engine.prune_forgotten(threshold=0.5, current_time=now)
    assert "forget" in pruned
    assert "keep" not in pruned
    assert engine.get_item("forget") is None


def test_stats_empty():
    engine = ForgettingCurveEngine()
    stats = engine.get_stats()
    assert stats["total_items"] == 0
    assert stats["avg_retention"] == 0.0


def test_stats_with_items():
    engine = ForgettingCurveEngine()
    engine.store("mem-1", "A")
    stats = engine.get_stats()
    assert stats["total_items"] == 1
    assert stats["avg_retention"] > 0.0


def test_memory_item_defaults():
    item = MemoryItem(item_id="test", content="hello")
    assert item.strength == 1.0
    assert item.review_count == 0
    assert item.importance == 0.5
