# mock-heavy test: monkeypatch + dynamic attribute setup; pyright cannot follow.
# pyright: reportAttributeAccessIssue=false

"""Basic tests for policydoc CLI."""

import shutil
import subprocess
from pathlib import Path

import pytest

POLICYDOC_BIN = shutil.which("policydoc") or str(Path(__file__).parent.parent / ".venv" / "bin" / "policydoc")
POLICYDOC = POLICYDOC_BIN if Path(POLICYDOC_BIN).exists() else None


class TestPolicydocBasic:
    @pytest.mark.skipif(not POLICYDOC, reason="policydoc CLI not found")
    def test_help(self):
        rc = subprocess.run([POLICYDOC, "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not POLICYDOC, reason="policydoc CLI not found")
    def test_version(self):
        rc = subprocess.run([POLICYDOC, "--version"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not POLICYDOC, reason="policydoc CLI not found")
    def test_commands_present(self):
        result = subprocess.run([POLICYDOC, "--help"], capture_output=True, text=True)  # type: ignore[reportArgumentType]
        for cmd in ["analyze", "documents", "docscan", "audit", "export", "status", "wiki", "install", "dashboard"]:
            assert cmd in result.stdout, f"{cmd} not found in policydoc"

    @pytest.mark.skipif(not POLICYDOC, reason="policydoc CLI not found")
    def test_documents_help(self):
        rc = subprocess.run([POLICYDOC, "documents", "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0

    @pytest.mark.skipif(not POLICYDOC, reason="policydoc CLI not found")
    def test_audit_help(self):
        rc = subprocess.run([POLICYDOC, "audit", "--help"], capture_output=True).returncode  # type: ignore[reportArgumentType]
        assert rc == 0
