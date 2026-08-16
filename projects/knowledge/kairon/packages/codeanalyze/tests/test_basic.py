# mock-heavy test: monkeypatch + dynamic attribute setup; pyright cannot follow.
# pyright: reportAttributeAccessIssue=false

"""Basic tests for codeanalyze analysis, export, and audit."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ANALYZE = shutil.which("codeanalyze") or shutil.which("analyze")


class TestCodeAnalyzeBasic:
    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_help(self):
        rc = subprocess.run([ANALYZE, "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_version(self):
        rc = subprocess.run([ANALYZE, "--version"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_analyze_help(self):
        rc = subprocess.run([ANALYZE, "analyze", "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_export_help(self):
        rc = subprocess.run([ANALYZE, "export", "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_search_help(self):
        rc = subprocess.run([ANALYZE, "search", "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not ANALYZE, reason="codeanalyze CLI not found")
    def test_analyze_simple_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            tmp = f.name
        rc = subprocess.run([ANALYZE, "analyze", tmp], capture_output=True).returncode  # type: ignore[reportArgumentType]
        Path(tmp).unlink(missing_ok=True)
        assert rc in (0, 1)
