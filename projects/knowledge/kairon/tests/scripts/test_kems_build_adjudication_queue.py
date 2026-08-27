from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kems_build_adjudication_queue import DEFAULT_SCENARIO_ID, QueueInputError, build_queue, write_queue


def _docs(tmp_path: Path) -> Path:
    inbox = tmp_path / "docs" / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "2026-auto-apple-mail.md").write_text("private body", encoding="utf-8")
    (inbox / "2026-auto-iphone-sms.md").write_text("private sms", encoding="utf-8")
    return inbox.parent


def test_queue_is_redacted_pending_and_deterministic(tmp_path: Path) -> None:
    docs_root = _docs(tmp_path)
    first = build_queue(docs_root, scenario_id="mail-review", split="test")
    second = build_queue(docs_root, scenario_id="mail-review", split="test")

    assert first == second
    assert len(first) == 2
    assert all(row["queue_schema"] == "kems.adjudication-queue.v1" for row in first)
    assert all(row["annotation_status"] == "pending" for row in first)
    assert all(row["labels"] == {} for row in first)
    assert all("private body" not in json.dumps(row) for row in first)
    assert all(str(row["source_ref"]).startswith("vault://redacted/") for row in first)


def test_default_scenario_matches_private_source_contract() -> None:
    assert DEFAULT_SCENARIO_ID == "private-source-review-v1"


def test_write_queue_is_atomic_and_private_free(tmp_path: Path) -> None:
    output = tmp_path / "queue" / "adjudication.jsonl"
    write_queue(build_queue(_docs(tmp_path), scenario_id="review", split="shadow"), output)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert not list(output.parent.glob(".*.tmp"))
    assert output.stat().st_mode & 0o077 == 0


def test_queue_rejects_empty_source_inventory(tmp_path: Path) -> None:
    (tmp_path / "docs" / "_inbox").mkdir(parents=True)
    with pytest.raises(QueueInputError, match="no controlled source"):
        build_queue(tmp_path / "docs", scenario_id="review", split="shadow")


def test_queue_rejects_invalid_split(tmp_path: Path) -> None:
    with pytest.raises(QueueInputError, match="split is unsupported"):
        build_queue(_docs(tmp_path), scenario_id="review", split="production")
