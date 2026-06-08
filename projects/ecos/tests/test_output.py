"""Tests for ecos OutputFormatter (standalone ANSI implementation)."""

import json
import sys

import pytest

from ecos.ssot.tools._output import OutputFormatter


class TestOutputFormatter:
    """OutputFormatter with default (terminal) mode."""

    @pytest.fixture
    def fmt(self):
        return OutputFormatter()

    def test_print_success(self, fmt, capsys):
        fmt.print_success("done")
        captured = capsys.readouterr()
        assert "done" in captured.out

    def test_print_error(self, fmt, capsys):
        fmt.print_error("fail", suggestion="try again")
        captured = capsys.readouterr()
        assert "fail" in captured.err
        assert "try again" in captured.err

    def test_print_error_no_suggestion(self, fmt, capsys):
        fmt.print_error("fail")
        captured = capsys.readouterr()
        assert "fail" in captured.err

    def test_print_warning(self, fmt, capsys):
        fmt.print_warning("careful")
        captured = capsys.readouterr()
        assert "careful" in captured.out

    def test_print_info(self, fmt, capsys):
        fmt.print_info("info")
        captured = capsys.readouterr()
        assert "info" in captured.out

    def test_print_progress(self, fmt, capsys):
        fmt.print_progress("loading")
        captured = capsys.readouterr()
        assert "loading" in captured.out

    def test_print_header(self, fmt, capsys):
        fmt.print_header("Section")
        captured = capsys.readouterr()
        assert "Section" in captured.out

    def test_print_section(self, fmt, capsys):
        fmt.print_section("Sub")
        captured = capsys.readouterr()
        assert "Sub" in captured.out

    def test_print_divider(self, fmt, capsys):
        fmt.print_divider()
        captured = capsys.readouterr()
        assert "\n" in captured.out

    def test_print_table_empty(self, fmt, capsys):
        fmt.print_table(["name", "value"], [], title="empty")
        captured = capsys.readouterr()
        assert "empty" in captured.out or "空" in captured.out

    def test_print_table_with_data(self, fmt, capsys):
        fmt.print_table(["Name", "Value"], [["a", "1"], ["b", "2"]], title="Data")
        captured = capsys.readouterr()
        assert "Name" in captured.out
        assert "Value" in captured.out
        assert "a" in captured.out
        assert "1" in captured.out

    def test_print_list_empty(self, fmt, capsys):
        fmt.print_list([], title="none")
        captured = capsys.readouterr()
        assert "空" in captured.out or "none" in captured.out

    def test_print_list_with_items(self, fmt, capsys):
        items = [{"name": "foo", "description": "bar"}, {"name": "baz"}]
        fmt.print_list(items, key_field="name", description_field="description", title="List")
        captured = capsys.readouterr()
        assert "foo" in captured.out
        assert "bar" in captured.out
        assert "baz" in captured.out

    def test_print_key_value(self, fmt, capsys):
        fmt.print_key_value({"status": "ok", "count": 5}, title="Stats")
        captured = capsys.readouterr()
        assert "status" in captured.out
        assert "ok" in captured.out
        assert "5" in captured.out

    # ── JSON mode ─────────────────────────────────────────────────────

    def test_json_mode_success(self, capsys):
        """JSON mode prints valid JSON to stdout."""
        fmt = OutputFormatter(json_mode=True)
        fmt.print_success("done")
        output = capsys.readouterr().out.strip()
        # Find JSON in output (may have ANSI prefix on first line)
        for line in output.splitlines():
            try:
                data = json.loads(line)
                assert data["status"] == "ok"
                assert data["message"] == "done"
                return
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON found in output: {output}")

    def test_json_mode_error(self, capsys):
        """JSON mode prints error JSON to stderr."""
        fmt = OutputFormatter(json_mode=True)
        fmt.print_error("fail", suggestion="retry")
        captured = capsys.readouterr()
        for line in captured.err.strip().splitlines():
            try:
                data = json.loads(line)
                assert data["status"] == "error"
                assert data["hint"] == "retry"
                return
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON found in stderr: {captured.err}")

    def test_json_mode_warning(self, capsys):
        """JSON mode prints warning JSON."""
        fmt = OutputFormatter(json_mode=True)
        fmt.print_warning("be careful")
        output = capsys.readouterr().out.strip()
        for line in output.splitlines():
            try:
                data = json.loads(line)
                assert data["status"] == "warning"
                return
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON: {output}")

    def test_json_mode_table(self, capsys):
        """JSON mode prints table as JSON."""
        fmt = OutputFormatter(json_mode=True)
        fmt.print_table(["N", "V"], [["x", "1"]], title="T")
        output = capsys.readouterr().out.strip()
        for line in output.splitlines():
            try:
                data = json.loads(line)
                if data.get("table"):
                    assert data["title"] == "T"
                    assert data["count"] == 1
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON table: {output}")

    def test_json_mode_key_value(self, capsys):
        """JSON mode prints key-value as JSON."""
        fmt = OutputFormatter(json_mode=True)
        fmt.print_key_value({"a": 1}, title="K")
        output = capsys.readouterr().out.strip()
        for line in output.splitlines():
            try:
                data = json.loads(line)
                if data.get("details"):
                    assert data["title"] == "K"
                    assert data["details"]["a"] == 1
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON: {output}")


class TestConvenienceFunctions:
    """Module-level convenience functions."""

    def test_print_success_func(self, capsys):
        from ecos.ssot.tools._output import print_success

        print_success("ok")
        captured = capsys.readouterr()
        assert "ok" in captured.out

    def test_print_error_func(self, capsys):
        from ecos.ssot.tools._output import print_error

        print_error("fail")
        captured = capsys.readouterr()
        assert "fail" in captured.err

    def test_print_warning_func(self, capsys):
        from ecos.ssot.tools._output import print_warning

        print_warning("warn")
        captured = capsys.readouterr()
        assert "warn" in captured.out

    def test_print_info_func(self, capsys):
        from ecos.ssot.tools._output import print_info

        print_info("info")
        captured = capsys.readouterr()
        assert "info" in captured.out
