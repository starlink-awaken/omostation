# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
import json

from eidos.schema import FieldType, Schema, SchemaField, SchemaRegistry


def make_card_schema() -> Schema:
    return Schema(
        name="card",
        version="1.0.0",
        description="Card schema",
        fields={
            "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
            "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
            "rank": SchemaField(name="rank", field_type=FieldType.INTEGER, required=False, default=1),
        },
    )


def test_field_type_enum_values():
    assert FieldType.STRING.value == "string"
    assert FieldType.INTEGER.value == "integer"
    assert FieldType.NUMBER.value == "number"
    assert FieldType.BOOLEAN.value == "boolean"
    assert FieldType.DATETIME.value == "datetime"
    assert FieldType.URL.value == "url"
    assert FieldType.PATH.value == "path"
    assert FieldType.LIST.value == "list"
    assert FieldType.MAP.value == "map"
    assert FieldType.REF.value == "ref"


def test_schema_field_creation():
    field = SchemaField(
        name="title",
        field_type=FieldType.STRING,
        required=True,
        description="Title field",
        default="Untitled",
        ref_schema="document",
        item_type=FieldType.STRING,
    )

    assert field.name == "title"
    assert field.field_type == FieldType.STRING
    assert field.required is True
    assert field.description == "Title field"
    assert field.default == "Untitled"
    assert field.ref_schema == "document"
    assert field.item_type == FieldType.STRING

    roundtrip = SchemaField.from_dict(field.to_dict())
    assert roundtrip == field


def test_schema_to_json_schema():
    schema = make_card_schema()
    json_schema = schema.to_json_schema()

    assert json_schema["title"] == "card"
    assert json_schema["type"] == "object"
    assert json_schema["properties"]["id"]["type"] == "string"
    assert json_schema["properties"]["rank"]["type"] == "integer"
    assert "id" in json_schema["required"]
    assert "title" in json_schema["required"]


def test_schema_roundtrip_json(tmp_path):
    schema = make_card_schema()
    path = tmp_path / "schema.json"
    path.write_text(schema.to_json(), encoding="utf-8")

    loaded = Schema.from_json_file(path)
    assert loaded == schema

    parsed = Schema.from_json(json.dumps(schema.to_dict()))
    assert parsed == schema


def test_schema_registry_register_and_get():
    registry = SchemaRegistry()
    schema = make_card_schema()

    registry.register(schema)

    assert registry.get("card") == schema
    assert registry.list_types() == ["card"]


def test_schema_registry_validate_valid_data():
    registry = SchemaRegistry()
    registry.register(make_card_schema())

    result = registry.validate("card", {"id": "c1", "title": "Hello", "rank": 2})

    assert result.is_valid is True
    assert result.errors == []


def test_schema_registry_validate_invalid_data():
    registry = SchemaRegistry()
    registry.register(make_card_schema())

    result = registry.validate("card", {"id": "c1", "extra": True})

    assert result.is_valid is False
    assert any(error.field == "title" for error in result.errors)
    assert any(error.field == "extra" for error in result.errors)
