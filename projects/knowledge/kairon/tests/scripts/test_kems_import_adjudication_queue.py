from __future__ import annotations

from scripts.kems_import_adjudication_queue import read_queue


def test_read_queue_skips_blank_lines_and_preserves_redacted_records(tmp_path) -> None:
    path = tmp_path / "queue.jsonl"
    path.write_text('\n{"sample_id":"sample-1","source_ref":"vault://redacted/one"}\n', encoding="utf-8")

    assert read_queue(path) == [{"sample_id": "sample-1", "source_ref": "vault://redacted/one"}]
