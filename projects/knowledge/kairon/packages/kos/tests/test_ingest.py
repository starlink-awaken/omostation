"""KOS ingest command tests."""

import json
from pathlib import Path
from types import SimpleNamespace

from kos.commands import ingest


def test_ingest_dry_run_counts_supported_files(tmp_path, capsys, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Hello\nworld\n", encoding="utf-8")
    (root / "raw.txt").write_text("plain text", encoding="utf-8")
    (root / "data.json").write_text('{"title": "JSON Title", "value": 1}', encoding="utf-8")
    (root / "skip.pdf").write_text("ignore me", encoding="utf-8")
    nested = root / "sub"
    nested.mkdir()
    (nested / "nested.md").write_text("# Nested\n", encoding="utf-8")

    monkeypatch.setattr(
        ingest, "_store_document", lambda record: (_ for _ in ()).throw(AssertionError("should not store in dry-run"))
    )

    result = ingest.ingest_command(SimpleNamespace(path=str(root), dry_run=True, verbose=False))
    out = capsys.readouterr().out

    assert result["ok"] is True
    assert result["found"] == 4
    assert result["indexed"] == 0
    assert result["skipped"] == 4
    assert "Found 4 files, indexed 0, skipped 4" in out


def test_ingest_classifies_md_txt_and_json(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Hello\nworld\n", encoding="utf-8")
    (root / "raw.txt").write_text("plain text", encoding="utf-8")
    (root / "data.json").write_text('{"title": "JSON Title", "value": 1}', encoding="utf-8")

    monkeypatch.setattr(ingest, "EIDOS_AVAILABLE", False)
    records = []
    monkeypatch.setattr(ingest, "_store_document", lambda record: records.append(record))

    result = ingest.ingest_command(SimpleNamespace(path=str(root), dry_run=False, verbose=False))

    assert result["found"] == 3
    assert result["indexed"] == 3
    kinds = {Path(r["source_path"]).name: r["kind"] for r in records}
    assert kinds["note.md"] == "KnowledgeCard"
    assert kinds["raw.txt"] == "RawDocument"
    assert kinds["data.json"] == "RawDocument"


def test_ingest_uses_eidos_when_available(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "data.json").write_text('{"title": "JSON Title", "value": 1}', encoding="utf-8")

    monkeypatch.setattr(ingest, "EIDOS_AVAILABLE", True)
    monkeypatch.setattr(ingest, "validate_object", lambda obj: True, raising=False)
    records = []
    monkeypatch.setattr(ingest, "_store_document", lambda record: records.append(record))

    ingest.ingest_command(SimpleNamespace(path=str(root), dry_run=False, verbose=False))

    assert records[0]["kind"] == "KnowledgeCard"
    assert '"eidos_validated": true' in records[0]["metadata_json"]


def test_ingest_assigns_canonical_meta_types(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "facts").mkdir(parents=True)
    (root / "inferences").mkdir()
    (root / "schemas").mkdir()
    (root / "processors").mkdir()
    (root / "facts" / "data.md").write_text("# Fact\n", encoding="utf-8")
    (root / "inferences" / "analysis.md").write_text("# Inference\n", encoding="utf-8")
    (root / "schemas" / "policy.json").write_text('{"title": "Policy"}', encoding="utf-8")
    (root / "processors" / "job.txt").write_text("processor notes", encoding="utf-8")

    monkeypatch.setattr(ingest, "EIDOS_AVAILABLE", False)
    records = []
    monkeypatch.setattr(ingest, "_store_document", lambda record: records.append(record))

    result = ingest.ingest_command(SimpleNamespace(path=str(root), dry_run=False, verbose=False))

    assert result["indexed"] == 4
    meta_types = {Path(r["source_path"]).name: json.loads(r["metadata_json"])["meta_type"] for r in records}
    assert meta_types["data.md"] == "fact"
    assert meta_types["analysis.md"] == "inference"
    assert meta_types["policy.json"] == "constraint"
    assert meta_types["job.txt"] == "processor"
