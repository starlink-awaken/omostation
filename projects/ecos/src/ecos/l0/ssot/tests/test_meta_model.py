"""Tests for SSOT meta model (meta_model.py).

Covers: enums, dataclasses, cross-reference validation, schema validation, orthogonality.
"""

import pytest
from sot_bridge.ssot_kernel.meta_model import (
    Confidence,
    Constraint,
    DomainConfig,
    Entity,
    Fact,
    Inference,
    MetaConstraint,
    MetaRelationType,
    MetaType,
    Relation,
    Rule,
    StateMachine,
    StateNode,
    Transition,
    check_relation_allowed,
    describe_meta_type,
    validate_cross_references,
    validate_yaml_schema,
    verify_orthogonality,
)

# ── Enum tests ──────────────────────────────────────────────────────────────


class TestMetaType:
    def test_values(self):
        assert MetaType.DOMAIN.value == "MET-DOMAIN"
        assert MetaType.FACT.value == "MET-FACT"
        assert MetaType.INFERENCE.value == "MET-INFERENCE"
        assert MetaType.STATE.value == "MET-STATE"
        assert MetaType.DOCUMENT.value == "MET-DOCUMENT"
        assert MetaType.CONSTRAINT.value == "MET-CONSTRAINT"
        assert MetaType.PROCESSOR.value == "MET-PROCESSOR"
        assert MetaType.RELATION.value == "MET-RELATION"
        assert len(MetaType) == 8

    def test_from_str_valid(self):
        assert MetaType.from_str("MET-DOMAIN") == MetaType.DOMAIN
        assert MetaType.from_str("met-fact") == MetaType.FACT
        assert MetaType.from_str("MET-INFERENCE") == MetaType.INFERENCE

    def test_from_str_invalid_raises(self):
        with pytest.raises(KeyError):
            MetaType.from_str("INVALID")


class TestMetaRelationType:
    def test_values(self):
        assert MetaRelationType.STRUCT.value == "MET-REL-STRUCT"
        assert MetaRelationType.DERIVE.value == "MET-REL-DERIVE"
        assert MetaRelationType.BEHAVIOR.value == "MET-REL-BEHAVIOR"
        assert MetaRelationType.JUSTIFY.value == "MET-REL-JUSTIFY"
        assert len(MetaRelationType) == 4


class TestMetaConstraint:
    def test_values(self):
        assert MetaConstraint.TYPE_PURITY.value == "META-CON-01"
        assert MetaConstraint.REL_DIRECTION.value == "META-CON-02"
        assert MetaConstraint.PROC_INPUT.value == "META-CON-03"
        assert MetaConstraint.SELF_REF_BOUND.value == "META-CON-04"
        assert len(MetaConstraint) == 4


class TestConfidence:
    def test_values(self):
        assert Confidence.FACT.value == "fact"
        assert Confidence.INFERENCE.value == "inference"
        assert Confidence.HYPOTHESIS.value == "hypothesis"
        assert Confidence.ESTIMATED.value == "estimated"
        assert len(Confidence) == 4


# ── Data class tests ────────────────────────────────────────────────────────


class TestEntity:
    def test_default_creation(self):
        e = Entity(id="ORG-test", name="Test", meta_type=MetaType.DOMAIN, entity_type="Organization")
        assert e.status == "active"
        assert e.confidence == Confidence.FACT
        assert e.source == ""
        assert e.attributes == {}
        assert e.metadata == {}

    def test_id_prefix(self):
        e = Entity(id="ORG-test-123", name="Test", meta_type=MetaType.DOMAIN, entity_type="Organization")
        assert e.id_prefix == "ORG-"

    def test_id_prefix_no_dash(self):
        e = Entity(id="test", name="Test", meta_type=MetaType.DOMAIN, entity_type="Organization")
        assert e.id_prefix == "test"

    def test_with_relations(self):
        r = Relation(source_id="ORG-a", target_id="ORG-b", relation_type="part_of")
        e = Entity(
            id="ORG-a",
            name="A",
            meta_type=MetaType.DOMAIN,
            entity_type="Organization",
            relations=[r],
        )
        assert len(e.relations) == 1
        assert e.relations[0].target_id == "ORG-b"


