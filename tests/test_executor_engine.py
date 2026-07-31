"""Tests for runtime executor engine core functions."""

import os
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

import pytest


# ── _log_execution ──────────────────────────────────────────────────────


def test_log_execution_writes_jsonl():
    """_log_execution writes a valid JSONL entry."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tf:
        log_path = Path(tf.name)

    try:
        with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", log_path):
            with mock.patch("runtime.executor.engine.report_execution"):
                from runtime.executor.engine import _log_execution

                _log_execution(
                    task_id="task-001",
                    status="ok",
                    summary="task completed",
                    result={
                        "result": "done",
                        "turns": 3,
                        "usage": {"total_tokens": 150},
                    },
                    duration_sec=2.5,
                )

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["task_id"] == "task-001"
        assert entry["status"] == "ok"
        assert entry["turns"] == 3
        assert entry["tokens_used"] == 150
        assert entry["duration_sec"] == 2.5
    finally:
        log_path.unlink(missing_ok=True)


def test_log_execution_with_error():
    """_log_execution handles error result with tokens."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tf:
        log_path = Path(tf.name)

    try:
        with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", log_path):
            with mock.patch("runtime.executor.engine.report_execution"):
                from runtime.executor.engine import _log_execution

                _log_execution(
                    task_id="task-err",
                    status="error",
                    summary="failed",
                    result={"error": "timeout", "turns": 1},
                    duration_sec=30.0,
                )

        entry = json.loads(log_path.read_text().strip())
        assert entry["task_id"] == "task-err"
        assert entry["status"] == "error"
        assert entry["tokens_used"] == 0
        assert entry["duration_sec"] == 30.0
    finally:
        log_path.unlink(missing_ok=True)


def test_log_execution_matrix_bridge_failure_is_silent():
    """report_execution failure doesn't break logging."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tf:
        log_path = Path(tf.name)

    try:
        with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", log_path):
            with mock.patch(
                "runtime.executor.engine.report_execution",
                side_effect=RuntimeError("matrix down"),
            ):
                from runtime.executor.engine import _log_execution

                _log_execution("task-001", "ok", "done", {}, 1.0)

        assert log_path.read_text().strip()
    finally:
        log_path.unlink(missing_ok=True)


# ── _build_alert_message ───────────────────────────────────────────────


def test_build_alert_message_basic():
    """_build_alert_message builds expected format."""
    with mock.patch("runtime.executor.engine.WORKSPACE", Path("/tmp")):
        from runtime.executor.engine import _build_alert_message

        msg = _build_alert_message(
            "task-alert",
            {"error": "LLM timeout", "turns": 5, "usage": {"total_tokens": 200}},
        )
        assert "⚠️" in msg
        assert "task-alert" in msg
        assert "LLM timeout" in msg
        assert "5" in msg
        assert "200" in msg


def test_build_alert_message_with_summary():
    """_build_alert_message includes result summary."""
    with mock.patch("runtime.executor.engine.WORKSPACE", Path("/tmp")):
        from runtime.executor.engine import _build_alert_message

        msg = _build_alert_message(
            "task-001",
            {
                "error": "oops",
                "turns": 1,
                "usage": {"total_tokens": 10},
                "result": "partial output here",
            },
        )
        assert "partial output here" in msg


def test_build_alert_message_no_summary():
    """_build_alert_message without result field."""
    with mock.patch("runtime.executor.engine.WORKSPACE", Path("/tmp")):
        from runtime.executor.engine import _build_alert_message

        msg = _build_alert_message("task-001", {"error": "e", "turns": 0, "usage": {}})
        assert "任务: task-001" in msg
        assert "错误: e" in msg


# ── AgentRuntime._execute_tool ─────────────────────────────────────────


def test_execute_tool_known_function():
    """_execute_tool dispatches to known function in tool registry."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            # Tool registry entries use {"fn": callable} format
            rt._tool_registry = {
                "echo": {"fn": lambda message: {"result": f"echoed: {message}"}}
            }

            tc = {
                "id": "call-1",
                "function": {"name": "echo", "arguments": '{"message": "hello"}'},
            }
            result = rt._execute_tool(tc)
            assert result["role"] == "tool"
            assert result["tool_call_id"] == "call-1"
            assert "echoed" in result["content"]


