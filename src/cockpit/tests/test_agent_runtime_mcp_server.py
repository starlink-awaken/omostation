"""Tests for agent_runtime_mcp_server.py"""

import sys
from unittest import mock

# Pre-mock runtime dependencies
_mock_runtime = mock.MagicMock()
_mock_runtime_executor = mock.MagicMock()
_mock_runtime_engine = mock.MagicMock()

sys.modules["runtime"] = _mock_runtime
sys.modules["runtime.executor"] = _mock_runtime_executor
sys.modules["runtime.executor.engine"] = _mock_runtime_engine
sys.modules["runtime.executor.config"] = mock.MagicMock()

# Now safe to import

from cockpit import agent_runtime_mcp_server


class TestGetRuntime:
    """get_runtime() 单例测试"""

    def test_get_runtime_creates_instance(self):
        """首次调用创建 AgentRuntime 实例"""
        agent_runtime_mcp_server._runtime = None
        result = agent_runtime_mcp_server.get_runtime()
        assert result is not None
        assert agent_runtime_mcp_server._runtime is result

    def test_get_runtime_returns_cached_instance(self):
        """再次调用返回缓存实例"""
        agent_runtime_mcp_server._runtime = None
        first = agent_runtime_mcp_server.get_runtime()
        second = agent_runtime_mcp_server.get_runtime()
        assert first is second


class TestRunTask:
    """run_task MCP 工具测试"""

    def test_run_task_success(self):
        """成功执行预定义任务"""
        import json

        task_def = {"prompt": "summarize the day"}
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {"result": "Today was good"}
        agent_runtime_mcp_server._runtime = mock_rt

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps(task_def)):
                result = agent_runtime_mcp_server.run_task("daily-summary")
                assert result == "Today was good"

    def test_run_task_not_found(self):
        """任务定义目录/文件不存在"""
        with mock.patch("pathlib.Path.exists", return_value=False):
            result = agent_runtime_mcp_server.run_task("nonexistent")
            assert "not found" in result

    def test_run_task_no_prompt(self):
        """任务定义中无 prompt"""
        import json

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps({"no_prompt": 1})):
                result = agent_runtime_mcp_server.run_task("empty-task")
                assert "no prompt" in result

    def test_run_task_with_error(self):
        """任务执行返回错误"""
        import json

        task_def = {"prompt": "do something"}
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {"error": "something broke"}
        agent_runtime_mcp_server._runtime = mock_rt

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps(task_def)):
                result = agent_runtime_mcp_server.run_task("bad-task")
                assert "[ERROR]" in result
                assert "something broke" in result

    def test_run_task_empty_response(self):
        """任务返回空结果"""
        import json

        task_def = {"prompt": "do nothing"}
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {}
        agent_runtime_mcp_server._runtime = mock_rt

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps(task_def)):
                result = agent_runtime_mcp_server.run_task("empty-result")
                assert "empty response" in result


class TestChat:
    """chat MCP 工具测试"""

    def test_chat_basic_message(self):
        """基本单轮消息"""
        mock_rt = mock.MagicMock()
        mock_rt._build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"content": "Hello!", "finish_reason": "stop"}
        agent_runtime_mcp_server._runtime = mock_rt

        result = agent_runtime_mcp_server.chat("hi")
        assert result == "Hello!"

    def test_chat_with_history(self):
        """多轮对话历史"""
        import json

        mock_rt = mock.MagicMock()
        mock_rt._build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"content": "Yes!", "finish_reason": "stop"}
        agent_runtime_mcp_server._runtime = mock_rt

        history = [
            {"role": "user", "content": "what is python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]
        result = agent_runtime_mcp_server.chat("is it popular?", history_json=json.dumps(history))
        assert result == "Yes!"

    def test_chat_with_invalid_history_json(self):
        """无效的历史 JSON 被忽略"""
        mock_rt = mock.MagicMock()
        mock_rt._build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"content": "Still works", "finish_reason": "stop"}
        agent_runtime_mcp_server._runtime = mock_rt

        result = agent_runtime_mcp_server.chat("hi", history_json="not valid json")
        assert result == "Still works"

    def test_chat_with_tool_calls(self):
        """带工具调用的对话"""
        mock_rt = mock.MagicMock()
        mock_rt._build_tool_schemas.return_value = [{"name": "read_file"}]
        mock_rt._call_llm.side_effect = [
            {
                "content": None,
                "finish_reason": "tool_calls",
                "tool_calls": [{"id": "1", "function": {"name": "read_file", "arguments": '{"path":"test.txt"}'}}],
            },
            {"content": "File contents here", "finish_reason": "stop"},
        ]
        mock_rt._execute_tool.return_value = {"role": "tool", "content": "file data"}
        agent_runtime_mcp_server._runtime = mock_rt

        result = agent_runtime_mcp_server.chat("read test.txt")
        assert result == "File contents here"
        mock_rt._execute_tool.assert_called()

    def test_chat_llm_error(self):
        """LLM 调用返回错误"""
        mock_rt = mock.MagicMock()
        mock_rt._build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"error": "LLM timeout"}
        agent_runtime_mcp_server._runtime = mock_rt

        result = agent_runtime_mcp_server.chat("hi")
        assert "错误" in result
        assert "LLM timeout" in result


class TestMain:
    """main() 入口测试"""

    def test_main_runs_mcp(self):
        """main() 启动 MCP server"""
        with mock.patch.object(agent_runtime_mcp_server.mcp, "run") as mock_run:
            agent_runtime_mcp_server.main()
            mock_run.assert_called_once_with(transport="stdio")
