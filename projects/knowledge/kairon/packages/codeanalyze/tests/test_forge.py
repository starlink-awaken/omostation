"""Tests for Forge Guardrails module."""

import pytest
from codeanalyze.integrations.forge import (
    GuardrailConfig,
    GuardrailStats,
    check_missing_steps,
    configure,
    get_stats,
    guardrail,
    rescue_json,
    reset_stats,
    retry_on_error,
)


@pytest.fixture(autouse=True)
def reset():
    reset_stats()
    configure()


class TestRescueJson:
    def test_valid_json(self):
        assert rescue_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert rescue_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_markdown_fenced_with_text(self):
        assert rescue_json('some text\n```json\n{"a": 1}\n```\nmore text') == {"a": 1}

    def test_none_input(self):
        assert rescue_json(None) is None  # type: ignore[reportArgumentType]

    def test_empty_string(self):
        assert rescue_json("") is None

    def test_not_json(self):
        assert rescue_json("纯文本内容，不是 JSON") is None

    def test_array_json(self):
        assert rescue_json("[1, 2, 3]") == [1, 2, 3]


class TestCheckMissingSteps:
    """check_missing_steps 接收 tool_calls (list[dict]) 和 required (list[str])。"""

    def test_all_steps_present(self):
        calls = [{"name": "analyze"}, {"name": "export"}]
        assert check_missing_steps(calls, ["analyze", "export"]) == []

    def test_missing_step(self):
        calls = [{"name": "analyze"}]
        missing = check_missing_steps(calls, ["analyze", "export", "validate"])
        assert "export" in missing
        assert "validate" in missing
        assert "analyze" not in missing

    def test_empty_calls(self):
        assert check_missing_steps([], ["step1"]) == ["step1"]

    def test_no_required_steps(self):
        assert check_missing_steps([{"name": "a"}], []) == []

    def test_nested_function_call(self):
        """支持 function.call 格式。"""
        calls = [{"function": {"name": "analyze"}}]
        assert check_missing_steps(calls, ["analyze"]) == []


class TestRetryOnError:
    def test_success_first_try(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return {"status": "ok"}

        result = retry_on_error(fn, max_retries=3)
        assert result == {"status": "ok"}
        assert call_count == 1

    def test_retry_then_succeed(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return {"status": "ok"}

        result = retry_on_error(fn, max_retries=5)
        assert result == {"status": "ok"}
        assert call_count == 3

    def test_exhaust_retries_returns_error(self):
        """耗尽重试后返回错误 dict，不抛出异常。"""

        def fn():
            raise ValueError("persistent error")

        result = retry_on_error(fn, max_retries=2)
        assert result["status"] == "error"
        assert "persistent error" in result["error"]

    def test_pass_args(self):
        def fn(x, y=None):
            return {"x": x, "y": y}

        result = retry_on_error(fn, args=(42,), kwargs={"y": "hello"})
        assert result == {"x": 42, "y": "hello"}


class TestGuardrailConfig:
    def test_default_config(self):
        cfg = GuardrailConfig()
        assert cfg.max_retries == 3
        assert cfg.rescue_parsing is True

    def test_custom_config(self):
        cfg = GuardrailConfig(required_steps=["analyze"], max_retries=5, rescue_parsing=False)
        assert cfg.required_steps == ["analyze"]
        assert cfg.max_retries == 5
        assert cfg.rescue_parsing is False


class TestGuardrailStats:
    def test_default_stats(self):
        stats = GuardrailStats()
        assert stats.total_calls == 0
        assert stats.rescued_parses == 0

    def test_reset_stats(self):
        s = get_stats()
        s.total_calls = 10
        reset_stats()
        assert get_stats().total_calls == 0

    def test_increment(self):
        s = get_stats()
        s.total_calls += 1
        assert get_stats().total_calls == 1


class TestGuardrailDecorator:
    def test_basic_wrapping(self):
        @guardrail(max_retries=1)
        def my_tool(path: str = ".") -> dict:
            return {"status": "ok", "path": path}

        result = my_tool("/test")
        assert result["status"] == "ok"
        assert result["path"] == "/test"

    def test_step_enforcement_missing(self):
        @guardrail(required_steps=["analyze", "export"], max_retries=1)
        def incomplete_tool() -> dict:
            return {"status": "ok"}

        result = incomplete_tool()
        assert "_missing_steps" in result

    def test_step_enforcement_all_present(self):
        @guardrail(required_steps=["analyze", "export"], max_retries=1)
        def complete_tool() -> dict:
            return {"status": "ok", "analyze": {}, "export": {}}

        result = complete_tool()
        assert "_missing_steps" not in result

    def test_rescue_str_result(self):
        """装饰器 rescue 参数控制是否修复字符串返回。"""

        @guardrail(rescue=True, max_retries=1)
        def string_return() -> str:
            return '{"status": "ok", "value": 42}'

        result = string_return()
        assert isinstance(result, dict)
        assert result["value"] == 42  # type: ignore[reportArgumentType]

    def test_no_rescue_when_disabled(self):
        @guardrail(rescue=False, max_retries=1)
        def string_return() -> str:
            return '{"status": "ok"}'

        result = string_return()
        # rescue=False, 所以字符串返回保持不变
        assert result == '{"status": "ok"}'

    def test_stats_tracking(self):
        reset_stats()

        @guardrail(max_retries=1)
        def tool() -> dict:
            return {"status": "ok"}

        tool()
        assert get_stats().total_calls == 1
