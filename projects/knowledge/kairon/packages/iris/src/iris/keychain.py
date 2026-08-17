"""Optional keychain integration for secure credential storage.

Uses the `keyring` library when available, falling back to plain config.
macOS: uses system Keychain via keyring.
Linux: uses Secret Service (gnome-keyring / kwallet).
"""

from __future__ import annotations

from typing import Any, cast

_KEYRING_SERVICE = "iris"
_KEYRING_ENABLED = {"1", "true", "yes", "on"}


def _get_keyring() -> Any:
    """Import keyring if available. Returns module or None."""
    import os

    if os.environ.get("IRIS_ENABLE_KEYRING", "").strip().lower() not in _KEYRING_ENABLED:
        return None
    try:
        import keyring as _kr

        return _kr
    except ImportError:
        return None


def get_password(key: str) -> str | None:
    """Get a password from the system keychain.

    Returns None if keyring is not available or key not found.
    """
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        return cast("str | None", kr.get_password(_KEYRING_SERVICE, key))
    except Exception:
        return None


def set_password(key: str, password: str) -> bool:
    """Store a password in the system keychain.

    Returns True if stored successfully, False if keyring is unavailable.
    """
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.set_password(_KEYRING_SERVICE, key, password)
        return True
    except Exception:
        return False


def delete_password(key: str) -> bool:
    """Delete a password from the system keychain."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password(_KEYRING_SERVICE, key)
        return True
    except Exception:
        return False