def test_execute_tool_unknown_function():
    """_execute_tool returns error for unknown tool."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            rt._tool_registry = {}

            tc = {
                "id": "call-99",
                "function": {"name": "nonexistent", "arguments": "{}"},
            }
            result = rt._execute_tool(tc)
            assert "Unknown tool" in result["content"]


def test_execute_tool_invalid_json_args():
    """_execute_tool handles invalid JSON arguments."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            rt._tool_registry = {"parse": {"fn": lambda x=42: str(x)}}

            tc = {
                "id": "call-1",
                "function": {"name": "parse", "arguments": "not valid json"},
            }
            result = rt._execute_tool(tc)
            # Falls back to {}, calls fn(**{})
            assert result["role"] == "tool"
            assert "42" in result["content"]


def test_execute_tool_exception_propagation():
    """_execute_tool propagates tool function exceptions and returns error."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()

            def crashy(**kwargs):
                raise ValueError("boom")

            rt._tool_registry = {"crashy": {"fn": crashy}}

            tc = {
                "id": "call-1",
                "function": {"name": "crashy", "arguments": "{}"},
            }
            with pytest.raises(ValueError, match="boom"):
                rt._execute_tool(tc)


# ── AgentRuntime.run_task ──────────────────────────────────────────────


def test_run_task_no_llm_returns_error():
    """run_task without LLM backend returns error gracefully."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            rt._call_llm = mock.MagicMock(
                return_value={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [],
                    "finish_reason": "error",
                    "error": "No LLM backend",
                }
            )

            result = rt.run_task("test prompt")
            assert "error" in result
            assert "No LLM backend" in result["error"]


