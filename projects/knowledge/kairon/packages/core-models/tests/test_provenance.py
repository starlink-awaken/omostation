"""Tests for core-models provenance."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from core_models.provenance import Provenance


def test_provenance_defaults():
    p = Provenance()
    assert isinstance(p.source_file, str)
