"""Tests for codeanalyze.commands.common — _validate_path, _INSTALL_GUIDE."""

import tempfile
from pathlib import Path

import click
import pytest
from codeanalyze.commands.common import _INSTALL_GUIDE, _validate_path


class TestInstallGuide:
    def test_has_expected_tools(self):
        assert "graphify" in _INSTALL_GUIDE
        assert "docling" in _INSTALL_GUIDE
        assert "marker" in _INSTALL_GUIDE
        assert "gitnexus" in _INSTALL_GUIDE

    def test_entries_have_command_and_desc(self):
        for tool, (cmd, desc) in _INSTALL_GUIDE.items():
            assert len(cmd) > 0
            assert len(desc) > 0


class TestValidatePath:
    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as d:
            result = _validate_path(d)
            assert isinstance(result, Path)
            assert result.exists()

    def test_nonexistent_path(self):
        with pytest.raises(click.BadParameter, match="does not exist"):
            _validate_path("/nonexistent/path/12345xyz")
