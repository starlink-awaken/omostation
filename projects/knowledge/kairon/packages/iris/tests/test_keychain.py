"""Tests for keychain module."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from iris.keychain import delete_password, get_password, set_password


class TestKeychain:
    """Keychain gracefully falls back when keyring is not installed."""

    def test_get_returns_none_without_keyring(self):
        result = get_password("nonexistent")
        assert result is None

    def test_set_returns_false_without_keyring(self):
        result = set_password("test", "value")
        assert result is False

    def test_delete_returns_false_without_keyring(self):
        result = delete_password("test")
        assert result is False
