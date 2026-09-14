"""Eidos MCP Server — expose schema modeling as MCP tools.

Usage:
    python -m eidos.mcp_server          # stdio MCP mode
    python -m eidos.mcp_server --help   # show help
"""

from __future__ import annotations

import json
import sys
from typing import Any

FORMAT_VERSION = "eidos-v1"


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)


def handle_list(params: dict | None = None) -> dict:
    """List all registered schemas."""
    from eidos.core.schema import SchemaRegistry
    from eidos.meta import list_types

    sr = SchemaRegistry()
    schemas: list[dict[str, Any]] = []

    registry = getattr(sr, "_registry", None)
    if isinstance(registry, dict) and registry:
        for name, schema in registry.items():
            fields_payload: list[dict[str, Any]] = []
            fields = getattr(schema, "fields", None)
            if isinstance(fields, dict):
                iterable: Any = fields.values()
            else:
                iterable = fields or []
            for field in iterable:
                fields_payload.append(
                    {
                        "name": getattr(field, "name", ""),
                        "type": getattr(
                            getattr(field, "field_type", None), "value", str(getattr(field, "field_type", ""))
                        ),
                        "required": getattr(field, "required", True),
                        "description": getattr(field, "description", ""),
                    }
                )
            schemas.append({"name": name, "fields": fields_payload})

    if not schemas:
        types = list_types()
        schemas = [{"name": t.get("type_name", ""), "meta_type": t.get("meta_type", "")} for t in types]

    return {"format_version": FORMAT_VERSION, "schemas": schemas, "count": len(schemas)}


def handle_validate(params: dict | None = None) -> dict:
    """Validate a JSON object against an Eidos schema type."""
    from eidos.types import Fact, KnowledgeCard, OntologyNode

    payload = params or {}
    data = payload.get("data", "{}")
    schema_type = payload.get("schema_type", "KnowledgeCard")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            return {
                "format_version": FORMAT_VERSION,
                "is_valid": False,
                "errors": [f"Invalid JSON: {exc}"],
                "type": schema_type,
            }

    st = str(schema_type).upper().replace(" ", "_")
    try:
        if "CARD" in st or "KNOWLEDGE" in st:
            card = KnowledgeCard.from_dict(data)
            errors = card.validate()
            return {
                "format_version": FORMAT_VERSION,
                "is_valid": len(errors) == 0,
                "errors": errors,
                "type": "KnowledgeCard",
            }
        if "FACT" in st:
            fact = Fact.from_dict(data)
            errors = fact.validate()
            return {"format_version": FORMAT_VERSION, "is_valid": len(errors) == 0, "errors": errors, "type": "Fact"}
        if "NODE" in st or "ONTOLOGY" in st:
            node = OntologyNode.from_dict(data)
            errors = node.validate()
            return {
                "format_version": FORMAT_VERSION,
                "is_valid": len(errors) == 0,
                "errors": errors,
                "type": "OntologyNode",
            }
        return {"format_version": FORMAT_VERSION, "is_valid": True, "errors": [], "type": schema_type}
    except Exception as exc:
        return {"format_version": FORMAT_VERSION, "is_valid": False, "errors": [str(exc)], "type": schema_type}


def handle_meta(params: dict | None = None) -> dict:
    """Get the Eidos meta-model definition (8 MetaType × 4 MetaRelationType)."""
    from eidos.meta import MetaRelationType, MetaType, list_types

    return {
        "format_version": FORMAT_VERSION,
        "meta_types": [{"value": mt.value, "name": mt.display_name()} for mt in MetaType],
        "meta_relations": [mr.value for mr in MetaRelationType],
        "type_mappings": list_types(),
    }


def handle_migrate(params: dict | None = None) -> dict:
    """Run Schema Migration on a data instance."""
    from eidos.core.schema import get_migrations, migrate_schema_instance

    payload = params or {}
    schema_name = payload.get("schema_name", "")
    data = payload.get("data", {})
    from_version = payload.get("from_version", "1.0")
    to_version = payload.get("to_version", "2.0")

    if not schema_name:
        return {"format_version": FORMAT_VERSION, "error": "schema_name is required", "migrated": False}
    if not data:
        return {"format_version": FORMAT_VERSION, "error": "data is required", "migrated": False}

    migrations = get_migrations(schema_name)
    if not migrations:
        return {
            "format_version": FORMAT_VERSION,
            "schema": schema_name,
            "migrated": False,
            "note": f"No migrations registered for '{schema_name}'",
            "from_version": from_version,
            "to_version": to_version,
            "data": data,
        }

    try:
        result = migrate_schema_instance(schema_name, data, from_version, to_version)
        return {
            "format_version": FORMAT_VERSION,
            "schema": schema_name,
            "migrated": True,
            "from_version": from_version,
            "to_version": result.get("_migrated_version", to_version),
            "data": result,
        }
    except Exception as exc:
        return {
            "format_version": FORMAT_VERSION,
            "schema": schema_name,
            "migrated": False,
            "error": str(exc),
            "from_version": from_version,
            "to_version": to_version,
            "data": data,
        }


