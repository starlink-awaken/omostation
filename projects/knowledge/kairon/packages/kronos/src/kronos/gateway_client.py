"""Gateway MCP Client — 从 CLI 调用 Gateway 管理的 MCP 工具。

通过子进程启动 gateway/bin/ 下的 MCP wrapper，用 stdin/stdout JSON-RPC 通信。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

GATEWAY_BIN = Path.home() / "Workspace" / "gateway" / "bin"


def _call_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    """调 Gateway 管理的某个 MCP 工具的 call_tool。

    先通过 tools/list 找到对应的 MCP server，再用 tools/call 调用。
    """
    # 工具名 → MCP server 名映射
    server_map = {
        "eidos_validate": "eidos-mcp",
        "eidos_meta": "eidos-mcp",
        "eidos_list": "eidos-mcp",
        "web_fetch": "minerva-mcp",  # minerva 有 web fetch 工具
    }

    server = server_map.get(tool_name)
    if not server:
        return {"error": f"unknown tool: {tool_name}"}

    wrapper = GATEWAY_BIN / server
    if not wrapper.exists():
        return {"error": f"gateway wrapper not found: {wrapper}"}

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }

    try:
        proc = subprocess.run(
            [str(wrapper)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = json.loads(proc.stdout)
        parsed: dict[str, Any] = result.get("result", {})
        return parsed
    except Exception as e:
        return {"error": str(e)}


def validate_with_eidos(data: dict[str, Any], schema_type: str = "KnowledgeCard") -> dict[str, Any]:
    """通过 Eidos MCP 校验数据结构"""
    return _call_mcp_tool(
        "eidos_validate",
        {
            "data": json.dumps(data, ensure_ascii=False),
            "schema_type": schema_type,
        },
    )


def check_ollama() -> bool:
    """检测 Ollama 是否在运行"""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "models" in result.stdout:
            return True
    except Exception:
        pass
    return False
