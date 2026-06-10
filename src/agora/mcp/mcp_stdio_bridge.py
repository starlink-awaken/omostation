"""MCP Stdio 协议桥接器 (P54-W0)
===============================
为下游 POC 服务的自定义协议提供标准 MCP stdio JSON-RPC 2.0 接口。

工作方式:
  1. 启动时以 MCP stdio server 运行
  2. 接收 MCP tools/call 请求
  3. 转换为 POC 自定义协议请求
  4. 转发给下游子进程
  5. 将结果转换回 MCP 格式返回

用法: python3 mcp_stdio_bridge.py <poc_command> [poc_args...]

此桥接器使现有 POC 服务无需修改即可通过标准 MCP 协议访问。
"""

import sys
import json
import subprocess
from typing import Any


class MCPStdioBridge:
    """将自定义 POC 协议桥接到标准 MCP stdio JSON-RPC 2.0。"""

    def __init__(self, command: list[str]):
        self.command = command
        self._proc: subprocess.Popen | None = None
        self._request_id = 0

    def start(self) -> None:
        """启动下游子进程。"""
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def handle(self) -> None:
        """主循环: 从 stdin 读取 MCP JSON-RPC 请求，转发到子进程，返回结果。"""
        if not self._proc:
            self.start()

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
                response = self._handle_tools_call(req_id, request.get("params", {}))
            else:
                response = self._error(req_id, -32601, f"Method not found: {method}")

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    def _handle_initialize(self, req_id: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-stdio-bridge", "version": "1.0"},
            },
        }

    def _handle_tools_list(self, req_id: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "poc_exec",
                        "description": f"Execute POC service: {' '.join(self.command)}",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "POC action name",
                                },
                                "args": {
                                    "type": "array",
                                    "description": "Positional arguments",
                                },
                            },
                        },
                    }
                ]
            },
        }

    def _handle_tools_call(self, req_id: Any, params: dict) -> dict:
        action = params.get("arguments", {}).get("action", "main")
        args_list = params.get("arguments", {}).get("args", [])

        # 使用自定义 POC 协议调用子进程
        self._request_id += 1
        poc_request = json.dumps(
            {
                "request_id": f"req-{self._request_id}",
                "action": action,
                "args": args_list,
            }
        )

        try:
            self._proc.stdin.write(poc_request + "\n")
            self._proc.stdin.flush()
            response_line = self._proc.stdout.readline()
            poc_result = json.loads(response_line.strip())

            if poc_result.get("status") == "ok":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    poc_result.get("result", poc_result)
                                ),
                            }
                        ],
                    },
                }
            else:
                return self._error(
                    req_id, -32000, poc_result.get("error", "POC execution failed")
                )
        except (BrokenPipeError, json.JSONDecodeError, OSError) as e:
            return self._error(req_id, -32000, str(e))

    def _error(self, req_id: Any, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def shutdown(self) -> None:
        if self._proc:
            self._proc.terminate()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mcp_stdio_bridge.py <poc_command...>", file=sys.stderr)
        sys.exit(1)

    bridge = MCPStdioBridge(sys.argv[1:])
    try:
        bridge.handle()
    except KeyboardInterrupt:
        bridge.shutdown()


if __name__ == "__main__":
    main()
