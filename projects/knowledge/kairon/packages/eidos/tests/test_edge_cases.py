"""Edge case tests — covering gaps found by red team audit."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestEdgeCases:
    """Tests for edge cases red team identified as gaps."""

    def test_knowledge_card_empty_strings(self):
        from eidos.types import KnowledgeCard

        c = KnowledgeCard(id="", title="", content="", source="", source_type="", schema_type="")
        errors = c.validate()
        assert len(errors) >= 5  # id, title, content, source, source_type all required

    def test_knowledge_card_none_values(self):
        from eidos.types import KnowledgeCard

        c = KnowledgeCard(id=None, title=None, content="test", source="test", source_type="test", schema_type="test")  # type: ignore[reportArgumentType]
        errors = c.validate()
        assert len(errors) >= 1  # id required

    def test_knowledge_card_very_long_values(self):
        from eidos.types import KnowledgeCard

        c = KnowledgeCard(
            id="x" * 1000,
            title="x" * 1000,
            content="x" * 10000,
            source="x" * 1000,
            source_type="x" * 1000,
            schema_type="x" * 1000,
        )
        errors = c.validate()
        assert len(errors) == 0  # no validation rules limit length

    def test_knowledge_card_unicode(self):
        from eidos.types import KnowledgeCard

        c = KnowledgeCard(
            id="卡-001",
            title="量子计算研究报告",
            content="一种基于表面码的量子纠错方法。",
            source="/知识库/专利",
            source_type="研究",
            schema_type="知识卡片",
        )
        errors = c.validate()
        assert len(errors) == 0

    def test_fact_empty_strings(self):
        from eidos.types import Fact

        f = Fact(id="", subject="", predicate="", object="")
        errors = f.validate()
        assert len(errors) >= 4

    def test_fact_unicode(self):
        from eidos.types import Fact

        f = Fact(
            id="f-量子", subject="量子计算", predicate="需要", object="纠错码", confidence=1.0, derived_from="research"
        )
        errors = f.validate()
        assert len(errors) == 0

    def test_ontology_node_missing_optional(self):
        from eidos.types import OntologyNode

        n = OntologyNode(id="n1", name="Test", node_type="concept")
        errors = n.validate()
        assert len(errors) == 0  # properties and aliases are optional

    def test_relation_invalid_cardinality(self):
        from eidos.types import Relation

        r = Relation(id="r1", source_id="a", target_id="b", relation_type="test", cardinality="INVALID")
        errors = r.validate()
        assert any("cardinality" in e.lower() for e in errors)

    def test_state_machine_initial_not_in_states(self):
        from eidos.types import StateMachine, StateTransition

        t = StateTransition(from_state="a", to_state="b", trigger="x")
        sm = StateMachine(id="sm1", name="test", states=["a", "b"], transitions=[t], initial_state="c")
        errors = sm.validate()
        assert any("initial_state" in e for e in errors)

    def test_state_machine_transition_not_in_states(self):
        from eidos.types import StateMachine, StateTransition

        t = StateTransition(from_state="z", to_state="y", trigger="x")
        sm = StateMachine(id="sm2", name="test", states=["a"], transitions=[t], initial_state="a")
        errors = sm.validate()
        assert len(errors) >= 2  # both from and to not in states

    def test_inference_rule_no_premises(self):
        from eidos.types import InferenceRule

        r = InferenceRule(id="r1", name="test", rule_type="forward", premises=[], conclusion="c")
        errors = r.validate()
        assert "premises" in errors[0].lower() or any("premise" in e for e in errors)

    def test_serialize_roundtrip_special_chars(self):
        from eidos.types import KnowledgeCard

        original = KnowledgeCard(
            id="k1",
            title="test\nwith\nnewlines",
            content='tab\there\nand"quotes"',
            source="http://example.com?a=1&b=2",
            source_type="web",
            schema_type="test",
            tags=["tag1", "tag2"],
        )
        d = original.to_dict()
        restored = KnowledgeCard.from_dict(d)
        assert restored.title == "test\nwith\nnewlines"
        assert restored.content == 'tab\there\nand"quotes"'
        assert restored.source == "http://example.com?a=1&b=2"
        assert restored.tags == ["tag1", "tag2"]

    def test_meta_type_values(self):
        from eidos.meta import MetaType

        values = {m.value for m in MetaType}
        expected = {"domain", "fact", "inference", "relation", "state", "document", "constraint", "processor"}
        assert values == expected

    def test_meta_relation_values(self):
        from eidos.meta import MetaRelationType

        values = {m.value for m in MetaRelationType}
        expected = {"struct", "derive", "behavior", "justify"}
        assert values == expected
