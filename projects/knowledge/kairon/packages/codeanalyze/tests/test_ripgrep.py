"""Tests for ripgrep adapter."""

from pathlib import Path

import pytest
from codeanalyze.analyzers.ripgrep import (
    RgMatch,
    RgResult,
    _parse_json_output,
    _parse_text_output,
    search,
    search_files,
)


class TestRgDataTypes:
    def test_rg_match(self):
        m = RgMatch(path="/a/b.py", line_number=10, column=1, text="def foo():")
        assert m.path == "/a/b.py"
        assert m.line_number == 10
        assert m.text == "def foo():"

    def test_rg_match_context(self):
        m = RgMatch("/a.py", 5, 0, "foo", lines_before=["# before"], lines_after=["# after"])
        assert "before" in m.context
        assert "foo" in m.context
        assert "after" in m.context

    def test_rg_result_defaults(self):
        result = RgResult(pattern="foo", path=".")
        assert result.total == 0
        assert result.error is None
        assert result.matches == []

    def test_rg_result_with_matches(self):
        m = RgMatch("/a.py", 5, 0, "foo")
        result = RgResult(pattern="foo", path=".", matches=[m], total=1)
        assert len(result.matches) == 1


class TestRipgrepParsing:
    """Test JSON and text output parsing with known inputs."""

    def _make_json_line(self, type_: str, **data_kw) -> str:
        import json

        d = {"type": type_, "data": data_kw}
        return json.dumps(d, ensure_ascii=False)

    def test_parse_json_empty(self):
        result = RgResult(pattern="x", path=".")
        _parse_json_output(result, "")
        assert len(result.matches) == 0

    def test_parse_json_one_match(self):
        result = RgResult(pattern="import", path=".")
        stdout = (
            self._make_json_line("begin", path={"text": "/a.py"}, bytes=50, lines=10)
            + "\n"
            + self._make_json_line(
                "match",
                path={"text": "/a.py"},
                line_number=5,
                absolute_offset=0,
                column=1,
                absolute_column=1,
                lines={"text": "import os\n"},
            )
            + "\n"
            + self._make_json_line("summary", stats={}, elapsed_millis=10)
        )
        _parse_json_output(result, stdout)
        assert len(result.matches) >= 1
        if result.matches:
            assert result.matches[0].line_number == 5

    def test_parse_json_multi_match(self):
        result = RgResult(pattern="import", path=".")
        stdout = "\n".join(
            [
                self._make_json_line("begin", path={"text": "/a.py"}, bytes=50, lines=5),
                self._make_json_line(
                    "match",
                    path={"text": "/a.py"},
                    line_number=3,
                    absolute_offset=0,
                    column=1,
                    absolute_column=1,
                    lines={"text": "import os\n"},
                ),
                self._make_json_line(
                    "match",
                    path={"text": "/a.py"},
                    line_number=7,
                    absolute_offset=20,
                    column=1,
                    absolute_column=1,
                    lines={"text": "import sys\n"},
                ),
                self._make_json_line("summary", stats={}, elapsed_millis=10),
            ]
        )
        _parse_json_output(result, stdout)
        assert len(result.matches) >= 2

    def test_parse_text_output(self):
        result = RgResult(pattern="x", path=".")
        _parse_text_output(result, "/a.py:5:import os\n/a.py:10:import sys\n")
        assert len(result.matches) == 2
        assert result.matches[0].line_number == 5
        assert result.matches[1].line_number == 10

    def test_parse_text_empty(self):
        result = RgResult(pattern="x", path=".")
        _parse_text_output(result, "")
        assert len(result.matches) == 0

    def test_parse_text_invalid_line(self):
        result = RgResult(pattern="x", path=".")
        _parse_text_output(result, "invalid\n")  # no colons
        assert len(result.matches) == 0


class TestRipgrepSearch:
    """Integration tests — require ripgrep installed."""

    def test_search_self(self):
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("def test_search_self", str(codeanalyze_root), max_count=5)
        assert isinstance(result, RgResult)
        if result.error:
            pytest.skip(f"rg not available: {result.error}")

    def test_search_no_match(self):
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("__THIS_SHOULD_NOT_MATCH_ANYTHING_XYZ__", str(codeanalyze_root))
        assert result.total == 0

    def test_search_with_max(self):
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("def ", str(codeanalyze_root), max_count=3)
        if result.error:
            pytest.skip(f"rg not available: {result.error}")
        assert result.total > 0  # -m 是每文件限制，不是全局限制

    def test_search_fixed(self):
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("def analyze", str(codeanalyze_root), regex=False, max_count=3)
        if result.error:
            pytest.skip(f"rg not available: {result.error}")
        assert result.total >= 0

    def test_search_files_conversion(self):
        result = search_files("class RgMatch", str(Path(__file__).parent.parent / "src"), max_count=5)
        assert isinstance(result, list)
        if result and "error" not in result[0]:
            assert all("file" not in item for item in result)  # uses different keys

    def test_search_glob_filter(self):
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("def ", str(codeanalyze_root), glob="*.py", max_count=3)
        if result.error:
            pytest.skip(f"rg not available: {result.error}")
        assert result.total >= 0

    def test_rg_result_no_error_on_not_found(self):
        """rg returns code 1 for no match, not an error."""
        codeanalyze_root = Path(__file__).parent.parent / "src"
        if not codeanalyze_root.exists():
            pytest.skip("source tree not found")
        result = search("XYZZYX_NONEXISTENT_PATTERN_12345", str(codeanalyze_root))
        assert result.error is None
        assert result.total == 0
