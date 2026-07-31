"""测试 base._notify_research_complete — macOS 系统通知。

异常处理覆盖 (lines 180-181)：
- FileNotFoundError → pass
- subprocess.SubprocessError → pass
- OSError → pass
"""

from __future__ import annotations

import subprocess

from cockpit.commands.base import (
    _notify_pipeline_error,
    _notify_pipeline_success,
    _notify_research_complete,
)


class TestNotifyResearchComplete:
    """_notify_research_complete 的异常处理分支。"""

    def test_file_not_found_handled(self, monkeypatch):
        """osascript 不存在→静默忽略"""

        def _fail_run(*args, **kwargs):
            raise FileNotFoundError("osascript not found")

        monkeypatch.setattr(subprocess, "run", _fail_run)
        _notify_research_complete("test topic")  # should not raise

    def test_subprocess_error_handled(self, monkeypatch):
        """subprocess 执行错误→静默忽略"""

        def _fail_run(*args, **kwargs):
            raise subprocess.SubprocessError("timeout")

        monkeypatch.setattr(subprocess, "run", _fail_run)
        _notify_research_complete("test topic")  # should not raise

    def test_os_error_handled(self, monkeypatch):
        """OSError→静默忽略"""

        def _fail_run(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(subprocess, "run", _fail_run)
        _notify_research_complete("test topic")  # should not raise


def test_notify_pipeline_success_formats_notification(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))

    _notify_pipeline_success("导入", "Imported Note")

    assert calls
    assert 'display notification "导入完成: Imported Note"' in calls[0][2]


def test_notify_pipeline_error_formats_notification(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))

    _notify_pipeline_error("导入", "broken.md")

    assert calls
    assert 'display notification "导入失败: broken.md"' in calls[0][2]