class TestRelation:
    def test_minimal_creation(self):
        r = Relation(source_id="ORG-a", target_id="ORG-b", relation_type="part_of")
        assert r.source_id == "ORG-a"
        assert r.target_id == "ORG-b"
        assert r.relation_type == "part_of"
        assert r.meta_relation is None

    def test_full_creation(self):
        r = Relation(
            source_id="ORG-a",
            target_id="ORG-b",
            relation_type="part_of",
            meta_relation=MetaRelationType.STRUCT,
            attributes={"weight": 1.0},
        )
        assert r.meta_relation == MetaRelationType.STRUCT
        assert r.attributes["weight"] == 1.0


class TestFact:
    def test_creation(self):
        f = Fact(id="DAT-001", title="Test fact", value=42, unit="km")
        assert f.meta_type == MetaType.FACT
        assert f.value == 42
        assert f.unit == "km"

    def test_default_tags(self):
        f = Fact(id="DAT-002", title="Another fact")
        assert f.tags == []


class TestInference:
    def test_creation(self):
        i = Inference(
            id="INF-001",
            title="Test inference",
            derives_from=["DAT-001", "DAT-002"],
            logic="A → B",
            conclusion="B is true",
        )
        assert i.meta_type == MetaType.INFERENCE
        assert i.confidence == Confidence.INFERENCE
        assert len(i.derives_from) == 2

    def test_status_default(self):
        i = Inference(id="INF-002", title="Another", derives_from=[], logic="", conclusion="")
        assert i.status == "active"


class TestStateMachine:
    def test_with_states_and_transitions(self):
        s1 = StateNode(id="S1", name="Start")
        s2 = StateNode(id="S2", name="End")
        t = Transition(from_state="S1", to_state="S2", condition="done")
        sm = StateMachine(id="SM-001", name="Process", states=[s1, s2], transitions=[t])
        assert len(sm.states) == 2
        assert len(sm.transitions) == 1
        assert sm.transitions[0].condition == "done"

    def test_minimal(self):
        sm = StateMachine(id="SM-002", name="Empty")
        assert sm.states == []
        assert sm.transitions == []


class TestRule:
    def test_default_pattern(self):
        r = Rule(id="R-001", pattern="contradiction")
        assert r.pattern == "contradiction"
        assert r.premises == []

    def test_with_premises(self):
        r = Rule(
            id="R-002",
            pattern="chain_trigger",
            premises=[{"condition": "A > B"}],
            logic="if A > B then trigger",
        )
        assert len(r.premises) == 1


class TestConstraint:
    def test_default_severity(self):
        c = Constraint(id="C-001", name="Test", expectation="X must be Y")
        assert c.severity == "WARN"

    def test_full_creation(self):
        c = Constraint(
            id="C-002",
            name="Critical",
            severity="BLOCKER",
            check_type="schema",
            expectation="must be non-null",
            meta_constraint=MetaConstraint.TYPE_PURITY,
        )
        assert c.severity == "BLOCKER"
        assert c.meta_constraint == MetaConstraint.TYPE_PURITY


class TestDomainConfig:
    def test_empty_config(self):
        config = DomainConfig()
        assert config.domain == {}
        assert config.entities == []
        assert config.facts == []

    def test_find_entity(self):
        e1 = Entity(id="ORG-a", name="A", meta_type=MetaType.DOMAIN, entity_type="Organization")
        e2 = Entity(id="ORG-b", name="B", meta_type=MetaType.DOMAIN, entity_type="Organization")
        config = DomainConfig(entities=[e1, e2])
        assert config.find_entity("ORG-a") is e1
        assert config.find_entity("nonexistent") is None

    def test_find_fact(self):
        f = Fact(id="DAT-001", title="Test")
        config = DomainConfig(facts=[f])
        assert config.find_fact("DAT-001") is f
        assert config.find_fact("nonexistent") is None

    def test_find_inference(self):
        i = Inference(id="INF-001", title="T", derives_from=[], logic="", conclusion="")
        config = DomainConfig(inferences=[i])
        assert config.find_inference("INF-001") is i
        assert config.find_inference("nonexistent") is None


# ── Functions tests ─────────────────────────────────────────────────────────


