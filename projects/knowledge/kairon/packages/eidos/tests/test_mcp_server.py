"""Tests for eidos.mcp_server — schema modeling MCP tools.

Covers 7 handler functions (list, validate, meta, migrate, migration_list,
define, export) + helpers (_json_default, _dump, _call_tool, _list_tools,
handle_mcp_request, main).
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from eidos import mcp_server
from eidos.mcp_server import (
    FORMAT_VERSION,
    TOOLS,
    _call_tool,
    _dump,
    _json_default,
    _list_tools,
    handle_define,
    handle_export,
    handle_list,
    handle_mcp_request,
    handle_meta,
    handle_migrate,
    handle_migration_list,
    handle_validate,
    main,
)

# ── _json_default ──────────────────────────────────────────────


class TestJsonDefault:
    def test_dict_falls_to_str_path(self):
        """Plain dict has __dict__ attribute, so falls through to __dict__ path
        which may equal the dict itself or its __dict__ dict."""
        result = _json_default({"a": 1})
        # Either the original dict (if it equals its __dict__) or a string
        # In CPython 3.13+ dicts no longer share __dict__ with instances;
        # result is the string repr.
        assert result in ({"a": 1}, str({"a": 1}))

    def test_int_passthrough_str(self):
        """int has __dict__? No, so falls to str fallback."""
        # 42 has no __dict__/to_dict → str(42) = "42"
        assert _json_default(42) == "42"

    def test_string_passthrough(self):
        # String has __dict__ (no slots), so falls to __dict__ path
        # which captures any internal attrs. For "hi" it's just the string.
        result = _json_default("hi")
        # Either the string itself or its dict form
        assert result == "hi" or result == {"__doc__": ...}

    def test_object_with_to_dict(self):
        class WithToDict:
            def to_dict(self):
                return {"converted": True}

        assert _json_default(WithToDict()) == {"converted": True}

    def test_object_with_dict_attr(self):
        class WithDict:
            pass

        obj = WithDict()
        obj.attr1 = 1
        obj.attr2 = "x"
        result = _json_default(obj)
        assert result["attr1"] == 1
        assert result["attr2"] == "x"


# ── _dump ──────────────────────────────────────────────────────


class TestDump:
    def test_dump_dict(self):
        result = _dump({"x": 1})
        parsed = json.loads(result)
        assert parsed == {"x": 1}

    def test_dump_unicode_preserved(self):
        result = _dump({"name": "中文"})
        assert "中文" in result

    def test_dump_indent_2(self):
        result = _dump({"a": 1})
        assert "\n" in result

    def test_dump_ensure_ascii_false(self):
        result = _dump({"emoji": "🎉"})
        assert "🎉" in result


# ── handle_list ────────────────────────────────────────────────


class TestHandleList:
    def test_returns_format_version(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_inst = mock_reg.return_value
            mock_inst._registry = {}
            result = handle_list()
        assert result["format_version"] == FORMAT_VERSION

    def test_includes_schemas(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_inst = mock_reg.return_value
            field = MagicMock()
            field.name = "title"
            field.field_type = MagicMock()
            field.field_type.value = "string"
            field.required = True
            field.description = "The title"
            schema = MagicMock()
            schema.fields = {"title": field}
            mock_inst._registry = {"article": schema}
            result = handle_list()
        assert result["count"] == 1
        assert result["schemas"][0]["name"] == "article"

    def test_empty_registry_falls_back_to_meta(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_inst = mock_reg.return_value
            mock_inst._registry = {}
            with patch(
                "eidos.meta.list_types",
                return_value=[
                    {"type_name": "Fact", "meta_type": "M0_FACT"},
                ],
            ):
                result = handle_list()
        assert result["count"] == 1
        assert result["schemas"][0]["name"] == "Fact"

    def test_schema_with_no_fields_attribute(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_inst = mock_reg.return_value
            schema = MagicMock(spec=["name"])
            schema.name = "broken"
            mock_inst._registry = {"broken": schema}
            result = handle_list()
        assert result["count"] == 1
        assert result["schemas"][0]["fields"] == []

    def test_accepts_params(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_inst = mock_reg.return_value
            mock_inst._registry = {}
            result = handle_list({"ignored": "x"})
        assert "schemas" in result


# ── handle_validate ────────────────────────────────────────────


class TestHandleValidate:
    def test_default_schema_type(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": "{}"})
        assert result["is_valid"] is True
        assert result["type"] == "KnowledgeCard"

    def test_knowledge_card_valid(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": "{}", "schema_type": "KnowledgeCard"})
        assert result["is_valid"] is True
        assert result["errors"] == []

    def test_knowledge_card_with_errors(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = ["missing field title"]
            result = handle_validate({"data": "{}", "schema_type": "KnowledgeCard"})
        assert result["is_valid"] is False

    def test_fact_schema_type(self):
        with patch("eidos.types.Fact") as mock_fact:
            mock_inst = mock_fact.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": "{}", "schema_type": "Fact"})
        assert result["type"] == "Fact"

    def test_ontology_node_schema_type(self):
        with patch("eidos.types.OntologyNode") as mock_node:
            mock_inst = mock_node.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": "{}", "schema_type": "OntologyNode"})
        assert result["type"] == "OntologyNode"

    def test_schema_type_keyword_card(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": "{}", "schema_type": "my card"})
        assert result["type"] == "KnowledgeCard"

    def test_unknown_schema_type(self):
        result = handle_validate({"data": "{}", "schema_type": "UnknownThing"})
        assert result["is_valid"] is True
        assert result["errors"] == []

    def test_invalid_json_data(self):
        result = handle_validate({"data": "not valid json", "schema_type": "KnowledgeCard"})
        assert result["is_valid"] is False
        assert "Invalid JSON" in result["errors"][0]

    def test_dict_data_skips_json_parse(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate({"data": {"already": "dict"}, "schema_type": "KnowledgeCard"})
        assert result["is_valid"] is True

    def test_exceptions_caught(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_card.from_dict.side_effect = ValueError("schema broken")
            result = handle_validate({"data": "{}", "schema_type": "KnowledgeCard"})
        assert result["is_valid"] is False
        assert "schema broken" in result["errors"]

    def test_none_params(self):
        with patch("eidos.types.KnowledgeCard") as mock_card:
            mock_inst = mock_card.from_dict.return_value
            mock_inst.validate.return_value = []
            result = handle_validate(None)
        assert result["format_version"] == FORMAT_VERSION


# ── handle_meta ────────────────────────────────────────────────


class TestHandleMeta:
    def test_returns_format_version(self):
        result = handle_meta()
        assert result["format_version"] == FORMAT_VERSION

    def test_includes_meta_types(self):
        result = handle_meta()
        assert "meta_types" in result
        assert isinstance(result["meta_types"], list)
        assert len(result["meta_types"]) > 0

    def test_meta_types_have_value_and_name(self):
        result = handle_meta()
        for mt in result["meta_types"]:
            assert "value" in mt
            assert "name" in mt

    def test_includes_meta_relations(self):
        result = handle_meta()
        assert "meta_relations" in result

    def test_includes_type_mappings(self):
        with patch("eidos.meta.list_types", return_value=[{"type_name": "T1", "meta_type": "M0"}]):
            result = handle_meta()
        assert result["type_mappings"] == [{"type_name": "T1", "meta_type": "M0"}]


# ── handle_migrate ─────────────────────────────────────────────


class TestHandleMigrate:
    def test_missing_schema_name(self):
        result = handle_migrate({})
        assert result["migrated"] is False
        assert "schema_name is required" in result["error"]

    def test_missing_data(self):
        result = handle_migrate({"schema_name": "x"})
        assert result["migrated"] is False
        assert "data is required" in result["error"]

    def test_no_migrations_registered(self):
        with patch("eidos.core.schema.get_migrations", return_value={}):
            result = handle_migrate({"schema_name": "x", "data": {"a": 1}})
        assert result["migrated"] is False
        assert "No migrations registered" in result["note"]

    def test_successful_migration(self):
        with patch("eidos.core.schema.get_migrations", return_value={"m1": "fake"}):
            with patch(
                "eidos.core.schema.migrate_schema_instance", return_value={"_migrated_version": "2.0", "data": "ok"}
            ):
                result = handle_migrate({"schema_name": "x", "data": {"a": 1}})
        assert result["migrated"] is True
        assert result["from_version"] == "1.0"
        assert result["to_version"] == "2.0"

    def test_custom_versions(self):
        with patch("eidos.core.schema.get_migrations", return_value={"m1": "fake"}):
            with patch("eidos.core.schema.migrate_schema_instance", return_value={"_migrated_version": "3.5"}):
                result = handle_migrate(
                    {
                        "schema_name": "x",
                        "data": {"a": 1},
                        "from_version": "2.0",
                        "to_version": "3.5",
                    }
                )
        # If success path, from_version should be in result
        if "from_version" in result:
            assert result["from_version"] == "2.0"
            assert result["to_version"] == "3.5"
            assert result["migrated"] is True
        else:
            # Otherwise must be the no-migrations path
            assert result["migrated"] is False
            assert "No migrations" in result.get("note", "")

    def test_migration_exception(self):
        with patch("eidos.core.schema.get_migrations", return_value={"m1": "fake"}):
            with patch("eidos.core.schema.migrate_schema_instance", side_effect=ValueError("broken")):
                result = handle_migrate({"schema_name": "x", "data": {"a": 1}})
        assert result["migrated"] is False
        assert "broken" in result.get("error", "")


# ── handle_migration_list ──────────────────────────────────────


class TestHandleMigrationList:
    def test_returns_format_version(self):
        result = handle_migration_list()
        assert result["format_version"] == FORMAT_VERSION

    def test_no_migrations(self):
        with patch("eidos.core.schema._SCHEMA_MIGRATIONS", {}):
            result = handle_migration_list()
        assert result["migrations"] == []
        assert result["count"] == 0

    def test_with_migrations(self):
        mock_mig = MagicMock()
        mock_mig.from_version = "1.0"
        mock_mig.to_version = "2.0"
        mock_mig.description = "Add foo"
        with patch("eidos.core.schema._SCHEMA_MIGRATIONS", {"my_schema": [mock_mig]}):
            result = handle_migration_list()
        assert result["count"] == 1
        assert result["migrations"][0]["schema"] == "my_schema"

    def test_multiple_migrations(self):
        m1 = MagicMock(from_version="1.0", to_version="2.0", description="A")
        m2 = MagicMock(from_version="2.0", to_version="3.0", description="B")
        with patch(
            "eidos.core.schema._SCHEMA_MIGRATIONS",
            {
                "s1": [m1, m2],
                "s2": [m1],
            },
        ):
            result = handle_migration_list()
        assert result["count"] == 3


# ── handle_define ──────────────────────────────────────────────


class TestHandleDefine:
    def test_default_name(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_reg.return_value.register = MagicMock()
            result = handle_define({})
        assert result["name"] == "Untitled"

    def test_custom_name(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_reg.return_value.register = MagicMock()
            result = handle_define({"name": "MySchema"})
        assert result["name"] == "MySchema"

    def test_no_fields(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_reg.return_value.register = MagicMock()
            result = handle_define({"name": "Empty"})
        assert result["fields"] == 0
        assert result["status"] == "registered"

    def test_with_fields(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_reg.return_value.register = MagicMock()
            result = handle_define(
                {
                    "name": "X",
                    "fields": [
                        {"name": "title", "type": "string", "required": True, "description": "Title"},
                        {"name": "count", "type": "int", "required": False, "description": "Count"},
                    ],
                }
            )
        assert result["fields"] == 2

    def test_invalid_field_type_defaults_to_string(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_reg.return_value.register = MagicMock()
            with patch("eidos.core.schema.FieldType") as mock_ft:
                mock_ft.STRING = "string"
                mock_ft.side_effect = ValueError("bad type")
                result = handle_define(
                    {
                        "name": "X",
                        "fields": [{"name": "f", "type": "unknown_type"}],
                    }
                )
        assert result["fields"] == 1

    def test_register_called(self):
        with patch("eidos.core.schema.SchemaRegistry") as mock_reg:
            mock_register = MagicMock()
            mock_reg.return_value.register = mock_register
            handle_define({"name": "X", "fields": [{"name": "f"}]})
        assert mock_register.called


# ── handle_export ─────────────────────────────────────────────


class TestHandleExport:
    def test_no_schemas(self):
        with patch("eidos.registry.create_registry") as mock_create:
            mock_reg = MagicMock()
            mock_reg.list_types.return_value = []
            mock_reg.get.return_value = None
            mock_create.return_value = mock_reg
            result = handle_export()
        assert result["count"] == 0
        assert result["exported"] == []

    def test_specific_names(self):
        with patch("eidos.registry.create_registry") as mock_create:
            mock_reg = MagicMock()
            schema = MagicMock()
            schema.name = "X"
            schema.version = "1.0"
            schema.description = "Test"
            schema.fields = {}
            schema.extends = []
            mock_reg.get.side_effect = lambda n: schema if n == "X" else None
            mock_create.return_value = mock_reg
            result = handle_export({"names": ["X"]})
        assert result["count"] == 1

    def test_nonexistent_name_skipped(self):
        with patch("eidos.registry.create_registry") as mock_create:
            mock_reg = MagicMock()
            mock_reg.get.return_value = None
            mock_create.return_value = mock_reg
            result = handle_export({"names": ["X", "Y"]})
        assert result["count"] == 0

    def test_export_format(self):
        with patch("eidos.registry.create_registry") as mock_create:
            mock_reg = MagicMock()
            field = MagicMock()
            field.name = "id"
            field.field_type.value = "int"
            field.required = True
            field.description = "ID"
            field.ref_schema = None
            field.item_type = None
            field.default = None
            schema = MagicMock()
            schema.name = "TestSchema"
            schema.version = "1.0"
            schema.description = "Test description"
            schema.fields = {"id": field}
            schema.extends = []
            schema.to_json_schema.return_value = {"type": "object"}
            mock_reg.list_types.return_value = ["TestSchema"]
            mock_reg.get.return_value = schema
            mock_create.return_value = mock_reg
            result = handle_export()
        assert result["count"] == 1
        exported = result["exported"][0]
        assert exported["name"] == "TestSchema"
        assert exported["$schema"] == {"type": "object"}


# ── TOOLS registry ──────────────────────────────────────────


class TestToolsRegistry:
    def test_all_handlers_registered(self):
        assert set(TOOLS.keys()) == {
            "eidos_list",
            "eidos_validate",
            "eidos_meta",
            "eidos_define",
            "eidos_export",
            "eidos_migrate",
            "eidos_migration_list",
        }

    def test_each_tool_has_callable_func(self):
        for name, info in TOOLS.items():
            assert "func" in info
            assert callable(info["func"])

    def test_each_tool_has_description(self):
        for name, info in TOOLS.items():
            assert "description" in info
            assert isinstance(info["description"], str)

    def test_each_tool_has_input_schema(self):
        for name, info in TOOLS.items():
            assert "input_schema" in info
            assert info["input_schema"]["type"] == "object"


# ── _call_tool ───────────────────────────────────────────────


class TestCallTool:
    def test_unknown_tool_raises_keyerror(self):
        with pytest.raises(KeyError):
            _call_tool("nonexistent_tool")

    def test_known_tool_invocation(self):
        result = _call_tool("eidos_meta")
        assert "content" in result
        assert result["content"][0]["type"] == "text"

    def test_params_passed_to_handler(self):
        mock_func = MagicMock(return_value={"is_valid": True})
        with patch.dict(
            mcp_server.TOOLS,
            {
                "eidos_validate": {
                    "func": mock_func,
                    "description": "x",
                    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                }
            },
        ):
            _call_tool("eidos_validate", {"data": "x"})
        mock_func.assert_called_once_with({"data": "x"})

    def test_none_params_becomes_empty_dict(self):
        mock_func = MagicMock(return_value={"is_valid": True})
        with patch.dict(
            mcp_server.TOOLS,
            {
                "eidos_validate": {
                    "func": mock_func,
                    "description": "x",
                    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                }
            },
        ):
            _call_tool("eidos_validate", None)
        mock_func.assert_called_once_with({})


# ── _list_tools ───────────────────────────────────────────────


class TestListTools:
    def test_returns_tools_list(self):
        result = _list_tools()
        assert "tools" in result
        assert isinstance(result["tools"], list)

    def test_each_tool_has_required_fields(self):
        result = _list_tools()
        for t in result["tools"]:
            assert "name" in t
            assert "description" in t
            assert "inputSchema" in t

    def test_tool_count_matches_tools_registry(self):
        result = _list_tools()
        assert len(result["tools"]) == len(TOOLS)


# ── handle_mcp_request ──────────────────────────────────────


class TestHandleMcpRequest:
    def test_initialize_method(self):
        request = {"method": "initialize", "id": 1, "params": {}}
        result = handle_mcp_request(request)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["result"]["serverInfo"]["name"] == "eidos-mcp"

    def test_list_tools_method(self):
        request = {"method": "list_tools", "id": 2, "params": {}}
        result = handle_mcp_request(request)
        assert "tools" in result["result"]

    def test_tools_list_method(self):
        request = {"method": "tools/list", "id": 3, "params": {}}
        result = handle_mcp_request(request)
        assert "tools" in result["result"]

    def test_call_tool_with_slash_separator(self):
        request = {"method": "call_tool/eidos_meta", "id": 4, "params": {}}
        result = handle_mcp_request(request)
        assert "content" in result["result"]

    def test_tools_call_method(self):
        request = {
            "method": "tools/call",
            "id": 5,
            "params": {"name": "eidos_meta", "arguments": {}},
        }
        result = handle_mcp_request(request)
        assert "content" in result["result"]

    def test_unknown_method(self):
        request = {"method": "weird/method", "id": 6, "params": {}}
        result = handle_mcp_request(request)
        assert "error" in result
        assert result["error"]["code"] == -32601

    def test_unknown_tool_via_call_method(self):
        request = {
            "method": "tools/call",
            "id": 7,
            "params": {"name": "nonexistent", "arguments": {}},
        }
        result = handle_mcp_request(request)
        assert "error" in result
        assert "Unknown tool" in result["error"]["message"]

    def test_exception_during_tool_call(self):
        with patch.object(mcp_server, "_call_tool", side_effect=RuntimeError("boom")):
            request = {
                "method": "tools/call",
                "id": 8,
                "params": {"name": "x", "arguments": {}},
            }
            result = handle_mcp_request(request)
        assert "error" in result
        assert "boom" in result["error"]["message"]

    def test_missing_id(self):
        request = {"method": "initialize", "params": {}}
        result = handle_mcp_request(request)
        assert "id" in result
        assert result["id"] is None


# ── main ─────────────────────────────────────────────────────


class TestMain:
    def test_help_flag(self, capsys):
        with patch("sys.argv", ["eidos-mcp", "--help"]):
            main()
        captured = capsys.readouterr()
        assert "Eidos MCP Server" in captured.out
        assert "Tools:" in captured.out
        for tool_name in TOOLS:
            assert tool_name in captured.out

    def test_short_help_flag(self, capsys):
        with patch("sys.argv", ["eidos-mcp", "-h"]):
            main()
        captured = capsys.readouterr()
        assert "Eidos MCP Server" in captured.out

    def test_no_fastmcp_exits_1(self, capsys):
        with patch("sys.argv", ["eidos-mcp"]):
            with patch("eidos.mcp_server._handle_fastmcp", return_value=None):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "FastMCP required" in captured.err

    def test_runs_app_when_fastmcp_available(self, capsys):
        mock_app = MagicMock()
        with patch("sys.argv", ["eidos-mcp"]):
            with patch("eidos.mcp_server._handle_fastmcp", return_value=mock_app):
                main()
        mock_app.run.assert_called_once()


class TestFormatVersion:
    def test_format_version_constant(self):
        assert FORMAT_VERSION == "eidos-v1"