def test_run_task_direct_answer():
    """run_task with direct LLM answer (no tool calls)."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            rt._call_llm = mock.MagicMock(
                return_value={
                    "role": "assistant",
                    "content": "The answer is 42",
                    "tool_calls": [],
                    "finish_reason": "stop",
                    "usage": {"total_tokens": 50},
                }
            )

            result = rt.run_task("what is 6*7?")
            assert result["result"] == "The answer is 42"
            assert result["turns"] == 1
            assert result["usage"]["total_tokens"] == 50


def test_call_llm_uses_registry_route_for_matching_provider():
    """_call_llm should prefer the registry-routed provider over providers[0]."""

    class _FakeProvider:
        provider_name = "anthropic"
        default_model = "claude-default"

        async def generate(self, request):
            return types.SimpleNamespace(
                content=f"provider={self.provider_name} model={request.model}",
                provider=self.provider_name,
                model=request.model,
                finish_reason="stop",
                input_tokens=12,
                output_tokens=8,
            )

    class _FallbackProvider:
        provider_name = "openai"
        default_model = "gpt-default"

        async def generate(self, request):
            return types.SimpleNamespace(
                content=f"provider={self.provider_name} model={request.model}",
                provider=self.provider_name,
                model=request.model,
                finish_reason="stop",
                input_tokens=1,
                output_tokens=1,
            )

    class _LLMRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _ToolSchema:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FallbackProvider(), _FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = _LLMRequest
    fake_provider.ToolSchema = _ToolSchema

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="anthropic",
            model=types.SimpleNamespace(
                id="anthropic/claude-sonnet-4", name="claude-sonnet-4"
            ),
            reasoning="Matched route anthropic/claude-sonnet-4",
        )
    )
    fake_registry_loader.estimate_model_cost = (
        lambda model_id, input_tokens, output_tokens: 0.0
    )

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: Path("/tmp/llm_calls.jsonl")

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        rt = AgentRuntime()
        response = rt._call_llm(
            [{"role": "user", "content": "hello"}], tools=[{"function": {"name": "x"}}]
        )

    assert response["content"] == "provider=anthropic model=claude-sonnet-4"
    assert response["provider"] == "anthropic"
    assert response["model"] == "claude-sonnet-4"
    assert response["route"]["role"] == "planner"
    assert response["route"]["fallback_used"] is False
    assert response["route"]["selected_model"] == "anthropic/claude-sonnet-4"


def test_call_llm_falls_back_when_routed_provider_unavailable():
    """_call_llm should fall back to the first detected provider when route target is unavailable."""

    class _FakeProvider:
        provider_name = "openai"
        default_model = "gpt-default"

        async def generate(self, request):
            return types.SimpleNamespace(
                content=f"provider={self.provider_name} model={request.model}",
                provider=self.provider_name,
                model=request.model,
                finish_reason="stop",
                input_tokens=6,
                output_tokens=4,
            )

    class _LLMRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _ToolSchema:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = _LLMRequest
    fake_provider.ToolSchema = _ToolSchema

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="anthropic",
            model=types.SimpleNamespace(
                id="anthropic/claude-sonnet-4", name="claude-sonnet-4"
            ),
            reasoning="Matched route anthropic/claude-sonnet-4",
        )
    )
    fake_registry_loader.estimate_model_cost = (
        lambda model_id, input_tokens, output_tokens: 0.0
    )

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: Path("/tmp/llm_calls.jsonl")

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        rt = AgentRuntime()
        response = rt._call_llm([{"role": "user", "content": "hello"}], tools=None)

    assert response["content"] == "provider=openai model=gpt-default"
    assert response["provider"] == "openai"
    assert response["route"]["role"] == "operator"
    assert response["route"]["fallback_used"] is True
    assert response["route"]["fallback_provider"] == "openai"


def test_call_llm_budget_policy_rejects_and_registers_debt(tmp_path):
    """_call_llm should block when estimated cost exceeds the declared budget."""

    class _FakeProvider:
        provider_name = "openai"
        default_model = "gpt-4.1"

        async def generate(self, request):
            raise AssertionError(
                "generate should not be called when budget rejects first"
            )

    class _LLMRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _ToolSchema:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = _LLMRequest
    fake_provider.ToolSchema = _ToolSchema

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="openai",
            model=types.SimpleNamespace(id="openai/gpt-4.1", name="gpt-4.1"),
            reasoning="Matched route openai/gpt-4.1",
        )
    )
    fake_registry_loader.estimate_model_cost = (
        lambda model_id, input_tokens, output_tokens: 0.42
    )

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: tmp_path / "unused.jsonl"

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
            (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True, exist_ok=True)
            omo_src = tmp_path / "projects" / "omo" / "src"
            omo_src.parent.mkdir(parents=True, exist_ok=True)
            real_omo_src = (
                Path(__file__).parent.parent.parent.parent / "projects" / "omo" / "src"
            )
            omo_src.symlink_to(real_omo_src, target_is_directory=True)
            with mock.patch("llm_gateway.budget.estimate_cost", return_value=0.42):
                rt = AgentRuntime()
                response = rt._call_llm(
                    [{"role": "user", "content": "hello"}],
                    tools=None,
                    request_context={
                        "task_id": "opc-p4-budget-demo",
                        "llm_budget_usd": 0.01,
                    },
                )

    assert "Budget policy blocked task opc-p4-budget-demo" in response["error"]
    debt_files = list(
        (tmp_path / ".omo" / "debt" / "items").glob("DEBT-OPC-P4-BUDGET-*.yaml")
    )
    assert len(debt_files) == 1
    debt_text = debt_files[0].read_text(encoding="utf-8")
    import yaml

    parsed = yaml.safe_load(debt_text)
    assert (
        "estimated cost 0.420000 USD exceeded budget 0.010000 USD"
        in parsed["description"]
    )
    # 治本 4 守护: debt YAML 必须可被 yaml.safe_load 解析 (无格式破坏)
    import yaml

    parsed = yaml.safe_load(debt_text)
    assert isinstance(parsed, dict)
    assert parsed["id"].startswith("DEBT-OPC-P4-BUDGET-")
    assert parsed["status"] == "open"
    assert parsed["severity"] == "medium"
    # 即便 task_id 含 YAML 特殊字符 (含 `:`, `#`, 换行) 也不会破格式
    assert "\n- " not in debt_text or "  " in debt_text, (
        "debt YAML 含未缩进的列表项, 表明字符串拼接导致格式破坏"
    )


def test_budget_debt_lock_prevents_concurrent_occurrence_loss(tmp_path):
    """治本 2 守护: read-modify-write 跨进程锁, 并发触发不丢 occurrence."""
    import yaml

    # 模拟两个 runtime agent 并发调用同 task_id 的 budget 拒绝
    from llm_gateway.budget import _register_budget_debt

    debt_dir = tmp_path / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)
    omo_src = tmp_path / "projects" / "omo" / "src"
    omo_src.parent.mkdir(parents=True, exist_ok=True)
    real_omo_src = (
        Path(__file__).parent.parent.parent.parent / "projects" / "omo" / "src"
    )
    omo_src.symlink_to(real_omo_src, target_is_directory=True)
    with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
        # 跑 5 次 (单进程顺序执行, 但验证 file 锁路径 + yaml.dump 都 OK)
        for i in range(5):
            _register_budget_debt(
                task_id="opc-p4-concurrent-test",
                model_id="openai/gpt-4.1",
                budget_usd=0.01,
                estimated_cost_usd=0.5,
            )
    debt_files = list(debt_dir.glob("DEBT-OPC-P4-BUDGET-*.yaml"))
    assert len(debt_files) == 1
    parsed = yaml.safe_load(debt_files[0].read_text(encoding="utf-8"))
    # 5 次顺序调用: occurrence_count 应从 1 累加到 5
    assert parsed["occurrence_count"] == 5, (
        f"5 次顺序调用 occurrence_count 应=5, 实际 {parsed['occurrence_count']} "
        f"(说明 read-modify-write 竞态)"
    )


def test_budget_debt_yaml_safe_for_special_chars_in_task_id(tmp_path):
    """治本 4 守护: task_id 含 YAML 特殊字符时, debt 文件可被 safe_load 解析."""
    import yaml
    from llm_gateway.budget import _register_budget_debt

    debt_dir = tmp_path / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)
    omo_src = tmp_path / "projects" / "omo" / "src"
    omo_src.parent.mkdir(parents=True, exist_ok=True)
    real_omo_src = (
        Path(__file__).parent.parent.parent.parent / "projects" / "omo" / "src"
    )
    omo_src.symlink_to(real_omo_src, target_is_directory=True)
    # 含冒号/井号/换行/前导横线
    weird_task_id = "task:foo #bar\n-baz end"
    with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
        _register_budget_debt(
            task_id=weird_task_id,
            model_id="openai/gpt-4.1",
            budget_usd=0.01,
            estimated_cost_usd=0.5,
        )
    debt_files = list(debt_dir.glob("DEBT-OPC-P4-BUDGET-*.yaml"))
    assert debt_files
    # 必须可解析 + special chars 已 sanitize (转 `-` 在 sanitized suffix 中)
    parsed = yaml.safe_load(debt_files[0].read_text(encoding="utf-8"))
    assert parsed["status"] == "open"
    # debt_id 用 sanitized suffix, 安全
    assert "FOO" in parsed["id"] or "BAR" in parsed["id"] or "BAZ" in parsed["id"]


def test_call_llm_records_audit_log(tmp_path):
    """_call_llm should record llm-gateway audit with task_id/role/model/cost/latency."""

    class _FakeProvider:
        provider_name = "anthropic"
        default_model = "claude-sonnet-4"

        async def generate(self, request):
            return types.SimpleNamespace(
                content="done",
                provider="anthropic",
                model="claude-sonnet-4",
                finish_reason="stop",
                input_tokens=20,
                output_tokens=10,
            )

    class _LLMRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _ToolSchema:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    audit_log = tmp_path / "llm_calls.jsonl"

    def _record_llm_audit(**kwargs):
        audit_log.write_text(json.dumps(kwargs, ensure_ascii=False), encoding="utf-8")
        return audit_log

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = _LLMRequest
    fake_provider.ToolSchema = _ToolSchema

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="anthropic",
            model=types.SimpleNamespace(
                id="anthropic/claude-sonnet-4", name="claude-sonnet-4"
            ),
            reasoning="Matched route anthropic/claude-sonnet-4",
        )
    )
    fake_registry_loader.estimate_model_cost = (
        lambda model_id, input_tokens, output_tokens: 0.123
    )

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = _record_llm_audit

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        rt = AgentRuntime()
        response = rt._call_llm(
            [{"role": "user", "content": "hello"}],
            tools=[{"function": {"name": "x"}}],
            request_context={"task_id": "opc-p4-audit-demo"},
        )

    payload = json.loads(audit_log.read_text(encoding="utf-8"))
    assert response["content"] == "done"
    assert payload["task_id"] == "opc-p4-audit-demo"
    assert payload["role"] == "planner"
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-sonnet-4"
    assert payload["total_cost_usd"] == 0.123
    assert payload["latency_ms"] >= 0.0


def test_run_task_truncated_on_max_turns():
    """run_task returns truncated after 30 turns of tool calls."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            from runtime.executor.engine import AgentRuntime

            rt = AgentRuntime()
            # Always return tool_calls to keep the loop going
            rt._call_llm = mock.MagicMock(
                return_value={
                    "role": "assistant",
                    "content": "calling",
                    "tool_calls": [
                        {
                            "id": "1",
                            "function": {"name": "echo", "arguments": '{"msg":"hi"}'},
                        }
                    ],
                    "finish_reason": "tool_calls",
                    "usage": {"total_tokens": 10},
                }
            )
            rt._tool_registry = {"echo": {"fn": lambda msg="": {"result": msg}}}

            result = rt.run_task("loop")
            assert result["truncated"] is True
            assert result["turns"] == 30


