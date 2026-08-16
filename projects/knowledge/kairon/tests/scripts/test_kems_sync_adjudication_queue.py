from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
KOS_SRC_DIR = Path(__file__).resolve().parents[2] / "packages" / "kos" / "src"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(KOS_SRC_DIR))

from kems_sync_adjudication_queue import sync_queue  # type: ignore[reportMissingImports]
from kos.kems import AdjudicationStore


def test_sync_queue_persists_redacted_inventory_idempotently(tmp_path: Path) -> None:
    docs_root = tmp_path / "Documents"
    inbox = docs_root / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "2026-auto-apple-mail.md").write_text("private source stays outside the queue", encoding="utf-8")
    database_path = tmp_path / "adjudication.sqlite"
    evidence_path = tmp_path / "evidence" / "queue.jsonl"

    first = sync_queue(docs_root, database_path, evidence_path)
    second = sync_queue(docs_root, database_path, evidence_path)

    assert first["sample_count"] == 1
    assert first["inserted_count"] == 1
    assert second["inserted_count"] == 0
    assert database_path.is_file()
    assert evidence_path.stat().st_mode & 0o777 == 0o600
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["scenario_id"] == "private-source-review-v1"
    assert "private source" not in evidence_path.read_text(encoding="utf-8")
    assert AdjudicationStore(database_path).list_items(status="pending")[0]["sample_id"].startswith("sample-")


def test_sync_queue_does_not_mutate_existing_metadata(tmp_path: Path) -> None:
    docs_root = tmp_path / "Documents"
    inbox = docs_root / "_inbox"
    inbox.mkdir(parents=True)
    source = inbox / "2026-auto-apple-mail.md"
    source.write_text("first", encoding="utf-8")
    database_path = tmp_path / "adjudication.sqlite"
    evidence_path = tmp_path / "queue.jsonl"
    sync_queue(docs_root, database_path, evidence_path)

    source.write_text("changed", encoding="utf-8")

    try:
        sync_queue(docs_root, database_path, evidence_path)
    except ValueError as exc:
        assert "different metadata" in str(exc)
    else:
        raise AssertionError("source hash changes must not silently mutate an existing sample")
