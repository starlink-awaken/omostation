"""KOS ↔ Eidos contract pilot tests."""

from __future__ import annotations

import json

from kos.commands import ingest


def test_validate_eidos_uses_protocol_contract_validator(tmp_path, monkeypatch):
    payload = {
        "id": "kc-1",
        "title": "Card title",
        "content": "Body",
        "source": "unit-test",
        "source_type": "test",
        "schema_type": "KnowledgeCard",
    }
    path = tmp_path / "card.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(
        ingest,
        "validate_contract_payload",
        lambda contract_name, data: ["contract failed"],
        raising=False,
    )

    is_valid, errors = ingest._validate_eidos(path, "KnowledgeCard")

    assert is_valid is False
    assert errors == ["contract failed"]
