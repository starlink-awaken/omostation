"""ToolForge FastMCP server — 思维工具匹配（MCP 工具：match / select / guide）.

落地契约（ToolForge 子模块 README 声明）：
  - toolforge_match  → 分组匹配
  - toolforge_select → 跨类别 Top-N
  - toolforge_guide  → 推导指导 markdown

复用 ToolForge 匹配引擎，避免与 `mcp_server.py` 重复实现。
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from fastmcp import FastMCP

from ontoderive.toolforge.matcher import ToolForge

mcp = FastMCP(
    "ontoderive-toolforge",
    instructions=(
        "ToolForge MCP — 思维工具匹配 (方法论/策略/模式/原则/理论/技能). "
        "Tools: toolforge_match, toolforge_select, toolforge_guide."
    ),
)


_TOOLFORGE: ToolForge | None = None


def _engine() -> ToolForge:
    global _TOOLFORGE
    if _TOOLFORGE is None:
        _TOOLFORGE = ToolForge()
    return _TOOLFORGE


@mcp.tool()
def toolforge_match(
    goal: str, context: str = "", mode: str = "keyword", limit: int = 3
) -> dict[str, list[dict[str, Any]]]:
    """分组匹配思维工具 — 按 6 大类别返回结果."""
    return _engine().match(goal, context, limit=limit, mode=mode)


@mcp.tool()
def toolforge_select(goal: str, context: str = "", mode: str = "keyword", top_n: int = 5) -> list[dict[str, Any]]:
    """跨类别 Top-N 工具扁平列表."""
    return _engine().select(goal, context, top_n=top_n, mode=mode)


@mcp.tool()
def toolforge_guide(goal: str, context: str = "", mode: str = "keyword") -> str:
    """生成 OntoDerive 推导指导 markdown."""
    return _engine().to_inference_guide(goal, context, mode=mode)


TOOL_DEFS = [
    {
        "name": "toolforge_match",
        "description": "分组匹配思维工具 — 按 6 大类别返回结果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string", "default": ""},
                "mode": {"type": "string", "enum": ["tfidf", "keyword", "hybrid"], "default": "keyword"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "toolforge_select",
        "description": "跨类别 Top-N 工具扁平列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string", "default": ""},
                "mode": {"type": "string", "enum": ["tfidf", "keyword", "hybrid"], "default": "keyword"},
                "top_n": {"type": "integer", "default": 5},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "toolforge_guide",
        "description": "生成 OntoDerive 推导指导 markdown",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string", "default": ""},
                "mode": {"type": "string", "enum": ["tfidf", "keyword", "hybrid"], "default": "keyword"},
            },
            "required": ["goal"],
        },
    },
]


def handle_request(request: dict) -> dict:
    """兼容委托入口 — Agora 9 FastMCP 聚合通道仍可走统一 bridge."""
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
                    "serverInfo": {"name": "ontoderive-toolforge", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            }

        if method in {"tools/list", "list_tools"}:
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOL_DEFS}}

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {}) or {}
            if name == "toolforge_match":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": toolforge_match(**arguments),
                }
            if name == "toolforge_select":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": toolforge_select(**arguments),
                }
            if name == "toolforge_guide":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": toolforge_guide(**arguments),
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": str(exc)}}


def main() -> None:
    parser = argparse.ArgumentParser(description="OntoDerive ToolForge MCP Server (fastmcp)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="SSE port (0 = stdio)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default=None)
    args = parser.parse_args()
    transport = args.transport or ("sse" if args.port else "stdio")
    print(f"[ontoderive-toolforge] transport={transport}", file=sys.stderr)
    if transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
