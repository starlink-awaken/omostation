"""BOS MCP 标准协议适配器 (P48) — 渐进迁移到 MCP JSON-RPC 2.0
===============================================================
封装标准 MCP stdio 协议: initialize → tools/list → tools/call

用法 (替代自定义 invoke_stdio 协议):
    from agora.mcp.bos_protocol import MCPStdioAdapter

    adapter = MCPStdioAdapter("uv run -m kos serve --mcp", timeout=5.0)
    result = await adapter.call("search", {"query": "什么是 eCOS"})

协议: 标准 MCP JSON-RPC 2.0 over stdin/stdout
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from typing import Any

_log = logging.getLogger(__name__)

# MCP JSON-RPC 2.0 常量
JSONRPC_VERSION = "2.0"
MCP_VERSION = "2024-11-05"


class MCPStdioAdapter:
    """标准 MCP stdio 协议适配器。

    封装完整的 JSON-RPC 2.0 生命周期:
    1. 启动子进程 (subprocess.Popen)
    2. initialize 握手
    3. tools/list 获取工具列表
    4. tools/call 调用工具
    5. 进程管理 (alive check, shutdown)
    """

    def __init__(self, command: str, timeout: float = 5.0):
        self.command = command
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._tools: dict[str, dict] = {}  # name → {inputSchema, description}
        self._initialized = False
        self._request_id = 0

    async def start(self) -> bool:
        """启动子进程并完成 MCP initialize 握手。"""
        try:
            self._proc = subprocess.Popen(
                self.command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # initialize
            init_result = await self._request("initialize", {
                "protocolVersion": MCP_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "agora-mcp-stdio-adapter", "version": "1.0"},
            })
            if init_result.get("error"):
                _log.error("mcp_initialize_failed: %s", init_result["error"])
                return False
            self._initialized = True

            # tools/list
            tools_result = await self._request("tools/list", {})
            for tool in tools_result.get("result", {}).get("tools", []):
                self._tools[tool["name"]] = tool
            _log.info("mcp_adapter_initialized: %s (%d tools)", self.command, len(self._tools))
            return True
        except Exception as e:
            _log.error("mcp_adapter_start_failed: %s — %s", self.command, e)
            return False

    async def call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用 MCP 工具。"""
        if not self._initialized or self._proc is None:
            return {"status": "error", "error": "adapter not initialized"}
        if tool_name not in self._tools:
            return {"status": "error", "error": f"tool not found: {tool_name}"}
        try:
            result = await self._request("tools/call", {
                "name": tool_name,
                "arguments": arguments or {},
            })
            content = result.get("result", {}).get("content", [])
            text_results = [c.get("text", "") for c in content if c.get("type") == "text"]
            return {"status": "ok", "result": text_results[0] if len(text_results) == 1 else text_results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 2.0 请求并等待响应。"""
        self._request_id += 1
        request = json.dumps({
            "jsonrpc": JSONRPC_VERSION,
            "id": self._request_id,
            "method": method,
            "params": params,
        })
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("process not started")
        self._proc.stdin.write(request + "\n")
        self._proc.stdin.flush()
        try:
            # Non-blocking fallback: read line with asyncio timeout
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, self._proc.stdout.readline)
            line = await asyncio.wait_for(future, timeout=self.timeout)
            return json.loads(line.strip())
        except asyncio.TimeoutError:
            return {"error": "mcp_request_timeout"}
        except (json.JSONDecodeError, BrokenPipeError) as e:
            return {"error": str(e)}

    def shutdown(self) -> None:
        """关闭子进程。"""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            self._initialized = False

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


async def test_adapter():
    """测试适配器：连接本地 MCP server。"""
    # 示例: 连接 ecos bos mounter
    try:
        adapter = MCPStdioAdapter("uv run -m agora.mcp.bos_resolve serve")
        ok = await adapter.start()
        print(f"MCP adapter started: {ok}, tools: {list(adapter._tools.keys())}")
        adapter.shutdown()
    except Exception as e:
        print(f"Test failed (expected in non-MCP env): {e}")
        return False
    return True
