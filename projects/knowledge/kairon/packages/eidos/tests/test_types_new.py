"""Tests for new Eidos type modules: InferenceRule, StateMachine, Relation."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestInferenceRule:
    def test_create_valid(self):
        from eidos.types import InferenceRule

        r = InferenceRule(id="r1", name="Test", rule_type="forward", premises=["a"], conclusion="b")
        assert r.validate() == []

    def test_missing_fields(self):
        from eidos.types import InferenceRule

        r = InferenceRule(id="", name="", rule_type="", premises=[], conclusion="")
        errors = r.validate()
        assert len(errors) >= 4

    def test_invalid_rule_type(self):
        from eidos.types import InferenceRule

        r = InferenceRule(id="r2", name="Bad", rule_type="unknown", premises=["a"], conclusion="b")
        assert "invalid" in r.validate()[0]

    def test_to_dict_roundtrip(self):
        from eidos.types import InferenceRule

        r1 = InferenceRule(
            id="r3", name="R3", rule_type="backward", premises=["p1", "p2"], conclusion="c1", confidence=0.8
        )
        d = r1.to_dict()
        r2 = InferenceRule.from_dict(d)
        assert r2.id == "r3"
        assert r2.rule_type == "backward"
        assert r2.confidence == 0.8


class TestStateMachine:
    def test_create_valid(self):
        from eidos.types import StateMachine, StateTransition

        t = StateTransition(from_state="a", to_state="b", trigger="x")
        sm = StateMachine(id="sm1", name="SM1", states=["a", "b"], transitions=[t], initial_state="a")
        assert sm.validate() == []

    def test_invalid_initial_state(self):
        from eidos.types import StateMachine, StateTransition

        t = StateTransition(from_state="a", to_state="b", trigger="x")
        sm = StateMachine(id="sm1", name="SM1", states=["a", "b"], transitions=[t], initial_state="c")
        errors = sm.validate()
        assert any("initial_state" in e for e in errors)

    def test_invalid_transition_state(self):
        from eidos.types import StateMachine, StateTransition

        t = StateTransition(from_state="x", to_state="y", trigger="t")
        sm = StateMachine(id="sm2", name="SM2", states=["a"], transitions=[t], initial_state="a")
        errors = sm.validate()
        assert len(errors) >= 2


class TestRelation:
    def test_create_valid(self):
        from eidos.meta import MetaRelationType
        from eidos.types import Relation

        r = Relation(
            id="r1", source_id="s1", target_id="t1", relation_type="is_a", meta_relation=MetaRelationType.STRUCT
        )
        assert r.validate() == []

    def test_missing_fields(self):
        from eidos.types import Relation

        r = Relation(id="", source_id="", target_id="", relation_type="")
        errors = r.validate()
        assert len(errors) == 4

    def test_to_dict_meta_relation(self):
        from eidos.meta import MetaRelationType
        from eidos.types import Relation

        r = Relation(
            id="r2", source_id="s", target_id="t", relation_type="implies", meta_relation=MetaRelationType.DERIVE
        )
        d = r.to_dict()
        assert d["meta_relation"] == "derive"

    def test_from_dict_meta_relation(self):
        from eidos.meta import MetaRelationType
        from eidos.types import Relation

        d = {"id": "r3", "source_id": "s", "target_id": "t", "relation_type": "part_of", "meta_relation": "struct"}
        r = Relation.from_dict(d)
        assert r.meta_relation == MetaRelationType.STRUCT
