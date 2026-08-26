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

# 只 mock runtime.executor 子模块, 保留真实的 runtime 包.
sys.modules["runtime.executor.config"] = _mock_runtime_config
sys.modules["runtime.executor.engine"] = _mock_runtime_engine

# Now safe to import
from fastapi.testclient import TestClient

from cockpit import agent_runtime_server


class TestCreateApp:
    """create_app() 测试"""

    def _install_runtime(self, mock_rt):
        """SFOP adapter seam: create_app uses agent_runtime_server.AgentRuntime."""
        _mock_runtime_engine.AgentRuntime.return_value = mock_rt
        agent_runtime_server.AgentRuntime = mock.Mock(return_value=mock_rt)
        agent_runtime_server._HAS_RUNTIME = True

    def _make_app(self, auth_token=""):
        """创建测试用 FastAPI app"""
        _mock_runtime_config.AUTH_TOKEN = auth_token
        agent_runtime_server.AUTH_TOKEN = auth_token
        mock_rt = mock.MagicMock()
        mock_rt.model = "mock-model"
        mock_rt.run_task.return_value = {"result": "ok"}
        mock_rt.tools.build_tool_schemas.return_value = []
        mock_rt._call_llm.return_value = {"content": "Hello!", "finish_reason": "stop"}
        self._install_runtime(mock_rt)
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
        app = self._make_app(auth_token="test-token")  # noqa: S106 (测试用假 token)
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
        self._install_runtime(mock_rt)

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
        self._install_runtime(mock_rt)

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=True):
            response = client.post(
                "/chat",
                json={
                    "message": "read",
                    "binding_receipt": {"schema": "capability-admission-verification-request/v1"},
                },
            )
        assert response.status_code == 200
        mock_rt._execute_tool.assert_called()

    def test_chat_session_truncated(self):
        """POST /chat 达到最大轮次数时返回 truncated"""
        mock_rt = mock.MagicMock()
        mock_rt.tools.build_tool_schemas.return_value = [{"name": "always_call"}]
        # 始终返回 tool_calls 使循环耗尽
        responses = []
        for _ in range(30):
            responses.append(
                {
                    "content": "calling tool",
                    "finish_reason": "tool_calls",
                    "tool_calls": [{"id": "1", "function": {"name": "always_call", "arguments": "{}"}}],
                }
            )
        mock_rt._call_llm.side_effect = responses
        mock_rt._execute_tool.return_value = {"role": "tool", "content": "data"}
        self._install_runtime(mock_rt)

        app = agent_runtime_server.create_app()
        client = TestClient(app)
        with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=True):
            response = client.post(
                "/chat",
                json={
                    "message": "loop",
                    "binding_receipt": {"schema": "capability-admission-verification-request/v1"},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("truncated") is True

    def test_run_task_direct_prompt(self):
        """POST /run-task 直接传 prompt"""
        mock_rt = mock.MagicMock()
        mock_rt.run_task.return_value = {"result": "done"}
        self._install_runtime(mock_rt)

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
        self._install_runtime(mock_rt)

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
            self._install_runtime(mock_rt)

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
            self._install_runtime(mock_rt)

            app = agent_runtime_server.create_app()
            client = TestClient(app)
            response = client.post("/chat", json={"message": "hi"}, headers={"Authorization": "Bearer secret"})
            assert response.status_code == 200
            assert response.json()["response"] == "authorized"

    def test_auth_wrong_token(self):
        """错误 Bearer token 返回 401"""
        with mock.patch.object(agent_runtime_server, "AUTH_TOKEN", "secret"):
            mock_rt = mock.MagicMock()
            mock_rt.tools.build_tool_schemas.return_value = []
            mock_rt._call_llm.return_value = {"content": "test", "finish_reason": "stop"}
            self._install_runtime(mock_rt)

            app = agent_runtime_server.create_app()
            client = TestClient(app)
            response = client.post("/chat", json={"message": "hi"}, headers={"Authorization": "Bearer wrong"})
            assert response.status_code == 401


def _client_with_tmp_log(tmp_path):
    t = TestCreateApp()
    app = t._make_app()
    agent_runtime_server.EXEC_LOG_FILE = tmp_path / "exec.log"
    return TestClient(app)


def test_run_task_effectful_without_binding_is_403(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    response = client.post("/run-task", json={"prompt": "do it", "tools": ["shell"]})
    assert response.status_code == 403
    assert "verified capability binding" in response.json()["detail"]


def test_run_task_with_binding_receipt_passes_gate(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=True):
        response = client.post(
            "/run-task",
            json={
                "prompt": "do it",
                "tools": ["shell"],
                "binding_receipt": {"schema": "capability-admission-verification-request/v1"},
            },
        )
    assert response.status_code == 200
    assert response.json()["authority_state"] == "bound"


def test_chat_without_binding_reports_non_authoritative(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["authority_state"] == "non_authoritative"


def test_run_task_rejected_binding_has_zero_runtime_effects(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    runtime = agent_runtime_server.AgentRuntime.return_value
    envelope = {"schema": "capability-admission-verification-request/v1"}

    with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=False):
        response = client.post(
            "/run-task",
            json={"prompt": "do it", "tools": ["shell"], "binding_receipt": envelope},
        )

    assert response.status_code == 403
    runtime.run_task.assert_not_called()
    runtime.tools.build_tool_schemas.assert_not_called()
    runtime._execute_tool.assert_not_called()


def test_chat_rejected_binding_has_zero_schema_or_tool_execution(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    runtime = agent_runtime_server.AgentRuntime.return_value
    envelope = {"schema": "capability-admission-verification-request/v1"}

    with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=False):
        response = client.post("/chat", json={"message": "hello", "binding_receipt": envelope})

    assert response.status_code == 403
    runtime.tools.build_tool_schemas.assert_not_called()
    runtime._call_llm.assert_not_called()
    runtime._execute_tool.assert_not_called()


def test_chat_verified_binding_builds_tools_and_reports_bound(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    runtime = agent_runtime_server.AgentRuntime.return_value
    envelope = {"schema": "capability-admission-verification-request/v1"}

    with mock.patch.object(agent_runtime_server.capability_binding, "verify_binding_envelope", return_value=True):
        response = client.post("/chat", json={"message": "hello", "binding_receipt": envelope})

    assert response.status_code == 200
    assert response.json()["authority_state"] == "bound"
    runtime.tools.build_tool_schemas.assert_called_once_with()


def test_unbound_chat_does_not_execute_unrequested_tool_calls(tmp_path):
    client = _client_with_tmp_log(tmp_path)
    runtime = agent_runtime_server.AgentRuntime.return_value
    runtime._call_llm.return_value = {
        "content": None,
        "finish_reason": "tool_calls",
        "tool_calls": [{"id": "1", "function": {"name": "shell", "arguments": "{}"}}],
    }

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["authority_state"] == "non_authoritative"
    runtime.tools.build_tool_schemas.assert_not_called()
    runtime._execute_tool.assert_not_called()
