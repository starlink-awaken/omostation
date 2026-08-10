"""pytest conftest — add scripts to sys.path for all tests"""

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture
def ssb_key(monkeypatch, tmp_path):
    """Opt-in hermetic SSB signing key.

    Only tests that request this fixture get a random key installed into the
    canonical ssb_auth module (tmp KEY_FILE, SSB_KEY env removed). Tests that
    do NOT request it keep observing the real fail-closed no-key behavior
    (_load_key() -> None, compute_signature() -> None).
    """
    from ecos.l0.ssb import ssb_auth as auth

    key_file = tmp_path / ".ssb_key"
    key = os.urandom(32)
    key_file.write_bytes(key)

    monkeypatch.delenv("SSB_KEY", raising=False)
    monkeypatch.setattr(auth, "KEY_FILE", key_file)
    return key
