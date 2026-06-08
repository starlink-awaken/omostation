"""Tests for agent_runtime_server.py"""

import sys
from unittest import mock

# Pre-mock runtime dependencies before any import
_mock_runtime = mock.MagicMock()
_mock_runtime_executor = mock.MagicMock()
_mock_runtime_config = mock.MagicMock()
_mock_runtime_engine = mock.MagicMock()

_mock_runtime_config.AUTH_TOKEN = ""
_mock_runtime_config.EXEC_LOG_FILE = mock.MagicMock()
_mock_runtime_config.log = mock.MagicMock()
_mock_runtime_config.setup_logging = mock.MagicMock()

sys.modules["runtime"] = _mock_runtime
sys.modules["runtime.executor"] = _mock_runtime_executor
sys.modules["runtime.executor.config"] = _mock_runtime_config
sys.modules["runtime.executor.engine"] = _mock_runtime_engine

# Now safe to import
from cockpit import agent_runtime_server
import pytest
from fastapi.testclient import TestClient


class TestCreateApp:
    """create_app() 测试"""

    def _make_app(self, auth_token=""):
        """创建测试用 FastAPI app"""
        _mock_runtime_config.AUTH_TOKEN = auth_token
        mock_rt = mock.MagicMock()
        mock_rt.model = "mock-model"
        mock_rt.run_task.return_value = {"result": "ok"}
        mock_rt.tools.build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"content": "Hello!", "finish_reason": "stop"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt
        return agent_runtime_server.create_app()

    def test_health_endpoint(self):
        """GET /health 返回状态"""
        app = self._make_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_bypasses_auth(self):
        """GET /health 有认证配置仍应放行"""
        app = self._make_app(auth_token="test-token")
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_chat_basic(self):
        """POST /chat 基本对话"""
        app = self._make_app()
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hi"})
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello!"
        assert "duration_sec" in data

    def test_chat_with_history(self):
        """POST /chat 带历史"""
        app = self._make_app()
        client = TestClient(app)
        response = client.post(
            "/chat",
            json={
                "message": "ok",
                "history": [{"role": "user", "content": "hey"}, {"role": "assistant", "content": "hi"}],
            },
        )
        assert response.status_code == 200
        assert response.json()["response"] == "Hello!"

    def test_chat_with_invalid_history(self):
        """POST /chat 无效历史条目被过滤"""
        app = self._make_app()
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hi", "history": [{"bad": "entry"}]})
        assert response.status_code == 200

    def test_chat_llm_error(self):
        """POST /chat LLM 返回错误"""
        mock_rt = mock.MagicMock()
        mock_rt.tools.build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"error": "timeout"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hi"})
        assert response.status_code == 200
        assert "错误" in response.json()["response"]

    def test_chat_with_tool_calls(self):
        """POST /chat 带工具调用"""
        mock_rt = mock.MagicMock()
        mock_rt.tools.build_tool_schemas.return_value = [{"name": "read"}]
        mock_rt._call_llm.side_effect = [
            {
                "content": None,
                "finish_reason": "tool_calls",
                "tool_calls": [{"id": "1", "function": {"name": "read", "arguments": "{}"}}],
            },
            {"content": "result", "finish_reason": "stop"},
        ]
        mock_rt._execute_tool.return_value = {"role": "tool", "content": "data"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        response = client.post("/chat", json={"message": "read"})
        assert response.status_code == 200
        mock_rt._execute_tool.assert_called()

    def test_chat_session_truncated(self):
        """POST /chat 达到最大轮次数时返回 truncated"""
        mock_rt = mock.MagicMock()
        mock_rt.tools.build_tool_schemas.return_value = [{"name": "always_call"}]
        # 始终返回 tool_calls 使循环耗尽
        responses = []
        for _ in range(30):
            responses.append({
                "content": "calling tool",
                "finish_reason": "tool_calls",
                "tool_calls": [{"id": "1", "function": {"name": "always_call", "arguments": "{}"}}],
            })
        mock_rt._call_llm.side_effect = responses
        mock_rt._execute_tool.return_value = {"role": "tool", "content": "data"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        response = client.post("/chat", json={"message": "loop"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("truncated") is True

    def test_run_task_direct_prompt(self):
        """POST /run-task 直接传 prompt"""
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {"result": "done"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        response = client.post("/run-task", json={"prompt": "hello"})
        assert response.status_code == 200
        assert response.json()["result"] == "done"

    def test_run_task_no_prompt_or_task(self):
        """POST /run-task 无 prompt 无 task 返回 400"""
        app = self._make_app()
        client = TestClient(app)
        response = client.post("/run-task", json={})
        assert response.status_code == 400

    def test_run_task_with_error(self):
        """POST /run-task 执行失败返回 500"""
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {"error": "execution failed"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        with mock.patch("cockpit.agent_runtime_server._log_execution"):
            with mock.patch("cockpit.agent_runtime_server._build_alert_message", return_value="alert"):
                with mock.patch.object(mock_rt.tools, "send_message", create=True):
                    response = client.post("/run-task", json={"prompt": "fail"})
                    assert response.status_code == 500

    def test_auth_required(self):
        """无 Bearer token 返回 401"""
        # AUTH_TOKEN 在模块级 import 时已绑定，需直接 patch
        with mock.patch.object(agent_runtime_server, "AUTH_TOKEN", "secret"):
            mock_rt = mock.MagicMock()
            mock_rt.tools.build_tool_schemas.return_value = []
            mock_rt._call_llm.return_value = {"content": "test", "finish_reason": "stop"}
            _mock_runtime_engine.AgentRuntime.return_value = mock_rt

            app = agent_runtime_server.create_app()
            client = TestClient(app)
            response = client.post("/chat", json={"message": "hi"})
            assert response.status_code == 401

    def test_auth_valid(self):
        """有效 Bearer token 正常通过"""
        with mock.patch.object(agent_runtime_server, "AUTH_TOKEN", "secret"):
            mock_rt = mock.MagicMock()
            mock_rt.tools.build_tool_schemas.return_value = []
            mock_rt._call_llm.return_value = {"content": "authorized", "finish_reason": "stop"}
            _mock_runtime_engine.AgentRuntime.return_value = mock_rt

            app = agent_runtime_server.create_app()
            client = TestClient(app)
            response = client.post(
                "/chat", json={"message": "hi"}, headers={"Authorization": "Bearer secret"}
            )
            assert response.status_code == 200
            assert response.json()["response"] == "authorized"

    def test_auth_wrong_token(self):
        """错误 Bearer token 返回 401"""
        with mock.patch.object(agent_runtime_server, "AUTH_TOKEN", "secret"):
            mock_rt = mock.MagicMock()
            mock_rt.tools.build_tool_schemas.return_value = []
            mock_rt._call_llm.return_value = {"content": "test", "finish_reason": "stop"}
            _mock_runtime_engine.AgentRuntime.return_value = mock_rt

            app = agent_runtime_server.create_app()
            client = TestClient(app)
            response = client.post(
                "/chat", json={"message": "hi"}, headers={"Authorization": "Bearer wrong"}
            )
            assert response.status_code == 401
