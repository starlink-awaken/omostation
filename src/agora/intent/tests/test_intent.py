"""Tests for the intent model (BET-Y2Q1-T3-02)."""

from __future__ import annotations

import time

import pytest

from agora.intent import IntentModel, IntentResult, Priority, Prioritizer, ScoreWeights


class _FakeTaskSource:
    def __init__(self, tasks):
        self._tasks = tasks

    def get_active_tasks(self):
        return self._tasks


class TestPrioritizer:
    def test_score_task_with_deadline_soon(self):
        now = int(time.time() * 1000)
        t = {
            "id": "t1",
            "title": "Ship release",
            "deadline_ms": now + 86_400_000,  # 1 day
            "updated_ms": now,
            "blocks": ["t2"],
        }
        p = Prioritizer()
        item = p.score_task(t)
        assert item.score > 50
        assert item.priority >= Priority.HIGH
        assert "deadline" in item.rationale

    def test_score_task_no_deadline(self):
        now = int(time.time() * 1000)
        t = {"id": "t2", "title": "Refactor", "updated_ms": now}
        p = Prioritizer()
        item = p.score_task(t)
        assert 10 < item.score < 60

    def test_rank_ordering(self):
        now = int(time.time() * 1000)
        p = Prioritizer()
        items = [
            p.score_task({"id": "a", "title": "Low", "deadline_ms": now + 86_400_000 * 7}),
            p.score_task({"id": "b", "title": "High", "deadline_ms": now + 3_600_000}),
        ]
        ranked = p.rank(items)
        assert ranked[0].id == "b"
        assert ranked[1].id == "a"

    def test_priority_bands(self):
        assert Priority.from_score(85) == Priority.CRITICAL
        assert Priority.from_score(65) == Priority.HIGH
        assert Priority.from_score(45) == Priority.MEDIUM
        assert Priority.from_score(25) == Priority.LOW
        assert Priority.from_score(5) == Priority.BACKLOG

    def test_custom_weights(self):
        w = ScoreWeights(deadline=1.0, goal_alignment=0, dependency=0, recency=0, effort=0)
        p = Prioritizer(w)
        now = int(time.time() * 1000)
        soon = p.score_task({"id": "x", "title": "Soon", "deadline_ms": now + 3_600_000})
        later = p.score_task({"id": "y", "title": "Later", "deadline_ms": now + 86_400_000 * 7})
        assert soon.score > later.score


class TestIntentModel:
    def test_whats_most_important_empty(self):
        model = IntentModel(task_source=[])
        result = model.whats_most_important()
        assert isinstance(result, IntentResult)
        assert result.items == []
        assert "No active" in result.context_summary

    def test_whats_most_important_ranks(self):
        now = int(time.time() * 1000)
        tasks = [
            {"id": "t1", "title": "Old low", "deadline_ms": now + 86_400_000 * 7, "updated_ms": now - 86_400_000 * 3},
            {"id": "t2", "title": "Urgent", "deadline_ms": now + 3_600_000, "updated_ms": now, "blocks": ["t3"]},
        ]
        model = IntentModel(task_source=_FakeTaskSource(tasks))
        result = model.whats_most_important(top_n=5)
        assert result.top is not None
        assert result.top.id == "t2"
        assert result.top.priority >= Priority.HIGH

    def test_to_dict_shape(self):
        now = int(time.time() * 1000)
        model = IntentModel(task_source=[{"id": "t1", "title": "Test", "updated_ms": now}])
        d = model.whats_most_important().to_dict()
        assert "generated_at" in d
        assert "items" in d
        assert d["items"][0]["priority"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "BACKLOG")

    def test_top_n_limit(self):
        now = int(time.time() * 1000)
        tasks = [{"id": f"t{i}", "title": f"Task {i}", "updated_ms": now} for i in range(10)]
        model = IntentModel(task_source=tasks)
        result = model.whats_most_important(top_n=3)
        assert len(result.items) == 3
