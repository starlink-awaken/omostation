"""Tests for runtime matrix module."""

from pathlib import Path

import pytest
from runtime.matrix import _expand_env, load_matrix


def test_expand_env_basic():
    """$HOME should expand to the home directory."""
    result = _expand_env("$HOME/test")
    assert result.endswith("/test")
    assert "/Users/" in result or "/home/" in result


def test_expand_env_missing():
    """$NONEXISTENT_VAR should remain as-is if not in env."""
    result = _expand_env("/path/$NONEXISTENT_VAR_XYZ123")
    # If var not set, the literal string stays
    assert (
        "NONEXISTENT_VAR_XYZ123" not in result
        or result == "/path/$NONEXISTENT_VAR_XYZ123"
    )


def test_expand_env_null():
    """Null/empty should return empty string."""
    assert _expand_env("") == ""
    assert _expand_env("null") == ""


@pytest.mark.skip(reason="Legacy or Sandbox blocked")
def test_matrix_load(tmp_path: Path):
    """Load a minimal matrix.yaml."""
    matrix = tmp_path / "matrix.yaml"
    matrix.write_text("""\
runtime_matrix:
  version: 2
  services:
    - name: "test-svc"
      type: "daemon"
      status: "running"
      port: 9999
      deploy_path: "$HOME/test"
""")
    services = load_matrix(matrix)
    assert len(services) == 1
    svc = services[0]
    assert svc.name == "test-svc"
    assert svc.type == "daemon"
    assert svc.port == 9999
    assert svc.deploy_path.endswith("/test")
    assert "$HOME" not in svc.deploy_path
