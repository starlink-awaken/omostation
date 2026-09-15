#!/usr/bin/env python3
"""OntoDerive MCP (FastMCP) — derive/validate/trace as MCP tools.

python3 engine/mcp_server.py                     # stdio
python3 engine/mcp_server.py --port 8321          # SSE"""

import argparse
import sys
from pathlib import Path
from typing import Any, cast

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastmcp import FastMCP

from ontoderive import __version__
from ontoderive.foundation.typesystem import META_TYPES, PREFIX_TO_META, TypeValidator

mcp = FastMCP(
    "ontoderive",
    instructions=(
        "OntoDerive MCP — 知识推导/验证/溯源. Tools: derive, trace, validate, list_entities, pipeline_status"
    ),
)

TOOL_DEFS = [
    {
        "name": "derive",
        "description": "正向知识推导 — 事实扫描 → 多引擎推理 → 推导结论",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "default": "."},
                "goal": {"type": "string", "default": ""},
                "auto": {"type": "boolean", "default": False},
                "with_tools": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "trace",
        "description": "溯源推理路径 — 从实体ID出发,追踪其涉及的推理链",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "depth": {"type": "integer", "default": 2},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "validate",
        "description": "校验数据是否符合OntoDerive类型系统 — ID前缀/子类型/必填字段",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema": {"type": "string"},
                "data": {"type": "string"},
            },
            "required": ["schema", "data"],
        },
    },
    {
        "name": "list_entities",
        "description": "列出OntoDerive类型系统中所有可用的元类型和子类型",
        "inputSchema": {
            "type": "object",
            "properties": {"meta_type": {"type": "string"}},
        },
    },
    {
        "name": "pipeline_status",
        "description": "检查OntoDerive管道就绪状态 — 模块可用性",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


@mcp.tool()
def derive(project: str = ".", goal: str = "", auto: bool = False, with_tools: bool = False) -> dict:
    """正向知识推导 — 事实扫描 → 多引擎推理 → 推导结论"""
    from ontoderive.core.derive import OntoDerive

    od = OntoDerive(project)
    result = od.derive()
    if auto:
        od.analyze()

    return {
        "facts": result.get("facts", 0),
        "entities": result.get("entities", 0),
        "inferences": result.get("inferences", 0),
        "confidence": result.get("confidence_distribution", {}),
        "conclusions": [c.get("title", c.get("label", ""))[:200] for c in result.get("derived_conclusions", [])],
        "hints": result.get("derivation_hints", []),
    }


@mcp.tool()
def trace(entity_id: str, depth: int = 2) -> dict:
    """溯源推理路径 — 从实体ID出发,追踪其涉及的推理链"""
    prefix_match: str | None = None
    for prefix in sorted(PREFIX_TO_META, key=len, reverse=True):
        if entity_id.startswith(prefix):
            prefix_match = prefix
            break

    meta_type = PREFIX_TO_META.get(prefix_match or "UNKNOWN", "UNKNOWN")
    meta_info = META_TYPES.get(meta_type, {})
    return {
        "entity_id": entity_id,
        "meta_type": meta_type,
        "meta_description": meta_info.get("description", ""),
        "depth": depth,
        "trace": [
            {
                "step": 0,
                "type": "entity_resolution",
                "detail": f"Entity '{entity_id}' resolved to meta-type '{meta_type}'",
            }
        ],
        "note": "Full inference-chain tracing requires a derived project with `derive()` first.",
    }


@mcp.tool()
def validate(schema: str, data: str) -> dict:
    """校验数据是否符合OntoDerive类型系统 — ID前缀/子类型/必填字段"""
    validator = TypeValidator()

    items = []
    for line in data.strip().split("\n"):
        line = line.strip()
        if not line or (line.startswith("|") and "---" in line):
            continue
        if line.startswith("|"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 1:
                items.append({"id": parts[0], "type": schema})

    results = []
    for item in items:
        r = validator.check_id(item["id"], item.get("type", ""))
        results.append(
            {
                "node_id": r.node_id,
                "declared_type": r.declared_type,
                "expected_type": r.expected_type,
                "valid": r.is_valid,
                "errors": r.errors,
                "warnings": r.warnings,
            }
        )

    return {"total": validator.summary()["total"], "valid": validator.summary()["valid"], "results": results}


@mcp.tool()
def list_entities(meta_type: str | None = None) -> list[dict]:
    """列出OntoDerive类型系统中所有可用的元类型和子类型"""
    result = []
    for name, info in META_TYPES.items():
        if meta_type and name.lower() != meta_type.lower():
            continue
        result.append(
            {
                "meta_type": name,
                "description": info["description"],
                "subtypes": sorted(info["subtypes"]),
                "id_prefixes": info["id_prefixes"],
                "required_fields": info["required_fields"],
            }
        )
    return result


@mcp.tool()
def pipeline_status() -> dict:
    """检查OntoDerive管道就绪状态 — 模块可用性"""
    checks = {}
    for mod_name, import_path in [
        ("OntoDerive", "engine.core.derive"),
        ("DerivePipeline", "engine.core.pipeline"),
        ("TypeValidator", "engine.foundation.typesystem"),
        ("ToolForge", "engine.toolforge"),
    ]:
        try:
            __import__(import_path)
            checks[mod_name] = "ready"
        except Exception as e:
            checks[mod_name] = f"unavailable: {e}"

    try:
        from ontoderive.intelligence.llm import get_enhancer

        enhancer = get_enhancer()
        checks["LLM"] = enhancer.backend if enhancer.available else "not configured"
    except Exception as e:
        checks["LLM"] = f"unavailable: {e}"

    return {
        "server": "ontoderive-mcp",
        "modules": checks,
        "meta_types": list(META_TYPES.keys()),
        "tools": ["derive", "trace", "validate", "list_entities", "pipeline_status"],
    }


_TOOL_HANDLERS: dict[str, Any] = {
    "derive": derive,
    "trace": trace,
    "validate": validate,
    "list_entities": list_entities,
    "pipeline_status": pipeline_status,
}


def _call_tool(name: str, arguments: dict | None = None) -> dict | list[dict]:
    if name not in _TOOL_HANDLERS:
        raise KeyError(f"Unknown tool: {name}")
    handler = _TOOL_HANDLERS[name]
    return cast("dict[Any, Any] | list[dict[Any, Any]]", handler(**(arguments or {})))


def handle_mcp_request(request: dict) -> dict:
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "0.1.0",
                    "serverInfo": {"name": "ontoderive", "version": __version__},
                    "capabilities": {"tools": {}},
                },
            }

        if method in {"tools/list", "list_tools"}:
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOL_DEFS}}

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return {"jsonrpc": "2.0", "id": req_id, "result": _call_tool(str(tool_name), arguments)}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": str(exc)}}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": str(exc)}}


handle_request = handle_mcp_request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OntoDerive MCP Server (fastmcp)",
        epilog="Example: python3 engine/mcp_server.py --port 8321",
    )
    parser.add_argument("--host", default="127.0.0.1", help="SSE bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="SSE port (0 = stdio mode)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default=None, help="Force transport mode")

    args = parser.parse_args()
    transport = args.transport or ("sse" if args.port else "stdio")

    print(f"[ontoderive-mcp] transport={transport}", file=sys.stderr)
    if args.port:
        print(f"[ontoderive-mcp] host={args.host} port={args.port}", file=sys.stderr)

    if transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
