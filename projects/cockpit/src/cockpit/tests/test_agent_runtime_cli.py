"""Tests for agent_runtime_cli.py"""

import sys
from unittest import mock

# Pre-mock runtime dependencies before any import
_mock_runtime = mock.MagicMock()
_mock_runtime_executor = mock.MagicMock()
_mock_runtime_config = mock.MagicMock()
_mock_runtime_engine = mock.MagicMock()

# Set up config defaults
_mock_runtime_config.AGENT_RUNTIME_PORT = 8888
_mock_runtime_config.DEFAULT_MODEL = "mock-model"
_mock_runtime_config.log = mock.MagicMock()
_mock_runtime_config.setup_logging = mock.MagicMock()

sys.modules["runtime"] = _mock_runtime
sys.modules["runtime.executor"] = _mock_runtime_executor
sys.modules["runtime.executor.config"] = _mock_runtime_config
sys.modules["runtime.executor.engine"] = _mock_runtime_engine
sys.modules["runtime.executor.server"] = mock.MagicMock()
sys.modules["uvicorn"] = mock.MagicMock()

# Now safe to import
from cockpit import agent_runtime_cli
import pytest


class TestCliMain:
    """agent_runtime_cli.cli_main() 测试"""

    def _run_with_args(self, args, runner_func=None):
        """Helper: run cli_main with mocked sys.argv"""
        with mock.patch.object(sys, "argv", args):
            try:
                if runner_func:
                    runner_func()
                else:
                    agent_runtime_cli.cli_main()
            except SystemExit:
                pass

    def test_server_mode_starts_uvicorn(self):
        """--server 模式应启动 uvicorn"""
        with mock.patch.object(sys, "argv", ["agent-runtime", "--server"]):
            try:
                agent_runtime_cli.cli_main()
            except SystemExit:
                pass
            _mock_runtime_config.setup_logging.assert_called()
            sys.modules["uvicorn"].run.assert_called()

    def test_prompt_from_cli_argument(self):
        """--prompt 从 CLI 参数直接传递"""
        mock_agent_runtime = mock.MagicMock()
        mock_agent_runtime.run_task.return_value = {"result": "ok"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_agent_runtime

        with mock.patch.object(sys, "argv", ["agent-runtime", "--prompt", "hello world"]):
            try:
                agent_runtime_cli.cli_main()
            except SystemExit:
                pass
            mock_agent_runtime.run_task.assert_called_once_with("hello world", tools_enabled=None)

    def test_prompt_from_task_definition(self):
        """--task 从 task_definitions/ 加载"""
        import json

        mock_agent_runtime = mock.MagicMock()
        mock_agent_runtime.run_task.return_value = {"result": "ok"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_agent_runtime

        task_def = {"prompt": "from task def"}
        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps(task_def)):
                with mock.patch.object(sys, "argv", ["agent-runtime", "--task", "test-task"]):
                    try:
                        agent_runtime_cli.cli_main()
                    except SystemExit:
                        pass
                    mock_agent_runtime.run_task.assert_called_once_with("from task def", tools_enabled=None)

    def test_task_file_not_found_exits(self):
        """--task 文件不存在时 sys.exit(1)"""
        with mock.patch("pathlib.Path.exists", return_value=False):
            with mock.patch.object(sys, "argv", ["agent-runtime", "--task", "nonexistent"]):
                with pytest.raises(SystemExit) as exc_info:
                    agent_runtime_cli.cli_main()
                assert exc_info.value.code == 1

    def test_task_def_no_prompt_exits(self):
        """--task 定义中没有 prompt 时 sys.exit(1)"""
        import json

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps({"no_prompt": 1})):
                with mock.patch.object(sys, "argv", ["agent-runtime", "--task", "empty-task"]):
                    with pytest.raises(SystemExit) as exc_info:
                        agent_runtime_cli.cli_main()
                    assert exc_info.value.code == 1

    def test_no_prompt_shows_help_and_exits(self):
        """无 --prompt 也无 --task 时 exit(1)"""
        with mock.patch("argparse.ArgumentParser.print_help"):
            with mock.patch.object(sys, "argv", ["agent-runtime"]):
                with pytest.raises(SystemExit) as exc_info:
                    agent_runtime_cli.cli_main()
                assert exc_info.value.code == 1

    def test_result_with_error_exits(self):
        """run_task 返回 error 时 exit(1)"""
        mock_agent_runtime = mock.MagicMock()
        mock_agent_runtime.run_task.return_value = {"error": "something broke"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_agent_runtime

        with mock.patch.object(sys, "argv", ["agent-runtime", "--prompt", "bad"]):
            with pytest.raises(SystemExit) as exc_info:
                agent_runtime_cli.cli_main()
            assert exc_info.value.code == 1

    def test_with_model_override(self):
        """--model 覆盖默认模型"""
        mock_agent_runtime = mock.MagicMock()
        mock_agent_runtime.run_task.return_value = {"result": "ok"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_agent_runtime

        with mock.patch.object(sys, "argv", ["agent-runtime", "--prompt", "hi", "--model", "gpt-4"]):
            try:
                agent_runtime_cli.cli_main()
            except SystemExit:
                pass
            _mock_runtime_engine.AgentRuntime.assert_called_with(model="gpt-4")

    def test_with_tools_enabled(self):
        """--tools 传递工具列表"""
        mock_agent_runtime = mock.MagicMock()
        mock_agent_runtime.run_task.return_value = {"result": "ok"}
        _mock_runtime_engine.AgentRuntime.return_value = mock_agent_runtime

        with mock.patch.object(sys, "argv", ["agent-runtime", "--prompt", "hi", "--tools", "read", "write"]):
            try:
                agent_runtime_cli.cli_main()
            except SystemExit:
                pass
            mock_agent_runtime.run_task.assert_called_once_with("hi", tools_enabled=["read", "write"])

    def test_main_alias_equals_cli_main(self):
        """main 是 cli_main 的别名"""
        assert agent_runtime_cli.main is agent_runtime_cli.cli_main
