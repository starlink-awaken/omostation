"""Envelope validation tests — real validate_envelope entry."""

import pytest
from mos.envelope import ValidationError, validate_envelope


def test_validate_requires_type_and_body():
    with pytest.raises(ValidationError):
        validate_envelope({"type": "episodic"})
    with pytest.raises(ValidationError):
        validate_envelope({"content": "x"})


def test_validate_ok_assigns_id_and_hash():
    env = validate_envelope({"type": "semantic", "content": "I prefer vegetarian meals"})
    assert env.id.startswith("mem_semantic_")
    assert env.content_hash and len(env.content_hash) == 64
    assert env.type == "semantic"


def test_high_pii_requires_content_ref():
    with pytest.raises(ValidationError, match="content_ref"):
        validate_envelope({"type": "episodic", "content": "ssn 123", "pii_class": "high"})
    env = validate_envelope({"type": "episodic", "content_ref": "vault://secret", "pii_class": "high"})
    assert env.content_ref.startswith("vault://")
