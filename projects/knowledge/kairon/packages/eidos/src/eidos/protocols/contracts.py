"""Serialized payload contracts for cross-project Eidos integrations."""

from __future__ import annotations

from typing import Any

from eidos.core.schema import FieldType, Schema, SchemaField, SchemaRegistry


def _build_registry() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register(
        Schema(
            name="knowledge-card-v0.3",
            version="0.3",
            description="Canonical serialized KnowledgeCard payload contract.",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
                "content": SchemaField(name="content", field_type=FieldType.STRING, required=True),
                "source": SchemaField(name="source", field_type=FieldType.STRING, required=True),
                "source_type": SchemaField(name="source_type", field_type=FieldType.STRING, required=True),
                "schema_type": SchemaField(name="schema_type", field_type=FieldType.STRING, required=True),
                "tags": SchemaField(name="tags", field_type=FieldType.LIST, item_type=FieldType.STRING),
                "relations": SchemaField(name="relations", field_type=FieldType.LIST, item_type=FieldType.MAP),
                "created_at": SchemaField(name="created_at", field_type=FieldType.STRING),
                "updated_at": SchemaField(name="updated_at", field_type=FieldType.STRING),
            },
            metadata={"owner": "eidos.protocols", "surface": "cross-project-pilot"},
        )
    )
    registry.register(
        Schema(
            name="fact-v0.3",
            version="0.3",
            description="Canonical serialized Fact payload contract.",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "subject": SchemaField(name="subject", field_type=FieldType.STRING, required=True),
                "predicate": SchemaField(name="predicate", field_type=FieldType.STRING, required=True),
                "object": SchemaField(name="object", field_type=FieldType.STRING, required=True),
                "confidence": SchemaField(name="confidence", field_type=FieldType.NUMBER),
                "source_card_id": SchemaField(name="source_card_id", field_type=FieldType.STRING),
                "derived_from": SchemaField(name="derived_from", field_type=FieldType.STRING),
            },
            metadata={"owner": "eidos.protocols", "surface": "cross-project-pilot"},
        )
    )
    return registry


CONTRACT_REGISTRY = _build_registry()


def _matches_type(value: Any, field_type: FieldType, item_type: FieldType | None = None) -> bool:
    if field_type in {FieldType.STRING, FieldType.DATETIME, FieldType.URL, FieldType.PATH, FieldType.REF}:
        return isinstance(value, str)
    if field_type == FieldType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == FieldType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == FieldType.BOOLEAN:
        return isinstance(value, bool)
    if field_type == FieldType.MAP:
        return isinstance(value, dict)
    if field_type == FieldType.LIST:
        if not isinstance(value, list):
            return False
        if item_type is None:
            return True
        return all(_matches_type(item, item_type) for item in value)
    return True


def validate_contract_payload(contract_name: str, payload: dict[str, Any]) -> list[str]:
    """Validate a serialized payload against a named contract."""

    schema = CONTRACT_REGISTRY.get(contract_name)
    if schema is None:
        return [f"unknown contract: {contract_name}"]

    errors: list[str] = []
    for field_name, field_def in schema.fields.items():
        if field_def.required and field_name not in payload:
            errors.append(f"{field_name} is required")
            continue
        if field_name not in payload:
            continue
        value = payload[field_name]
        if not _matches_type(value, field_def.field_type, field_def.item_type):
            errors.append(f"{field_name} must be {field_def.field_type.value}")
    return errors
