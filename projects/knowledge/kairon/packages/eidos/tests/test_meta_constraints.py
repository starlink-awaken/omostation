"""Tests for meta-model constraints."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestMetaConstraints:
    def test_builtin_constraints(self):
        from eidos.meta import BUILTIN_CONSTRAINTS

        assert len(BUILTIN_CONSTRAINTS) >= 4
        assert any(c.cardinality == "N:N" for c in BUILTIN_CONSTRAINTS)

    def test_relation_cardinality(self):
        from eidos.types import Relation

        r = Relation(id="r1", source_id="a", target_id="b", relation_type="test", cardinality="1:1")
        assert r.validate() == []

    def test_relation_invalid_cardinality(self):
        from eidos.types import Relation

        r = Relation(id="r2", source_id="a", target_id="b", relation_type="test", cardinality="X:Y")
        assert len(r.validate()) > 0

    def test_list_constraints_smoke(self):
        from eidos.meta import list_constraints

        constraints = list_constraints()
        assert len(constraints) >= 4
