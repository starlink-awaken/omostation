"""Tests for agent_runtime_mcp_server.py"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# Pre-mock runtime dependencies
_mock_runtime = mock.MagicMock()
_mock_runtime_executor = mock.MagicMock()
_mock_runtime_engine = mock.MagicMock()

# 只 mock runtime.executor 子模块, 保留真实的 runtime 包.
sys.modules["runtime.executor.engine"] = _mock_runtime_engine
sys.modules["runtime.executor.config"] = mock.MagicMock()

# Now safe to import

from cockpit import agent_runtime_mcp_server


def _verified_binding():
    return mock.patch.object(
        agent_runtime_mcp_server.capability_binding,
        "verify_binding_envelope",
        return_value=True,
    )


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
                with _verified_binding():
                    result = agent_runtime_mcp_server.run_task(
                        "daily-summary",
                        binding_receipt={"schema": "capability-admission-verification-request/v1"},
                    )
                assert result == "Today was good"

    def test_run_task_not_found(self):
        """任务定义目录/文件不存在"""
        with mock.patch("pathlib.Path.exists", return_value=False):
            with _verified_binding():
                result = agent_runtime_mcp_server.run_task(
                    "nonexistent",
                    binding_receipt={"schema": "capability-admission-verification-request/v1"},
                )
            assert "not found" in result

    def test_run_task_no_prompt(self):
        """任务定义中无 prompt"""
        import json

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps({"no_prompt": 1})):
                with _verified_binding():
                    result = agent_runtime_mcp_server.run_task(
                        "empty-task",
                        binding_receipt={"schema": "capability-admission-verification-request/v1"},
                    )
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
                with _verified_binding():
                    result = agent_runtime_mcp_server.run_task(
                        "bad-task",
                        binding_receipt={"schema": "capability-admission-verification-request/v1"},
                    )
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
                with _verified_binding():
                    result = agent_runtime_mcp_server.run_task(
                        "empty-result",
                        binding_receipt={"schema": "capability-admission-verification-request/v1"},
                    )
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

        with _verified_binding():
            result = agent_runtime_mcp_server.chat(
                "read test.txt",
                binding_receipt={"schema": "capability-admission-verification-request/v1"},
            )
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


def test_run_task_rejected_binding_does_not_construct_runtime_or_execute(monkeypatch):
    forbidden = mock.Mock(side_effect=AssertionError("runtime must not be constructed"))
    monkeypatch.setattr(agent_runtime_mcp_server, "get_runtime", forbidden)
    monkeypatch.setattr(
        agent_runtime_mcp_server.capability_binding,
        "verify_binding_envelope",
        lambda _envelope: False,
    )

    result = json.loads(
        agent_runtime_mcp_server.run_task(
            "daily-summary",
            binding_receipt={"schema": "capability-admission-verification-request/v1"},
        )
    )

    assert result["authority_state"] == "non_authoritative"
    forbidden.assert_not_called()


def test_mcp_chat_rejected_binding_does_not_construct_runtime_or_tools(monkeypatch):
    forbidden = mock.Mock(side_effect=AssertionError("runtime must not be constructed"))
    monkeypatch.setattr(agent_runtime_mcp_server, "get_runtime", forbidden)
    monkeypatch.setattr(
        agent_runtime_mcp_server.capability_binding,
        "verify_binding_envelope",
        lambda _envelope: False,
    )

    result = json.loads(
        agent_runtime_mcp_server.chat(
            "hello",
            binding_receipt={"schema": "capability-admission-verification-request/v1"},
        )
    )

    assert result["authority_state"] == "non_authoritative"
    assert result["tools"] == []
    forbidden.assert_not_called()


def test_mcp_unbound_chat_never_builds_or_executes_tools():
    mock_rt = mock.MagicMock()
    mock_rt._call_llm.return_value = {
        "content": None,
        "finish_reason": "tool_calls",
        "tool_calls": [{"id": "1", "function": {"name": "shell", "arguments": "{}"}}],
    }
    agent_runtime_mcp_server._runtime = mock_rt

    result = json.loads(agent_runtime_mcp_server.chat("hello"))

    assert result["authority_state"] == "non_authoritative"
    assert result["tools"] == []
    mock_rt._build_tool_schemas.assert_not_called()
    mock_rt._execute_tool.assert_not_called()


class TestMain:
    """main() 入口测试"""

    def test_main_runs_mcp(self):
        """main() 启动 MCP server"""
        with mock.patch.object(agent_runtime_mcp_server.mcp, "run") as mock_run:
            agent_runtime_mcp_server.main()
            mock_run.assert_called_once_with(transport="stdio")


class TestL0ToolRegistration:
    """L0 治理工具自动注册 (P78 audit: 8 个 l0_mcp_tools 工具必须暴露)"""

    def test_l0_tools_registered(self):
        """L0 工具在 mcp 中可调用"""
        import asyncio

        from cockpit import l0_mcp_tools

        tools = asyncio.run(agent_runtime_mcp_server.mcp.list_tools())
        names = {t.name for t in tools}
        expected = set(l0_mcp_tools.MCP_TOOLS.keys())
        missing = expected - names
        assert not missing, f"L0 tools not registered: {missing}"

    def test_l0_tools_have_descriptions(self):
        """L0 工具都带 description 注解"""
        import asyncio

        tools = asyncio.run(agent_runtime_mcp_server.mcp.list_tools())
        for t in tools:
            if t.name in {"run_task", "chat"}:
                continue  # builtin agent-runtime tools
            assert t.description, f"Tool {t.name} missing description"


class TestGovernanceTools:
    """Cowork 客户端通过同一个 MCP server 获取只读 SSOT 投影。"""

    def test_governance_tools_registered(self):
        import asyncio

        tools = asyncio.run(agent_runtime_mcp_server.mcp.list_tools())
        names = {tool.name for tool in tools}
        assert {
            "workspace_context",
            "domains_list",
            "domain_context",
            "domain_project_status",
            "domain_facts_audit",
            "domain_facts_validation_status",
            "domain_controller_shadow_status",
            "domain_model_freshness_status",
            "domain_sanyi_status_consistency_status",
            "cards_status",
            "cards_check",
            "kems_status",
        } <= names

    def test_workspace_context_returns_stable_json_from_adapter(self, monkeypatch):
        payload = {"schema": "cockpit.governance-context.v1", "status": "degraded", "available": True}
        monkeypatch.setattr(agent_runtime_mcp_server.governance_context, "workspace_context", lambda: payload)

        assert json.loads(agent_runtime_mcp_server.workspace_context()) == payload

    def test_domain_context_passes_domain_id_to_adapter(self, monkeypatch):
        seen = []
        payload = {"schema": "cockpit.domain-context.v1", "status": "unavailable", "available": False}
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_context",
            lambda domain_id: seen.append(domain_id) or payload,
        )

        assert json.loads(agent_runtime_mcp_server.domain_context("unknown")) == payload
        assert seen == ["unknown"]

    def test_domain_context_redacts_documents_root_from_mcp_envelope(self, tmp_path: Path, monkeypatch):
        documents_root = tmp_path / "Documents"
        payload = {
            "schema": "cockpit.domain-context.v1",
            "status": "ok",
            "available": True,
            "domain_id": "work-weijian",
            "domain": {
                "id": "work-weijian",
                "path": str(documents_root / "@工作文档" / "卫健委"),
            },
            "binding": {
                "status": "ok",
                "profile_id": "content-domain",
                "capability_routes": {"workflows": {"status": "ok"}},
            },
            "sources": {"domain_registry": str(documents_root / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml")},
        }
        monkeypatch.setenv("L4_DOCUMENTS_ROOT", str(documents_root))
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_context",
            lambda _domain_id: payload,
        )

        serialized = agent_runtime_mcp_server.domain_context("work-weijian")
        result = json.loads(serialized)

        assert str(documents_root) not in serialized
        assert result["domain_id"] == "work-weijian"
        assert result["binding"]["profile_id"] == "content-domain"
        assert result["binding"]["capability_routes"]["workflows"]["status"] == "ok"

    def test_domain_project_status_passes_domain_id_to_adapter(self, monkeypatch):
        seen = []
        payload = {"schema": "cockpit.domain-project-status.v1", "status": "ok", "available": True}
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_project_status",
            lambda domain_id="": seen.append(domain_id) or payload,
        )

        assert json.loads(agent_runtime_mcp_server.domain_project_status("vault")) == payload
        assert seen == ["vault"]

    def test_domain_facts_audit_passes_domain_id_and_returns_parseable_envelope(self, monkeypatch):
        seen = []
        payload = {"schema": "cockpit.domain-facts-audit.v1", "status": "ok", "available": True}
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_facts_audit",
            lambda domain_id="": seen.append(domain_id) or payload,
        )

        assert json.loads(agent_runtime_mcp_server.domain_facts_audit("vault")) == payload
        assert seen == ["vault"]

    def test_domain_facts_validation_status_passes_domain_id_and_returns_parseable_envelope(self, monkeypatch):
        seen = []
        payload = {"schema": "cockpit.domain-facts-validation.v1", "status": "ok", "available": True}
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_facts_validation_status",
            lambda domain_id="": seen.append(domain_id) or payload,
        )

        assert json.loads(agent_runtime_mcp_server.domain_facts_validation_status("vault")) == payload
        assert seen == ["vault"]

    def test_domain_controller_shadow_status_passes_domain_id_and_returns_parseable_envelope(self, monkeypatch):
        seen = []
        payload = {"schema": "cockpit.domain-controller-shadow.v2", "status": "shadow_observed", "available": True}
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_controller_shadow_status",
            lambda domain_id: seen.append(domain_id) or payload,
        )

        assert json.loads(agent_runtime_mcp_server.domain_controller_shadow_status("vault")) == payload
        assert seen == ["vault"]

    @pytest.mark.parametrize(
        ("status", "available"),
        [("ok", True), ("attention", True), ("unavailable", False)],
    )
    def test_domain_model_freshness_status_passes_domain_id_and_returns_parseable_envelope(
        self, monkeypatch, status, available
    ):
        seen = []
        payload = {
            "schema": "cockpit.domain-model-freshness.v1",
            "status": status,
            "available": available,
            "sources": {
                "domain_registry": "l4-domain-registry",
                "binding_registry": "workspace-documents-domain-projects",
                "runtime_evidence": "runtime-model-freshness-evidence",
            },
        }
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_model_freshness_status",
            lambda domain_id: seen.append(domain_id) or payload,
            raising=False,
        )

        output = agent_runtime_mcp_server.domain_model_freshness_status("vault")
        assert json.loads(output) == payload
        assert "/Users/reviewer/Documents" not in output
        assert seen == ["vault"]

    def test_domain_model_freshness_status_actual_adapter_redacts_documents_registry_failure(
        self, tmp_path: Path, monkeypatch
    ):
        workspace_root = tmp_path / "workspace"
        documents_root = tmp_path / "Documents-private"
        registry_path = documents_root / "private-domain-registry.yaml"
        workspace_root.mkdir()
        documents_root.mkdir()
        monkeypatch.setenv("WORKSPACE_ROOT", str(workspace_root))
        monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

        output = agent_runtime_mcp_server.domain_model_freshness_status("vault")
        payload = json.loads(output)
        assert payload["status"] == "unavailable"
        assert payload["error"] == "domain_registry_unavailable"
        assert payload["sources"]["domain_registry"] == "l4-domain-registry"
        assert str(documents_root) not in output
        assert registry_path.name not in output
        assert str(registry_path) not in output

    def test_domain_model_freshness_status_exception_boundary_returns_pathless_unavailable_envelope(
        self, tmp_path: Path, monkeypatch
    ):
        documents_root = tmp_path / "Documents-private"
        secret_path = documents_root / "private-domain-registry.yaml"

        def raise_documents_path(_domain_id):
            raise RuntimeError(f"failed to load {secret_path}")

        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_model_freshness_status",
            raise_documents_path,
        )

        output = agent_runtime_mcp_server.domain_model_freshness_status("work-weijian")
        assert json.loads(output) == {
            "schema": "cockpit.domain-model-freshness.v1",
            "status": "unavailable",
            "available": False,
            "domain_id": "work-weijian",
            "job": None,
            "freshness": None,
            "sources": {
                "domain_registry": "l4-domain-registry",
                "binding_registry": "workspace-documents-domain-projects",
            },
            "error": "model_freshness_mcp_unavailable",
        }
        assert str(documents_root) not in output
        assert secret_path.name not in output

    def test_domain_sanyi_status_consistency_delegates_and_preserves_the_envelope(self, monkeypatch):
        seen = []
        payload = {
            "schema": "cockpit.domain-sanyi-status-consistency.v1",
            "status": "attention",
            "available": True,
            "sources": {
                "domain_registry": "l4-domain-registry",
                "binding_registry": "workspace-documents-domain-projects",
                "runtime_evidence": "runtime-sanyi-status-consistency-evidence",
            },
        }
        monkeypatch.setattr(
            agent_runtime_mcp_server.governance_context,
            "domain_sanyi_status_consistency_status",
            lambda domain_id: seen.append(domain_id) or payload,
            raising=False,
        )

        assert json.loads(agent_runtime_mcp_server.domain_sanyi_status_consistency_status("work-weijian")) == payload
        assert seen == ["work-weijian"]
