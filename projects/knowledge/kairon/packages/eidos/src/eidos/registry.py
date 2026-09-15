from __future__ import annotations

from eidos.core.schema import FieldType, Schema, SchemaField, SchemaRegistry


def create_registry() -> SchemaRegistry:
    registry = SchemaRegistry()

    registry.register(
        Schema(
            name="KnowledgeCard",
            version="1.0.0",
            description="Concrete knowledge card schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
                "content": SchemaField(name="content", field_type=FieldType.STRING, required=True),
                "source": SchemaField(name="source", field_type=FieldType.STRING, required=True),
                "source_type": SchemaField(name="source_type", field_type=FieldType.STRING, required=True),
                "schema_type": SchemaField(name="schema_type", field_type=FieldType.STRING, required=True),
                "tags": SchemaField(name="tags", field_type=FieldType.LIST, required=False, item_type=FieldType.STRING),
                "relations": SchemaField(
                    name="relations", field_type=FieldType.LIST, required=False, item_type=FieldType.MAP
                ),
                "created_at": SchemaField(name="created_at", field_type=FieldType.STRING, required=False),
                "updated_at": SchemaField(name="updated_at", field_type=FieldType.STRING, required=False),
            },
        )
    )

    registry.register(
        Schema(
            name="Fact",
            version="1.0.0",
            description="Concrete fact schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "subject": SchemaField(name="subject", field_type=FieldType.STRING, required=True),
                "predicate": SchemaField(name="predicate", field_type=FieldType.STRING, required=True),
                "object": SchemaField(name="object", field_type=FieldType.STRING, required=True),
                "confidence": SchemaField(name="confidence", field_type=FieldType.NUMBER, required=False, default=1.0),
                "source_card_id": SchemaField(name="source_card_id", field_type=FieldType.STRING, required=False),
                "derived_from": SchemaField(name="derived_from", field_type=FieldType.STRING, required=False),
            },
        )
    )

    registry.register(
        Schema(
            name="OntologyNode",
            version="1.0.0",
            description="Concrete ontology node schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "name": SchemaField(name="name", field_type=FieldType.STRING, required=True),
                "node_type": SchemaField(name="node_type", field_type=FieldType.STRING, required=True),
                "parent": SchemaField(name="parent", field_type=FieldType.STRING, required=False),
                "properties": SchemaField(name="properties", field_type=FieldType.MAP, required=False),
                "aliases": SchemaField(
                    name="aliases", field_type=FieldType.LIST, required=False, item_type=FieldType.STRING
                ),
                "description": SchemaField(name="description", field_type=FieldType.STRING, required=False),
            },
        )
    )

    return registry


registry = create_registry()
