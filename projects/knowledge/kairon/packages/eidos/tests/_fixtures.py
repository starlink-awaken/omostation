"""Eidos test fixtures."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest


@pytest.fixture
def sample_entity():
    return {"id": "test-entity-1", "type": "concept", "name": "Test Entity"}