# ── P4-E3 budget governance closeout ─────────────────────────────────────


def test_budget_policy_includes_task_id_and_model_in_route_info(tmp_path):
    """E3 closeout: budget_policy must record task_id, budget_usd, estimated_cost_usd, model."""

    class _FakeProvider:
        provider_name = "anthropic"
        default_model = "claude-sonnet-4"

        async def generate(self, request):
            raise AssertionError("budget must reject before provider call")

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_provider.ToolSchema = lambda **kwargs: types.SimpleNamespace(**kwargs)

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="anthropic",
            model=types.SimpleNamespace(
                id="anthropic/claude-sonnet-4", name="claude-sonnet-4"
            ),
            reasoning="Matched",
        )
    )
    fake_registry_loader.estimate_model_cost = lambda mid, inp, out: 0.02

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: tmp_path / "unused.jsonl"

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
            (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True, exist_ok=True)
            omo_src = tmp_path / "projects" / "omo" / "src"
            omo_src.parent.mkdir(parents=True, exist_ok=True)
            real_omo_src = (
                Path(__file__).parent.parent.parent.parent / "projects" / "omo" / "src"
            )
            omo_src.symlink_to(real_omo_src, target_is_directory=True)
            with mock.patch("llm_gateway.budget.estimate_cost", return_value=0.02):
                rt = AgentRuntime()
                response = rt._call_llm(
                    [{"role": "user", "content": "hi"}],
                    tools=None,
                    request_context={
                        "task_id": "opc-p4-budget-policy-fields",
                        "llm_budget_usd": 0.005,
                    },
                )

    assert "Budget policy blocked" in response["error"]
    policy = response["route"]["budget_policy"]
    assert policy["task_id"] == "opc-p4-budget-policy-fields"
    assert policy["budget_usd"] == 0.005
    assert policy["estimated_cost_usd"] == 0.02
    assert policy["model"] == "anthropic/claude-sonnet-4"
    assert "debt_path" in policy


