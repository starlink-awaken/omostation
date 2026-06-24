"""Tests for health check module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from ecos.services.core.health_check import (
    format_report,
    run_check,
)


class TestRunCheck:
    @patch("ecos.services.core.health_check.subprocess.run")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/fake/test.py"],
            "requires": [],
        }
        with patch("ecos.services.core.health_check.Path.exists", return_value=True):
            result = run_check(check)
        assert result["pass"] is True
        assert result["status"] == "pass"

    @patch("ecos.services.core.health_check.subprocess.run")
    def test_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "fail"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/fake/test.py"],
            "requires": [],
        }
        with patch("ecos.services.core.health_check.Path.exists", return_value=True):
            result = run_check(check)
        assert result["pass"] is False
        assert result["status"] == "fail"

    @patch("ecos.services.core.health_check.subprocess.run")
    def test_timeout(self, mock_run):
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("test.py", 30)
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/fake/test.py"],
            "requires": [],
        }
        with patch("ecos.services.core.health_check.Path.exists", return_value=True):
            result = run_check(check)
        assert result["pass"] is False
        assert result["status"] == "timeout"
        assert "超时" in result["reason"]

    @patch("ecos.services.core.health_check.subprocess.run")
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("not found")
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/fake/test.py"],
            "requires": [],
        }
        with patch("ecos.services.core.health_check.Path.exists", return_value=True):
            result = run_check(check)
        assert result["pass"] is False
        assert result["status"] == "error"

    def test_missing_dependency(self):
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/fake/test.py"],
            "requires": ["/nonexistent/path"],
        }
        result = run_check(check)
        assert result["pass"] is None
        assert result["status"] == "skipped"

    def test_missing_script(self):
        check = {
            "id": "test",
            "name": "Test",
            "dim": "X1",
            "cmd": ["python3", "/nonexistent/script.py"],
            "requires": [],
        }
        result = run_check(check)
        assert result["pass"] is None
        assert result["status"] == "missing"


class TestFormatReport:
    def test_format_empty(self):
        report = format_report([])
        assert "通过: 0" in report
        assert "失败: 0" in report

    def test_format_with_results(self):
        results = [
            {
                "id": "c1",
                "name": "Check 1",
                "dim": "X1",
                "pass": True,
                "status": "pass",
                "reason": "",
                "duration_ms": 10,
            },
            {
                "id": "c2",
                "name": "Check 2",
                "dim": "X2",
                "pass": False,
                "status": "fail",
                "reason": "error msg",
                "duration_ms": 5,
            },
        ]
        report = format_report(results)
        assert "通过: 1" in report
        assert "失败: 1" in report
        assert "Check 1" in report
        assert "Check 2" in report
