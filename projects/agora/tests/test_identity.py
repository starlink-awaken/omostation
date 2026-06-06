"""Tests for typed identity normalization in Agora."""

from __future__ import annotations

import importlib
import importlib.util


def _identity_module():
    spec = importlib.util.find_spec("agora.auth.identity")
    assert spec is not None, "agora.auth.identity module should exist for typed identity support"
    return importlib.import_module("agora.auth.identity")


def test_normalize_identity_formats_actor_billing_and_payload():
    identity_mod = _identity_module()
    assert hasattr(identity_mod, "normalize_identity")

    identity = identity_mod.normalize_identity(
        {
            "subject_id": "alice",
            "subject_type": "user",
            "issuer": "auth0",
            "tenant": "acme",
        }
    )

    assert identity.actor == "user:alice"
    assert identity.billing_subject == "tenant:acme"
    assert identity.to_payload() == {
        "subject_id": "alice",
        "subject_type": "user",
        "issuer": "auth0",
        "tenant": "acme",
    }


def test_normalize_identity_preserves_legacy_string_actor():
    identity_mod = _identity_module()
    identity = identity_mod.normalize_identity("legacy-user")

    assert identity.actor == "legacy-user"
    assert identity.billing_subject == "legacy-user"
    assert identity.to_payload() == {
        "subject_id": "legacy-user",
        "subject_type": "legacy",
        "issuer": "legacy",
        "tenant": "",
    }
