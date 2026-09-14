# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
from eidos.core.validator import Validator
from eidos.schema import FieldType, Schema, SchemaField, SchemaRegistry


def make_registry() -> SchemaRegistry:
    registry = SchemaRegistry()

    registry.register(
        Schema(
            name="card",
            version="1.0.0",
            description="Card schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
                "count": SchemaField(name="count", field_type=FieldType.INTEGER, required=False),
            },
        )
    )

    registry.register(
        Schema(
            name="fact",
            version="1.0.0",
            description="Fact schema",
            fields={
                "subject": SchemaField(name="subject", field_type=FieldType.STRING, required=True),
                "value": SchemaField(name="value", field_type=FieldType.NUMBER, required=True),
            },
        )
    )

    registry.register(
        Schema(
            name="node",
            version="1.0.0",
            description="Node schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "type": SchemaField(name="type", field_type=FieldType.STRING, required=True),
            },
        )
    )

    return registry


def test_validate_valid_card_passes():
    validator = Validator(make_registry())

    result = validator.validate_card({"id": "c1", "title": "Card", "count": 3})

    assert result.is_valid is True
    assert result.errors == []


def test_validate_invalid_card_missing_required_field():
    validator = Validator(make_registry())

    result = validator.validate_card({"id": "c1"})

    assert result.is_valid is False
    assert any(error.field == "title" for error in result.errors)


def test_validate_valid_fact_passes():
    validator = Validator(make_registry())

    result = validator.validate_fact({"subject": "gravity", "value": 9.8})

    assert result.is_valid is True
    assert result.errors == []


def test_validate_fact_with_wrong_type_fails():
    validator = Validator(make_registry())

    result = validator.validate_fact({"subject": "gravity", "value": "9.8"})

    assert result.is_valid is False
    assert any(error.field == "value" for error in result.errors)


def test_validate_unknown_schema_type_fails():
    validator = Validator(make_registry())

    result = validator.validate_object("unknown", {"id": "x"})

    assert result.is_valid is False
    assert any("unknown" in error.message.lower() for error in result.errors)
