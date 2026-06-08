"""Tests for runtime executor engine core functions."""

import json
import tempfile
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
                    result={"result": "done", "turns": 3, "usage": {"total_tokens": 150}},
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
                "runtime.executor.engine.report_execution", side_effect=RuntimeError("matrix down")
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

        msg = _build_alert_message("task-alert", {"error": "LLM timeout", "turns": 5, "usage": {"total_tokens": 200}})
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
            with mock.patch("runtime.executor.engine.register_executor_service"):
                from runtime.executor.engine import AgentRuntime

                rt = AgentRuntime()
                # Tool registry entries use {"fn": callable} format
                rt._tool_registry = {"echo": {"fn": lambda message: {"result": f"echoed: {message}"}}}

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
            with mock.patch("runtime.executor.engine.register_executor_service"):
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
            with mock.patch("runtime.executor.engine.register_executor_service"):
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
            with mock.patch("runtime.executor.engine.register_executor_service"):
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
            with mock.patch("runtime.executor.engine.register_executor_service"):
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
            with mock.patch("runtime.executor.engine.register_executor_service"):
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


def test_run_task_truncated_on_max_turns():
    """run_task returns truncated after 30 turns of tool calls."""
    with mock.patch("runtime.executor.engine.EXEC_LOG_FILE", Path("/dev/null")):
        with mock.patch("runtime.executor.engine.report_execution"):
            with mock.patch("runtime.executor.engine.register_executor_service"):
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