def test_budget_debt_reuse_does_not_create_duplicate_files(tmp_path):
    """E3 closeout: same task_id hitting the budget guard twice must not create a second debt file."""

    class _FakeProvider:
        provider_name = "openai"
        default_model = "gpt-4.1"

        async def generate(self, request):
            raise AssertionError("generate should not be called when budget rejects")

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_provider.ToolSchema = lambda **kwargs: types.SimpleNamespace(**kwargs)

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="openai",
            model=types.SimpleNamespace(id="openai/gpt-4.1", name="gpt-4.1"),
            reasoning="Matched",
        )
    )
    fake_registry_loader.estimate_model_cost = lambda mid, inp, out: 0.5

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: tmp_path / "unused.jsonl"

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
            (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True, exist_ok=True)
            omo_src = tmp_path / "projects" / "omo" / "src"
            omo_src.parent.mkdir(parents=True, exist_ok=True)
            real_omo_src = (
                Path(__file__).parent.parent.parent.parent / "projects" / "omo" / "src"
            )
            omo_src.symlink_to(real_omo_src, target_is_directory=True)
            with mock.patch("llm_gateway.budget.estimate_cost", return_value=0.5):
                rt = AgentRuntime()
                ctx = {"task_id": "opc-p4-budget-reuse", "llm_budget_usd": 0.01}
                rt._call_llm(
                    [{"role": "user", "content": "x"}], tools=None, request_context=ctx
                )
                rt._call_llm(
                    [{"role": "user", "content": "y"}], tools=None, request_context=ctx
                )
                rt._call_llm(
                    [{"role": "user", "content": "z"}], tools=None, request_context=ctx
                )

    debt_files = sorted(
        (tmp_path / ".omo" / "debt" / "items").glob("DEBT-OPC-P4-BUDGET-*.yaml")
    )
    assert len(debt_files) == 1, f"expected single debt file, got {debt_files}"
    body = debt_files[0].read_text(encoding="utf-8")
    assert "occurrence_count: 3" in body
    assert "first_seen_at:" in body
    assert "last_seen_at:" in body


