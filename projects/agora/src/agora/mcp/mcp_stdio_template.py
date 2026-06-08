"""MCP Stdio Server 参考实现 (P54-W1)
===============================
下游包添加最小 MCP stdio 服务的模板。

将此文件复制到下游包 (如 kairon/kos) 并在 __main__.py 中调用 main()。

用法: python -m kos serve --mcp-stdio
"""

import sys
import json


class MCPStdioServer:
    """最小 MCP stdio JSON-RPC 2.0 服务端实现。

    下游包只需继承此类，实现 handle_tool_call() 方法即可。
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: list[dict] = []

    def register_tool(self, name: str, description: str, input_schema: dict | None = None):
        """注册一个工具。"""
        self._tools.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema or {"type": "object"},
        })

    def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """子类重写: 处理工具调用, 返回结果。"""
        raise NotImplementedError("Subclass must implement handle_tool_call()")

    def run(self):
        """主循环: 从 stdin 读取 JSON-RPC 请求, 处理, 写回 stdout。"""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            method = request.get("method", "")
            req_id = request.get("id")

            if method == "initialize":
                response = self._handle_initialize(req_id)
            elif method == "tools/list":
                response = self._handle_tools_list(req_id)
            elif method == "tools/call":
                response = self._handle_tools_call(
                    req_id, request.get("params", {})
                )
            else:
                response = self._error(req_id, -32601, f"Method not found: {method}")

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    def _handle_initialize(self, req_id) -> dict:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": self.version},
            },
        }

    def _handle_tools_list(self, req_id) -> dict:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": self._tools},
        }

    def _handle_tools_call(self, req_id, params: dict) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result = self.handle_tool_call(tool_name, arguments)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                },
            }
        except Exception as e:
            return self._error(req_id, -32000, str(e))

    def _error(self, req_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ══ 示例: 下游包如何使用 ══


class ExampleKOSServer(MCPStdioServer):
    """示例: KOS 搜索服务的 MCP stdio 实现。"""

    def __init__(self):
        super().__init__("kos", "1.0.0")
        self.register_tool("search", "KOS 跨域语义搜索", {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "limit": {"type": "integer", "default": 10},
            },
        })

    def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        if tool_name == "search":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            return {
                "query": query,
                "limit": limit,
                "results": [],
                "note": "Replace with actual KOS implementation",
            }
        raise ValueError(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
    # 下游包使用方法:
    #   1. 继承 MCPStdioServer
    #   2. 注册工具 (register_tool)
    #   3. 实现 handle_tool_call
    #   4. 调用 server.run()
    server = ExampleKOSServer()
    server.run()
