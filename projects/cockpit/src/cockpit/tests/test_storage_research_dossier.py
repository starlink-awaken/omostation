from __future__ import annotations

from pathlib import Path

import cockpit.storage as storage


def test_research_dossier_includes_relations_and_publications(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    source_a = storage.save_research("source a", "summary a", "body a", source_count=1)
    source_b = storage.save_research("source b", "summary b", "body b", source_count=2)
    digest_id = storage.save_research("digest c", "summary c", "body c", source_count=3)

    storage.add_research_relations([source_a, source_b], digest_id, "digest")
    storage.save_published_report(digest_id, "brief", "/tmp/report.md")

    dossier = storage.get_research_dossier(digest_id)

    assert dossier is not None
    assert dossier["record"]["id"] == digest_id
    assert {item["id"] for item in dossier["parents"]} == {source_a, source_b}
    assert dossier["children"] == []
    assert dossier["publications"][0]["style"] == "brief"
    assert dossier["publications"][0]["output_path"] == "/tmp/report.md"
