"""Tests for omo_adjudication.py (BET-Y1Q1-T4-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from omo.omo_adjudication import (
    ADJUDICATION_SCHEMA,
    AdjudicationStore,
    VALID_VERDICTS,
)
from omo.omo_io import AppendOnlyLog


@pytest.fixture
def store(tmp_path: Path) -> AdjudicationStore:
    log_path = tmp_path / "adjudications.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = AppendOnlyLog(path=log_path, lock=None)
    return AdjudicationStore(log=log)


def test_record_accepted(store: AdjudicationStore):
    adj_id = store.record(
        decision_id="do-0001",
        verdict="accepted",
        adjudicator="operator-x",
        time_spent_seconds=12.5,
    )
    assert adj_id == "adj-0001"

    records = store.query(decision_id="do-0001")
    assert len(records) == 1
    assert records[0]["verdict"] == "accepted"
    assert records[0]["decision_id"] == "do-0001"
    assert records[0]["adjudicator"] == "operator-x"
    assert records[0]["schema_version"] == ADJUDICATION_SCHEMA


def test_record_modified_with_diff(store: AdjudicationStore):
    adj_id = store.record(
        decision_id="do-0002",
        verdict="modified",
        edit_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
        time_spent_seconds=45.0,
        notes="fixed variable naming",
    )
    assert adj_id == "adj-0001"

    records = store.query(verdict="modified")
    assert len(records) == 1
    assert "old" in records[0]["edit_diff"]
    assert records[0]["notes"] == "fixed variable naming"


def test_record_rejected(store: AdjudicationStore):
    store.record(
        decision_id="do-0003",
        verdict="rejected",
        notes="approach fundamentally wrong",
    )
    records = store.query(verdict="rejected")
    assert len(records) == 1
    assert records[0]["verdict"] == "rejected"


def test_invalid_verdict_raises(store: AdjudicationStore):
    with pytest.raises(ValueError, match="verdict must be one of"):
        store.record(decision_id="do-0001", verdict="maybe")


def test_multiple_records_increment_id(store: AdjudicationStore):
    id1 = store.record(decision_id="do-0001", verdict="accepted")
    id2 = store.record(decision_id="do-0002", verdict="rejected")
    id3 = store.record(decision_id="do-0003", verdict="modified")
    assert id1 == "adj-0001"
    assert id2 == "adj-0002"
    assert id3 == "adj-0003"


def test_query_by_decision_id(store: AdjudicationStore):
    store.record(decision_id="do-0001", verdict="accepted")
    store.record(decision_id="do-0002", verdict="rejected")
    store.record(decision_id="do-0001", verdict="modified")

    results = store.query(decision_id="do-0001")
    assert len(results) == 2
    assert all(r["decision_id"] == "do-0001" for r in results)


def test_query_limit(store: AdjudicationStore):
    for i in range(10):
        store.record(decision_id=f"do-{i:04d}", verdict="accepted")
    results = store.query(limit=3)
    assert len(results) == 3


def test_stats(store: AdjudicationStore):
    store.record(decision_id="do-0001", verdict="accepted")
    store.record(decision_id="do-0002", verdict="accepted")
    store.record(decision_id="do-0003", verdict="rejected")

    s = store.stats()
    assert s["total"] == 3
    assert s["accepted"] == 2
    assert s["rejected"] == 1
    assert s["modified"] == 0


def test_append_only_persistence(tmp_path: Path):
    log_path = tmp_path / "adjudications.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log1 = AppendOnlyLog(path=log_path, lock=None)
    store1 = AdjudicationStore(log=log1)
    store1.record(decision_id="do-0001", verdict="accepted")

    log2 = AppendOnlyLog(path=log_path, lock=None)
    store2 = AdjudicationStore(log=log2)
    records = store2.query()
    assert len(records) == 1
    assert records[0]["decision_id"] == "do-0001"
