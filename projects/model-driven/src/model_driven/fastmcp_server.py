"""model-driven FastMCP wrapper — 委派给 MCPServer

FastMCP 3.x 不支持 **kwargs，所以用单个通用工具 + JSON 参数。
"""

from __future__ import annotations

import json as _json
from model_driven.mcp_server import MCPServer

try:
    from fastmcp import FastMCP
except ImportError:
    raise SystemExit("fastmcp not installed. Install with: uv sync")

mcp = FastMCP("model-driven")

_server = MCPServer()
_tools = _server.list_tools()


@mcp.tool()
def model_tools_list(category: str = "") -> str:
    """列出所有可用模型驱动工具，可按 category 过滤: lifecycle|spec|adr|okr|omo|collab|toolchain|ssot|trigger"""
    tools = _server.list_tools(category=category or None)
    return _json.dumps([{
        "name": t["name"],
        "description": t["description"],
        "category": t.get("category", ""),
    } for t in tools], ensure_ascii=False)


@mcp.tool()
def model_tool_execute(tool_name: str, params_json: str = "{}") -> str:
    """执行指定的模型驱动工具。

    tool_name: 工具名（用 model_tools_list 查询可用列表）
    params_json: JSON 字符串形式的参数，如 '{"entity_id": "proj-1", "title": "My Project"}'
    """
    try:
        params = _json.loads(params_json) if params_json else {}
    except _json.JSONDecodeError as e:
        return _json.dumps({"error": f"参数 JSON 解析失败: {e}"})
    result = _server.execute(tool_name, **params)
    if isinstance(result, dict | list):
        return _json.dumps(result, ensure_ascii=False, default=str)
    return str(result)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