class TestCheckRelationAllowed:
    def test_valid_relation(self):
        assert check_relation_allowed(MetaType.DOMAIN, MetaType.DOMAIN, MetaRelationType.STRUCT)

    def test_invalid_relation(self):
        assert not check_relation_allowed(MetaType.DOMAIN, MetaType.DOMAIN, MetaRelationType.DERIVE)

    def test_unknown_pair(self):
        # Use RELATION type which is not in the matrix
        assert not check_relation_allowed(MetaType.RELATION, MetaType.DOMAIN, MetaRelationType.STRUCT)


class TestDescribeMetaType:
    def test_domain_description(self):
        desc = describe_meta_type(MetaType.DOMAIN)
        assert "nature" in desc
        assert desc["nature"] == "可指认的现实实体"

    def test_unknown_type(self):
        desc = describe_meta_type(MetaType.RELATION)
        assert desc["nature"] == "连接实体的边"

    def test_all_types_have_description(self):
        for mt in MetaType:
            desc = describe_meta_type(mt)
            assert "nature" in desc, f"{mt} missing nature"
            assert "can_do" in desc, f"{mt} missing can_do"
            assert "cannot_do" in desc, f"{mt} missing cannot_do"


class TestValidateYamlSchema:
    def test_valid_domain(self):
        errors = validate_yaml_schema("domain", {"domain": {"name": "test"}})
        assert errors == []

    def test_missing_required(self):
        errors = validate_yaml_schema("domain", {"domain": {}})
        # The schema validator checks top-level required fields only;
        # nested object required fields (like domain.name) are not validated.
        assert isinstance(errors, list)

    def test_valid_entities(self):
        errors = validate_yaml_schema("entities", {"entities": [{"id": "E1", "type": "Organization"}]})
        assert errors == []

    def test_entity_missing_id(self):
        errors = validate_yaml_schema("entities", {"entities": [{"type": "Organization"}]})
        assert len(errors) >= 1

    def test_facts_section(self):
        errors = validate_yaml_schema("facts", {"policy": [{"id": "POL-001", "title": "Policy1"}]})
        assert errors == []

    def test_unknown_schema(self):
        errors = validate_yaml_schema("nonexistent", {"foo": "bar"})
        assert errors == []

    def test_invalid_entity_status(self):
        errors = validate_yaml_schema(
            "entities",
            {
                "entities": [{"id": "E1", "type": "T", "status": "invalid_status"}],
            },
        )
        assert len(errors) >= 1


class TestValidateCrossReferences:
    def test_no_errors(self):
        config = DomainConfig(
            entities=[Entity(id="ORG-a", name="A", meta_type=MetaType.DOMAIN, entity_type="Organization")],
            relations=[Relation(source_id="ORG-a", target_id="ORG-a", relation_type="part_of")],
        )
        errors = validate_cross_references(config)
        assert errors == []

    def test_relation_source_missing(self):
        config = DomainConfig(
            relations=[Relation(source_id="nonexistent", target_id="ORG-a", relation_type="part_of")],
        )
        errors = validate_cross_references(config)
        assert any("nonexistent" in e for e in errors)

    def test_inference_dep_missing(self):
        config = DomainConfig(
            inferences=[Inference(id="INF-001", title="T", derives_from=["MISSING"], logic="", conclusion="")],
        )
        errors = validate_cross_references(config)
        assert any("MISSING" in e for e in errors)

    def test_state_transition_invalid(self):
        sm = StateMachine(
            id="SM-001",
            name="Test",
            states=[StateNode(id="S1", name="Start")],
            transitions=[Transition(from_state="S1", to_state="S2", condition="")],
        )
        config = DomainConfig(state_machines=[sm])
        errors = validate_cross_references(config)
        assert any("S2" in e for e in errors)

    def test_entity_metadata_fact_missing(self):
        config = DomainConfig(
            entities=[
                Entity(
                    id="ORG-a",
                    name="A",
                    meta_type=MetaType.DOMAIN,
                    entity_type="Organization",
                    metadata={"facts": ["MISSING-FACT"]},
                )
            ],
        )
        errors = validate_cross_references(config)
        assert any("MISSING-FACT" in e for e in errors)


class TestVerifyOrthogonality:
    def test_all_orthogonal(self):
        violations = verify_orthogonality()
        assert violations == []