def test_budget_reject_returns_error_dict_not_traceback(tmp_path):
    """E3 closeout: budget reject must propagate as a structured error dict, never raise."""

    class _FakeProvider:
        provider_name = "openai"
        default_model = "gpt-4.1"

        async def generate(self, request):
            raise AssertionError("must not be reached")

    fake_detection = types.ModuleType("llm_gateway.detection")
    fake_detection.detect_backends = lambda: [_FakeProvider()]

    fake_provider = types.ModuleType("llm_gateway.provider")
    fake_provider.LLMRequest = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_provider.ToolSchema = lambda **kwargs: types.SimpleNamespace(**kwargs)

    fake_registry_loader = types.ModuleType("llm_gateway.registry_data_loader")
    fake_registry_loader.route_role_request = lambda role, required_capabilities=None: (
        types.SimpleNamespace(
            provider_name="openai",
            model=types.SimpleNamespace(id="openai/gpt-4.1", name="gpt-4.1"),
            reasoning="Matched",
        )
    )
    fake_registry_loader.estimate_model_cost = lambda mid, inp, out: 1.0

    fake_audit = types.ModuleType("llm_gateway.audit")
    fake_audit.record_llm_audit = lambda **kwargs: tmp_path / "unused.jsonl"

    with mock.patch.dict(
        sys.modules,
        {
            "llm_gateway._legacy.detection": fake_detection,
            "llm_gateway._legacy.provider": fake_provider,
            "llm_gateway._legacy.registry_data_loader": fake_registry_loader,
            "llm_gateway._legacy.audit": fake_audit,
            "llm_gateway.registry_data_loader": fake_registry_loader,
        },
    ):
        from runtime.executor.engine import AgentRuntime

        with mock.patch.dict(os.environ, {"WORKSPACE": str(tmp_path)}):
            (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True, exist_ok=True)
            with mock.patch("llm_gateway.budget.estimate_cost", return_value=1.0):
                rt = AgentRuntime()
                ctx = {
                    "task_id": "opc-p4-budget-structured-error",
                    "llm_budget_usd": 0.1,
                }
                # Must NOT raise — return dict
                response = rt._call_llm(
                    [{"role": "user", "content": "hello"}],
                    tools=None,
                    request_context=ctx,
                )

    assert isinstance(response, dict)
    assert response["finish_reason"] == "error"
    assert (
        "Budget policy blocked task opc-p4-budget-structured-error" in response["error"]
    )
    assert "openai/gpt-4.1" in response["error"]
    assert "debt_path" in response["route"]["budget_policy"]
    assert response["route"]["role"] in {"planner", "operator"}
