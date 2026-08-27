from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eidos.core.schema import FieldType, SchemaField, SchemaRegistry


@dataclass
class ValidationError:
    field: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "message": self.message}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationError:
        return cls(field=data["field"], message=data["message"])


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"is_valid": self.is_valid, "errors": [error.to_dict() for error in self.errors]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationResult:
        return cls(
            is_valid=bool(data.get("is_valid", False)),
            errors=[ValidationError.from_dict(error) for error in data.get("errors", [])],
        )


class Validator:
    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry

    def validate_object(self, schema_type: str, data: dict[str, Any], strict: bool = True) -> ValidationResult:
        schema = self.registry.get(schema_type)
        if schema is None:
            return ValidationResult(
                False, [ValidationError(field="__schema__", message=f"Unknown schema type: {schema_type}")]
            )

        errors: list[ValidationError] = []
        for field_name, field_def in schema.fields.items():
            if field_def.required and field_name not in data:
                errors.append(ValidationError(field=field_name, message="Missing required field"))
                continue
            if field_name in data and not self._matches_type(data[field_name], field_def):
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Expected {field_def.field_type.value}",
                    )
                )

        if strict:
            extra_fields = sorted(set(data) - set(schema.fields))
            for field_name in extra_fields:
                errors.append(ValidationError(field=field_name, message="Unexpected field"))

        result = ValidationResult(is_valid=not errors, errors=errors)

        if not result.is_valid:
            try:
                import httpx

                # 触发 X1 告警并强锚定到 L0 SSB Immutable Log
                httpx.post(
                    "http://127.0.0.1:8080/v1/tools/call",
                    json={
                        "name": "append_ssb_log",
                        "arguments": {
                            "event_type": "DATA_POISON_ATTEMPT",
                            "agent_name": "eidos.validator",
                            "summary": f"Eidos blocked malformed data for schema '{schema_type}'",
                            "detail": f"Errors: {[e.to_dict() for e in errors]}",
                        },
                    },
                    timeout=0.5,  # 快进快出
                )
            except Exception:
                pass  # Ignore anchoring errors to not crash the validator

        return result

    def validate_card(self, data: dict[str, Any], strict: bool = True) -> ValidationResult:
        return self.validate_object("card", data, strict=strict)

    def validate_fact(self, data: dict[str, Any], strict: bool = True) -> ValidationResult:
        return self.validate_object("fact", data, strict=strict)

    def validate_node(self, data: dict[str, Any], strict: bool = True) -> ValidationResult:
        return self.validate_object("node", data, strict=strict)

    def _matches_type(self, value: Any, field_def: SchemaField) -> bool:
        field_type = field_def.field_type
        if field_type == FieldType.STRING:
            return isinstance(value, str)
        if field_type == FieldType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if field_type == FieldType.NUMBER:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if field_type == FieldType.BOOLEAN:
            return isinstance(value, bool)
        if field_type == FieldType.DATETIME:
            return isinstance(value, str) and self._is_datetime(value)
        if field_type == FieldType.URL:
            return isinstance(value, str) and value.startswith(("http://", "https://"))
        if field_type == FieldType.PATH:
            return isinstance(value, str)
        if field_type == FieldType.LIST:
            return isinstance(value, list)
        if field_type == FieldType.MAP:
            return isinstance(value, dict)
        if field_type == FieldType.REF:
            return isinstance(value, str)
        return False

    def _is_datetime(self, value: str) -> bool:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
