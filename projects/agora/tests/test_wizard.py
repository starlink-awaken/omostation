"""Tests for setup wizard."""

from agora.wizard import _confirm, run_wizard


def test_confirm_non_tty(monkeypatch):
    """_confirm returns True in non-interactive mode."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert _confirm("step", "prompt") is True


def test_run_wizard_non_tty(monkeypatch):
    """run_wizard completes without error in non-interactive mode."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    result = run_wizard()
    assert result == 0
