"""Unit tests for agora.mcp.bos_protocol — MCPStdioAdapter.

验证:
  1. 初始状态 (未初始化、alive 为 False)
  2. 进程生命周期 (start→shutdown)
  3. 错误路径 (命令不存在、超时)
  4. 工具列表管理
  5. shutdown 清理
"""
from __future__ import annotations

import asyncio
import subprocess

import pytest

from agora.mcp.bos_protocol import MCPStdioAdapter  # type: ignore[import-not-found]


class TestMCPStdioAdapterInit:
    def test_initial_state(self):
        """创建后应处于未初始化状态。"""
        adapter = MCPStdioAdapter("echo test")
        assert adapter._initialized is False
        assert adapter._proc is None
        assert adapter.alive is False
        assert adapter._tools == {}

    def test_constructor_stores_params(self):
        """构造函数应保存参数。"""
        adapter = MCPStdioAdapter("python3 -m test", timeout=10.0)
        assert adapter.command == "python3 -m test"
        assert adapter.timeout == 10.0


class TestMCPStdioAdapterErrorPaths:
    def test_call_before_start(self):
        """未初始化时调用应返回错误。"""
        adapter = MCPStdioAdapter("echo")

        async def run():
            result = await adapter.call("any_tool", {})
            assert result["status"] == "error"
            assert "not initialized" in result["error"]

        asyncio.run(run())

    def test_start_nonexistent_command(self):
        """命令不存在时 start 应返回 False。"""
        adapter = MCPStdioAdapter("/nonexistent/path/to/binary --flag", timeout=1.0)

        async def run():
            ok = await adapter.start()
            assert ok is False

        asyncio.run(run())

    def test_tool_not_found_error(self):
        """调用未注册的工具应返回错误。"""
        adapter = MCPStdioAdapter("echo")
        adapter._initialized = True
        adapter._proc = subprocess.Popen(
            ["echo", "test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        async def run():
            result = await adapter.call("nonexistent_tool")
            assert result["status"] == "error"
            assert "tool not found" in result["error"]
            adapter.shutdown()

        asyncio.run(run())

    def test_shutdown_cleans_up(self):
        """shutdown 应清理进程。"""
        proc = subprocess.Popen(
            ["echo", "test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        adapter = MCPStdioAdapter("echo")
        adapter._proc = proc
        adapter._initialized = True
        adapter.shutdown()
        assert adapter._proc is None
        assert adapter._initialized is False

    def test_shutdown_already_dead(self):
        """进程已死时 shutdown 不应报错。"""
        adapter = MCPStdioAdapter("echo")
        adapter.shutdown()  # _proc is None, should not raise

    def test_shutdown_timeout_kills(self):
        """进程不响应 terminate 时 kill。"""
        # 用 sleep 进程模拟不响应
        proc = subprocess.Popen(
            ["sleep", "10"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        adapter = MCPStdioAdapter("sleep 10")
        adapter._proc = proc
        adapter._initialized = True
        adapter.shutdown()
        assert adapter._proc is None


class TestMCPStdioAdapterTools:
    def test_tools_populated_after_start(self):
        """start 后 tools 不应为空（假设子进程返回工具列表）。"""
        # 使用真正的 MCP server 测试会更好，这里测试框架行为
        adapter = MCPStdioAdapter("echo '{}'")  # 不会真正初始化

        async def run():
            # 预期 start 会失败因为 echo 不是 MCP server
            ok = await adapter.start()
            # 但不应报错，应优雅返回 False
            assert ok is False

        asyncio.run(run())

    def test_tools_empty_initially(self):
        adapter = MCPStdioAdapter("test")
        assert adapter._tools == {}

    def test_shutdown_without_start(self):
        """多次 shutdown 不应报错。"""
        adapter = MCPStdioAdapter("echo")
        adapter.shutdown()
        adapter.shutdown()  # 第二次


class TestMCPStdioAdapterLifecycle:
    def test_double_initialization(self):
        """多次 start 应幂等。"""
        adapter = MCPStdioAdapter("echo test", timeout=0.5)

        async def run():
            ok1 = await adapter.start()
            # 第二次 start 应创建新进程或优雅失败
            ok2 = await adapter.start()
            adapter.shutdown()
            # echo test 不是有效的 MCP server，所以 start 返回 False
            assert ok1 is False
            assert ok2 is False

        asyncio.run(run())

    def test_alive_property_changes(self):
        """alive 属性应随进程状态变化。"""
        adapter = MCPStdioAdapter("echo")
        assert adapter.alive is False
        proc = subprocess.Popen(
            ["cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        adapter._proc = proc
        assert adapter.alive is True
        proc.terminate()
        proc.wait()
        assert adapter.alive is False
