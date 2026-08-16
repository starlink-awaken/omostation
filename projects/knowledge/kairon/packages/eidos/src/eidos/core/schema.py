from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from kairon_utils import atomic_write_json


class FieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    URL = "url"
    PATH = "path"
    LIST = "list"
    MAP = "map"
    REF = "ref"


def _field_type_from_value(value: Any) -> FieldType | None:
    if value is None:
        return None
    if isinstance(value, FieldType):
        return value
    return FieldType(value)


@dataclass
class SchemaField:
    name: str
    field_type: FieldType
    required: bool = False
    description: str | None = None
    default: Any = None
    ref_schema: str | None = None
    item_type: FieldType | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "required": self.required,
            "description": self.description,
            "default": self.default,
            "ref_schema": self.ref_schema,
            "item_type": self.item_type.value if self.item_type else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaField:
        ft = _field_type_from_value(data["field_type"])
        assert ft is not None, f"field_type is required for field {data.get('name', '?')}"
        return cls(
            name=data["name"],
            field_type=ft,
            required=bool(data.get("required", False)),
            description=data.get("description"),
            default=data.get("default"),
            ref_schema=data.get("ref_schema"),
            item_type=_field_type_from_value(data.get("item_type")),
        )


@dataclass
class Schema:
    name: str
    version: str
    description: str | None = None
    fields: dict[str, SchemaField] = field(default_factory=dict)
    extends: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "fields": {key: value.to_dict() for key, value in self.fields.items()},
            "extends": list(self.extends),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schema:
        return cls(
            name=data["name"],
            version=data["version"],
            description=data.get("description"),
            fields={key: SchemaField.from_dict(value) for key, value in data.get("fields", {}).items()},
            extends=list(data.get("extends", [])),
            metadata=dict(data.get("metadata", {})),
        )

    def _field_json_schema(self, field_def: SchemaField) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": field_def.field_type.value}
        if field_def.description is not None:
            schema["description"] = field_def.description
        if field_def.default is not None:
            schema["default"] = field_def.default
        if field_def.field_type == FieldType.REF and field_def.ref_schema:
            schema["$ref"] = f"#/definitions/{field_def.ref_schema}"
        if field_def.field_type == FieldType.LIST and field_def.item_type is not None:
            schema["items"] = {"type": field_def.item_type.value}
        return schema

    def to_json_schema(self) -> dict[str, Any]:
        properties = {name: self._field_json_schema(field_def) for name, field_def in self.fields.items()}
        required = [name for name, field_def in self.fields.items() if field_def.required]
        result: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": self.name,
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if self.description:
            result["description"] = self.description
        if required:
            result["required"] = required
        if self.extends:
            result["extends"] = list(self.extends)
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, data: str) -> Schema:
        return cls.from_dict(json.loads(data))

    @classmethod
    def from_json_file(cls, path: str | Path) -> Schema:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


class SchemaRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, Schema] = {}
        self._schemas = self._registry

    def register(self, schema: Schema) -> None:
        self._registry[schema.name] = schema

    def get(self, name: str) -> Schema | None:
        return self._registry.get(name)

    def list_types(self) -> list[str]:
        return sorted(self._registry)

    def save(self, path: str | Path | None = None) -> str:
        """Save all registered schemas to a JSON file.

        Uses Schema.to_dict() for full field fidelity (preserves ref_schema,
        item_type, default, expand). Appends a `_format_version` for forward
        compatibility.

        Args:
            path: Output path (default: ~/.eidos/registry.json)

        Returns:
            Path to saved file
        """
        if path is None:
            path = DEFAULT_REGISTRY_PATH
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "_format_version": "1",
            "schemas": {name: s.to_dict() for name, s in self._registry.items()},
        }
        atomic_write_json(path, data)
        return str(path)

    @classmethod
    def load(cls, path: str | Path | None = None) -> SchemaRegistry:
        """Load schemas from a JSON file.

        Reads schemas serialized by SchemaRegistry.save() (full field
        fidelity). Also tolerant of the legacy v0 format for migration.
        """
        if path is None:
            path = DEFAULT_REGISTRY_PATH
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        registry = cls()

        raw_schemas = data.get("schemas", {})

        # Detect legacy v0 format (flat dict, no schema-level to_dict)
        # Legacy: fields is a list of flat dicts (lost ref_schema/item_type/default)
        # Modern: fields is a dict of SchemaField.to_dict() (full fidelity)
        first: dict[str, Any] = next(iter(raw_schemas.values()), {})
        fields_raw = first.get("fields", {})
        is_legacy_format = isinstance(fields_raw, list)

        for name, sdata in raw_schemas.items():
            if is_legacy_format:
                schema = cls._legacy_dict_to_schema(name, sdata)
            else:
                schema = Schema.from_dict(sdata)
            registry.register(schema)
        return registry

    @staticmethod
    def _legacy_dict_to_schema(name: str, sdata: dict) -> Schema:
        """Convert a legacy v0 serialized schema dict to a Schema object."""
        from eidos.core.schema import FieldType, Schema, SchemaField

        valid_field_types = [e.value for e in FieldType]
        fields: dict[str, SchemaField] = {}
        for fd in sdata.get("fields", []):
            ft = FieldType(fd["field_type"]) if fd.get("field_type") in valid_field_types else FieldType.STRING
            fields[fd["name"]] = SchemaField(
                name=fd["name"],
                field_type=ft,
                required=fd.get("required", True),
                description=fd.get("description", ""),
            )
        return Schema(
            name=sdata["name"],
            version=sdata.get("version", "1.0"),
            description=sdata.get("description", ""),
            fields=fields,
        )

    def _ensure_storage(self) -> None:
        """Ensure the storage directory exists."""
        DEFAULT_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

    def validate(self, schema_name: str, data: dict[str, Any], strict: bool = True) -> Any:
        from eidos.core.validator import Validator

        return Validator(self).validate_object(schema_name, data, strict=strict)


# ── Schema Migration ──


class SchemaMigration:
    """Represents a single migration step from a source schema version to a target.

    A migration transforms data instances from one schema version to another
    through a user-supplied callable.  The callable receives the old data dict
    and must return the new data dict.
    """

    def __init__(
        self,
        from_version: str,
        to_version: str,
        description: str = "",
        transform: Callable | None = None,
    ) -> None:
        self.from_version = from_version
        self.to_version = to_version
        self.description = description
        self.transform = transform  # callable(data: dict) -> dict

    def apply(self, data: dict) -> dict:
        if self.transform is not None:
            return cast("dict[Any, Any]", self.transform(data))
        return data


# In-memory migration registry
_SCHEMA_MIGRATIONS: dict[str, list[SchemaMigration]] = {}


def register_migration(schema_name: str, migration: SchemaMigration) -> None:
    """Register a migration for a schema name."""
    _SCHEMA_MIGRATIONS.setdefault(schema_name, []).append(migration)


def get_migrations(schema_name: str) -> list[SchemaMigration]:
    """Get all registered migrations for a schema name, sorted by version."""
    return sorted(_SCHEMA_MIGRATIONS.get(schema_name, []), key=lambda m: m.from_version)


def migrate_schema_instance(
    schema_name: str,
    data: dict,
    from_version: str,
    to_version: str,
) -> dict:
    """Migrate a single data instance through registered migrations.

    Applies all migration steps that fall within [from_version, to_version)
    in ascending version order.

    Args:
        schema_name: The schema name (e.g. 'KnowledgeCard')
        data: The data dict to migrate
        from_version: Source schema version (e.g. '1.0')
        to_version: Target schema version (e.g. '2.0')

    Returns:
        The migrated data dict

    Raises:
        EidosError: SCHEMA_MIGRATION_FAILED if a transform fails
    """
    from eidos.errors import EidosError, ErrorCode

    migrations = get_migrations(schema_name)
    current = data

    for m in migrations:
        # Skip migrations whose from_version is before our starting point
        # or whose to_version exceeds the target
        if m.from_version < from_version:
            continue
        if m.to_version > to_version:
            break  # beyond target, stop

        try:
            current = m.apply(current)
            # Stamp the version onto the migrated data for traceability
            current["_migrated_version"] = m.to_version
        except Exception as exc:
            raise EidosError(
                ErrorCode.SCHEMA_MIGRATION_FAILED,
                f"Migration {m.from_version}→{m.to_version} failed for schema '{schema_name}': {exc}",
                {"schema": schema_name, "from": m.from_version, "to": m.to_version},
            ) from exc

    return current


DEFAULT_REGISTRY_PATH = Path.home() / ".eidos" / "registry.json"