def handle_migration_list(params: dict | None = None) -> dict:
    """List all registered schema migrations."""
    from eidos.core.schema import _SCHEMA_MIGRATIONS

    result = []
    for schema_name, migrations in _SCHEMA_MIGRATIONS.items():
        for m in migrations:
            result.append(
                {
                    "schema": schema_name,
                    "from_version": m.from_version,
                    "to_version": m.to_version,
                    "description": m.description,
                }
            )
    return {"format_version": FORMAT_VERSION, "migrations": result, "count": len(result)}


def handle_define(params: dict | None = None) -> dict:
    """Define a new schema."""
    from eidos.core.schema import FieldType, Schema, SchemaField, SchemaRegistry

    payload = params or {}
    name = payload.get("name", "Untitled")
    fields_data = payload.get("fields", [])

    fields: list[SchemaField] = []
    for fd in fields_data:
        ft = FieldType.STRING
        try:
            ft = FieldType(str(fd.get("type", "string")))
        except Exception:
            pass
        fields.append(
            SchemaField(
                name=fd["name"],
                field_type=ft,
                required=fd.get("required", True),
                description=fd.get("description", ""),
            )
        )

    schema = Schema(name=name, version="1.0", fields={f.name: f for f in fields})
    sr = SchemaRegistry()
    sr.register(schema)
    return {"format_version": FORMAT_VERSION, "name": name, "fields": len(fields), "status": "registered"}


def handle_export(params: dict | None = None) -> dict:
    """Export a registered Schema to a standardized cross-project format.

    The output is a JSON document that downstream tools (ontoderive, kronos,
    minerva) can consume for schema-aware data processing.
    """
    from eidos.registry import create_registry

    payload = params or {}
    schema_names = payload.get("names", [])

    registry = create_registry()

    if schema_names:
        schemas = [registry.get(n) for n in schema_names if registry.get(n)]
    else:
        schemas = [registry.get(n) for n in registry.list_types()]

    if not schemas:
        return {"format_version": FORMAT_VERSION, "exported": [], "count": 0}

    export: list[dict] = []
    for schema in schemas:
        if schema is None:
            continue
        fields_export = []
        for field_name, field in schema.fields.items():
            fields_export.append(
                {
                    "name": field_name,
                    "type": field.field_type.value if field.field_type else "string",
                    "required": field.required,
                    "description": field.description,
                    "ref_schema": field.ref_schema,
                    "item_type": field.item_type.value if field.item_type else None,
                    "default": field.default,
                }
            )
        export.append(
            {
                "name": schema.name,
                "version": schema.version,
                "description": schema.description,
                "fields": fields_export,
                "extends": list(schema.extends),
                "$schema": schema.to_json_schema(),
            }
        )

    return {"format_version": FORMAT_VERSION, "exported": export, "count": len(export)}


