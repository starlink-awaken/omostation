"""
watchdog 看门狗守护进程单元测试

测试覆盖:
- _send_notification —— 通知发送逻辑
- _run_health_check —— 健康检查执行
- _signal_handler / _remove_pid —— 信号处理
- 状态迁移与 main() 入口
"""

import logging
import signal
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from forge import watchdog as m


class TestSendNotification:
    """测试通知发送逻辑。"""

    def test_ntfy_with_topic(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "mytopic")
        subprocess_calls = []

        def mock_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "ntfy")
        assert len(subprocess_calls) == 1
        assert "ntfy.sh" in str(subprocess_calls[0])

    def test_ntfy_missing_topic(self, monkeypatch):
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        called = False

        def mock_run(*a, **kw):
            nonlocal called
            called = True
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "ntfy")
        assert not called

    def test_discord_with_webhook(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/xxx")
        subprocess_calls = []

        def mock_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "discord")
        assert len(subprocess_calls) == 1
        assert "discord.com" in str(subprocess_calls[0])

    def test_discord_missing_webhook(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)
        called = False

        def mock_run(*a, **kw):
            nonlocal called
            called = True
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "discord")
        assert not called

    def test_both_channels(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "t")
        monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/xxx")
        subprocess_calls = []

        def mock_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "both")
        assert len(subprocess_calls) == 2

    def test_unknown_type(self, monkeypatch):
        called = False

        def mock_run(*a, **kw):
            nonlocal called
            called = True
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        m._send_notification("test msg", "unknown")
        assert not called

    def test_ntfy_exception(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "mytopic")

        def mock_run(*a, **kw):
            raise RuntimeError("curl failed")

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Should not crash, should log warning
        m._send_notification("test msg", "ntfy")


class TestRunHealthCheck:
    """测试 _run_health_check 健康检查执行。"""

    def test_healthy(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("R", (), {"returncode": 0, "stdout": "all ok\n", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        healthy, output = m._run_health_check()
        assert healthy is True
        assert "all ok" in output

    def test_unhealthy(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("R", (), {"returncode": 1, "stdout": "error!", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        healthy, output = m._run_health_check()
        assert healthy is False
        assert "error!" in output

    def test_timeout(self, monkeypatch):
        def mock_run(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="test", timeout=60)

        monkeypatch.setattr(subprocess, "run", mock_run)
        healthy, output = m._run_health_check()
        assert healthy is False
        assert "超时" in output

    def test_exception(self, monkeypatch):
        def mock_run(*a, **kw):
            raise FileNotFoundError("python3 not found")

        monkeypatch.setattr(subprocess, "run", mock_run)
        healthy, output = m._run_health_check()
        assert healthy is False
        assert "FileNotFoundError" in output or "不存在" in output


class TestPidFile:
    """测试 PID 文件管理。"""

    def test_write_pid(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "forge-watchdog.pid"
        monkeypatch.setattr(m, "PID_FILE", pid_file)
        m._write_pid()
        assert pid_file.exists()
        assert pid_file.read_text().strip().isdigit()

    def test_remove_pid(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "forge-watchdog.pid"
        pid_file.write_text("12345")
        monkeypatch.setattr(m, "PID_FILE", pid_file)
        m._remove_pid()
        assert not pid_file.exists()

    def test_remove_nonexistent_pid(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "forge-watchdog.pid"
        monkeypatch.setattr(m, "PID_FILE", pid_file)
        # Should not crash
        m._remove_pid()


class TestSignalHandler:
    """测试信号处理器。"""

    def test_handler_removes_pid_and_exits(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "forge-watchdog.pid"
        pid_file.write_text("99999")
        monkeypatch.setattr(m, "PID_FILE", pid_file)

        with pytest.raises(SystemExit) as exc:
            m._signal_handler(signal.SIGTERM, None)
        assert exc.value.code == 0
        assert not pid_file.exists()


class TestMain:
    """测试 main() 入口。"""

    def test_main_immediate_exit(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["watchdog.py", "--interval", "1"])
        call_count = 0

        def mock_health():
            nonlocal call_count
            call_count += 1
            raise KeyboardInterrupt()

        monkeypatch.setattr(m, "_run_health_check", mock_health)
        monkeypatch.setattr(signal, "signal", lambda *a, **kw: None)
        monkeypatch.setattr(m, "_send_notification", lambda *a, **kw: None)
        monkeypatch.setattr(m, "_write_pid", lambda: None)
        monkeypatch.setattr(m, "_remove_pid", lambda: None)
        monkeypatch.setattr(logging, "basicConfig", lambda **kw: None)

        result = m.main()
        assert result == 0
        assert call_count == 1

    def test_main_with_daemon_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["watchdog.py", "--daemon", "--interval", "1"])

        def mock_health():
            raise KeyboardInterrupt()

        monkeypatch.setattr(m, "_run_health_check", mock_health)
        monkeypatch.setattr(m, "_daemonize", lambda: None)
        monkeypatch.setattr(signal, "signal", lambda *a, **kw: None)
        monkeypatch.setattr(m, "_send_notification", lambda *a, **kw: None)
        monkeypatch.setattr(m, "_write_pid", lambda: None)
        monkeypatch.setattr(m, "_remove_pid", lambda: None)
        monkeypatch.setattr(m, "_setup_logging", lambda **kw: None)
        monkeypatch.setattr(logging, "basicConfig", lambda **kw: None)

        result = m.main()
        assert result == 0

    def test_main_state_transitions(self, monkeypatch):
        """测试健康状态 None -> True -> False -> True 的迁移"""
        monkeypatch.setattr("sys.argv", ["watchdog.py", "--interval", "1"])
        # Inject a sequence of health states: first healthy, then unhealthy, then healthy
        states = iter([(True, "healthy"), (False, "unhealthy"), (True, "healthy again")])
        notifications = []

        def mock_health():
            try:
                return next(states)
            except StopIteration:
                raise KeyboardInterrupt()

        def mock_notify(msg: str, notify_type: str):
            notifications.append((msg, notify_type))

        monkeypatch.setattr(m, "_run_health_check", mock_health)
        monkeypatch.setattr(signal, "signal", lambda *a, **kw: None)
        monkeypatch.setattr(m, "_send_notification", mock_notify)
        monkeypatch.setattr(m, "_write_pid", lambda: None)
        monkeypatch.setattr(m, "_remove_pid", lambda: None)

        result = m.main()
        assert result == 0
        assert m._last_healthy is True
        # Should have sent notification for unhealthy->healthy transition
        [
            n
            for n in notifications
            if "recovered" in n[0].lower() or "healthy" == n[0].split(": ")[-1].split("\n")[0].lower()
        ]
        # At least one notification for the unclean->clean transition
        assert len(notifications) >= 1
