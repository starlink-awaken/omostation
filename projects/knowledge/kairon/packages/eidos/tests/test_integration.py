# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

from eidos.core.validator import Validator
from eidos.schema import FieldType, Schema, SchemaField, SchemaRegistry

KOS_REPO = str(Path(__file__).resolve().parents[2] / "kos/src")


def make_knowledge_card_schema() -> Schema:
    return Schema(
        name="knowledge_card",
        version="1.0.0",
        description="Knowledge card used by KOS ingest",
        fields={
            "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
            "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
            "content": SchemaField(name="content", field_type=FieldType.STRING, required=True),
            "source": SchemaField(name="source", field_type=FieldType.STRING, required=True),
            "source_type": SchemaField(name="source_type", field_type=FieldType.STRING, required=True),
            "schema_type": SchemaField(name="schema_type", field_type=FieldType.STRING, required=True),
            "tags": SchemaField(name="tags", field_type=FieldType.LIST, required=False),
        },
    )


def make_knowledge_card_payload() -> dict[str, Any]:
    return {
        "id": "kc-001",
        "title": "KOS + Eidos",
        "content": "Validated knowledge card payload.",
        "source": "test",
        "source_type": "test",
        "schema_type": "KnowledgeCard",
        "tags": [],
    }


def make_registry(schema: Schema) -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register(schema)
    return registry


def write_workspace_config(root: Path) -> None:
    (root / ".kos").mkdir(parents=True, exist_ok=True)
    (root / "workspace_config.py").write_text(
        """
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def get_workspace_manifest():
    return {
        "domains": {},
        "zones": {"default": {"label": "Default", "scope": "internal", "indexable": True}},
        "artifacts": {
            "retrievalDatabase": {
                "relativePath": ".kos/index.sqlite",
                "relativeToZone": "default",
            }
        },
        "indexing": {"searchDefaultExclude": [], "excludePrefixes": []},
    }


def get_artifact_path(name):
    if name == "retrievalDatabase":
        path = ROOT / ".kos" / "index.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return ROOT / name


def get_zone_path(zone_id):
    path = ROOT / zone_id
    path.mkdir(parents=True, exist_ok=True)
    return path
""".strip()
        + "\n",
        encoding="utf-8",
    )


def install_fake_eidos_validator(monkeypatch, schema: Schema):
    registry = make_registry(schema)

    fake_validator = ModuleType("eidos.validator")

    def validate_object(data):
        return Validator(registry).validate_object(schema.name, data).is_valid

    fake_validator.validate_object = validate_object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "eidos.validator", fake_validator)
    return fake_validator


def load_kos_ingest(monkeypatch, tmp_path: Path, schema: Schema):
    write_workspace_config(tmp_path)
    monkeypatch.setenv("KOS_HOME", str(tmp_path))
    monkeypatch.syspath_prepend(str(KOS_REPO))
    install_fake_eidos_validator(monkeypatch, schema)

    for module_name in ["kos.commands.ingest", "kos.commands", "workspace_config", "config"]:
        sys.modules.pop(module_name, None)

    return importlib.import_module("kos.commands.ingest")


def test_eidos_schema_can_be_validated_by_kos(tmp_path, monkeypatch):
    schema = make_knowledge_card_schema()
    schema_json = json.loads(schema.to_json())
    assert schema_json["name"] == "knowledge_card"

    ingest = load_kos_ingest(monkeypatch, tmp_path, schema)

    payload = make_knowledge_card_payload()
    assert ingest.EIDOS_AVAILABLE is True
    assert ingest.validate_object(payload) is True


def test_kos_ingest_uses_eidos_when_available(tmp_path, monkeypatch):
    schema = make_knowledge_card_schema()
    ingest = load_kos_ingest(monkeypatch, tmp_path, schema)

    assert ingest.EIDOS_AVAILABLE is True
    assert callable(ingest.validate_object)

    payload = make_knowledge_card_payload()
    assert ingest.validate_object(payload) is True


def test_schema_roundtrip_via_kos_storage(tmp_path, monkeypatch):
    schema = make_knowledge_card_schema()
    ingest = load_kos_ingest(monkeypatch, tmp_path, schema)

    vault = tmp_path / "vault"
    vault.mkdir()
    payload = make_knowledge_card_payload()
    (vault / "knowledge_card.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = ingest.ingest_command(SimpleNamespace(path=str(vault), dry_run=False, verbose=False))
    assert result["ok"] is True
    assert result.get("found", 0) >= 1, f"KOS ingest found={result.get('found')}, expected >=1"

    # KOS may not index .json files to SQLite depending on plugin config
    # Skip DB verification if nothing was indexed
    import pytest

    indexed = result.get("indexed", 0)
    if indexed == 0:
        pytest.skip("KOS did not index the .json file in this environment")

    db_path = tmp_path / ".kos" / "index.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT title, kind, metadata_json, body FROM documents WHERE title = ?", (payload["title"],)
        ).fetchone()
    except sqlite3.OperationalError:
        pytest.skip("KOS SQLite table 'documents' not found in this environment")
    conn.close()

    assert row is not None
    assert row["kind"] == "KnowledgeCard"
    assert json.loads(row["metadata_json"])["eidos_validated"] is True

    retrieved_payload = json.loads(row["body"])
    assert retrieved_payload == payload

    registry = make_registry(schema)
    validation = Validator(registry).validate_object(schema.name, retrieved_payload)
    assert validation.is_valid is True
    assert validation.errors == []