TOOLS: dict[str, dict[str, Any]] = {
    "eidos_list": {
        "func": handle_list,
        "description": "列出所有已注册 Schema",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "eidos_validate": {
        "func": handle_validate,
        "description": "校验 JSON 对象是否符合指定 Schema 类型",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "JSON string or object stringified"},
                "schema_type": {"type": "string", "description": "KnowledgeCard, Fact, OntologyNode"},
            },
            "additionalProperties": True,
        },
    },
    "eidos_meta": {
        "func": handle_meta,
        "description": "查询元模型 (8 MetaType × 4 MetaRelationType)",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "eidos_define": {
        "func": handle_define,
        "description": "定义新的 Schema",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "fields": {"type": "array"},
            },
            "required": ["name", "fields"],
            "additionalProperties": True,
        },
    },
    "eidos_export": {
        "func": handle_export,
        "description": "导出 Schema 为跨项目标准化格式（JSON Schema + 字段详情）",
        "input_schema": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要导出的 Schema 名称列表（为空则导出全部）",
                }
            },
            "additionalProperties": False,
        },
    },
    "eidos_migrate": {
        "func": handle_migrate,
        "description": "对数据实例执行 Schema 版本迁移（从 from_version → to_version）",
        "input_schema": {
            "type": "object",
            "properties": {
                "schema_name": {"type": "string", "description": "Schema 名称"},
                "data": {"type": "object", "description": "待迁移的数据实例"},
                "from_version": {"type": "string", "description": "源版本号（default: 1.0）"},
                "to_version": {"type": "string", "description": "目标版本号（default: 2.0）"},
            },
            "required": ["schema_name", "data"],
            "additionalProperties": False,
        },
    },
    "eidos_migration_list": {
        "func": handle_migration_list,
        "description": "列出所有已注册的 Schema 迁移",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def _call_tool(name: str, params: dict | None = None) -> dict:
    if name not in TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    result = TOOLS[name]["func"](params or {})
    return {"content": [{"type": "text", "text": _dump(result)}]}


def _list_tools() -> dict:
    return {
        "tools": [
            {"name": name, "description": info["description"], "inputSchema": info["input_schema"]}
            for name, info in TOOLS.items()
        ]
    }


def _handle_fastmcp() -> Any:
    try:
        from fastmcp import FastMCP
    except Exception:
        return None

    app = FastMCP("eidos-mcp")

    @app.tool(name="eidos_list", description=TOOLS["eidos_list"]["description"])
    def _eidos_list() -> dict:
        return handle_list({})

    @app.tool(name="eidos_validate", description=TOOLS["eidos_validate"]["description"])
    def _eidos_validate(data: str = "{}", schema_type: str = "KnowledgeCard") -> dict:
        return handle_validate({"data": data, "schema_type": schema_type})

    @app.tool(name="eidos_meta", description=TOOLS["eidos_meta"]["description"])
    def _eidos_meta() -> dict:
        return handle_meta({})

    @app.tool(name="eidos_define", description=TOOLS["eidos_define"]["description"])
    def _eidos_define(name: str = "Untitled", fields: list[dict] | None = None) -> dict:
        return handle_define({"name": name, "fields": fields or []})

    @app.tool(name="eidos_export", description=TOOLS["eidos_export"]["description"])
    def _eidos_export(names: list[str] | None = None) -> dict:
        return handle_export({"names": names or []})

    @app.tool(name="eidos_migrate", description=TOOLS["eidos_migrate"]["description"])
    def _eidos_migrate(
        schema_name: str,
        data: dict,
        from_version: str = "1.0",
        to_version: str = "2.0",
    ) -> dict:
        return handle_migrate(
            {"schema_name": schema_name, "data": data, "from_version": from_version, "to_version": to_version}
        )

    @app.tool(name="eidos_migration_list", description=TOOLS["eidos_migration_list"]["description"])
    def _eidos_migration_list() -> dict:
        return handle_migration_list({})

    return app


def handle_mcp_request(request: dict) -> dict:
    """Process an MCP JSON-RPC request."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        if method in {"initialize"}:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "0.1.0",
                    "serverInfo": {"name": "eidos-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            }

        if method in {"list_tools", "tools/list"}:
            return {"jsonrpc": "2.0", "id": req_id, "result": _list_tools()}

        if method.startswith("call_tool/"):
            tool_name = method.split("/", 1)[1]
            return {"jsonrpc": "2.0", "id": req_id, "result": _call_tool(tool_name, params.get("data", {}))}

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return {"jsonrpc": "2.0", "id": req_id, "result": _call_tool(str(tool_name), arguments)}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": str(exc)}}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": str(exc)}}


def main() -> None:
    """Run Eidos MCP server (FastMCP stdio).

    协议统一 (2026-07-13): app 在 _handle_fastmcp() 注册 7 @app.tool, main 走 app.run()
    (FastMCP stdio, 和 iris/kronos/ontoderive 一致). fastmcp 必装 (eidos[mcp] optional dep).
    """
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Eidos MCP Server (FastMCP stdio)")
        print("")
        print("Tools:")
        for name, info in TOOLS.items():
            print(f"  {name}: {info['description']}")
        return

    app = _handle_fastmcp()
    if app is None:
        print("FastMCP required. Install: uv sync --extra mcp  (or pip install fastmcp)", file=sys.stderr)
        sys.exit(1)
    app.run()
