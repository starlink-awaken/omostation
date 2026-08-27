"""Basic smoke tests for core-models package."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from core_models import ENTITY_TYPES, RELATION_TYPES, Entity, KnowledgeGraph, Provenance, Relation
from core_models.capability import CapabilityRegistry, CapabilitySchema
from core_models.entity import EntityType
from core_models.neuron_pool import NeuronPool, ServiceRef
from core_models.protocols.circuit import CircuitDefinition, CircuitStep, FailureAction
from core_models.protocols.governance import GovernancePolicy
from core_models.protocols.health import HealthStatus
from core_models.protocols.identity import IdentityResult
from core_models.relation import RelationType


class TestCoreModelsBasic:
    """Core functionality and edge case tests."""

    def test_imports(self):
        """All expected exports are importable."""
        assert Entity is not None
        assert Relation is not None
        assert Provenance is not None
        assert KnowledgeGraph is not None
        assert ENTITY_TYPES is not None
        assert RELATION_TYPES is not None

    def test_entity_creation(self):
        """Entity with minimal fields."""
        e = Entity(id="e1", name="TestEntity", type="Function", source="test")
        assert e.id == "e1"
        assert e.name == "TestEntity"
        assert e.type == "Function"

    def test_relation_creation(self):
        """Relation with minimal fields."""
        r = Relation(
            source_id="e1",
            target_id="e2",
            type="CALLS",
        )
        assert r.source_id == "e1"
        assert r.target_id == "e2"

    def test_provenance_creation(self):
        """Provenance with minimal fields."""
        p = Provenance(
            source_file="test",
            analyzer="test",
        )
        assert p.source_file == "test"

    def test_knowledge_graph_init(self):
        """KnowledgeGraph initializes empty."""
        kg = KnowledgeGraph()
        assert len(kg.entities) == 0
        assert len(kg.relations) == 0

    def test_entity_types_contains_known(self):
        assert "Function" in ENTITY_TYPES
        assert "Class" in ENTITY_TYPES
        assert len(ENTITY_TYPES) >= 20

    def test_capability_registry(self):
        """CapabilityRegistry initializes."""
        reg = CapabilityRegistry()
        assert reg.list_capabilities() == []

    def test_capability_schema(self):
        """CapabilitySchema stores parameters."""
        schema = CapabilitySchema(name="test", description="Test capability")
        assert schema.name == "test"
        assert schema.description == "Test capability"
        # No required_params, so any params are valid
        assert schema.validate({"param1": "val1"}) is True
        assert schema.validate({}) is True

    def test_circuit_definition(self):
        """CircuitDefinition stores parameters."""
        step = CircuitStep(id="step1", action="fetch")
        cd = CircuitDefinition(name="test", steps=[step])
        assert cd.name == "test"
        assert len(cd.steps) == 1
        assert cd.steps[0].id == "step1"

    def test_failure_action_enum(self):
        """FailureAction enum has expected values."""
        assert FailureAction.REJECT.value == "reject"
        assert FailureAction.RETRY.value == "retry"
        assert FailureAction.SKIP.value == "skip"

    def test_health_status(self):
        """HealthStatus with service field."""
        hs = HealthStatus(service="test-component", status="healthy", version="1.0")
        assert hs.service == "test-component"
        assert hs.status == "healthy"
        assert hs.version == "1.0"

    def test_identity_result(self):
        """IdentityResult creation."""
        ir = IdentityResult(identity_id="i1", principal="test-user", authenticated=True)
        assert ir.identity_id == "i1"
        assert ir.authenticated is True

    def test_governance_policy(self):
        """GovernancePolicy stores parameters."""
        gp = GovernancePolicy(service="test-svc", compliance_level="full")
        assert gp.service == "test-svc"
        assert gp.compliance_level == "full"
        assert gp.audit_enabled is False

    def test_service_ref_creation(self):
        """ServiceRef with minimal fields."""
        ref = ServiceRef(name="test-svc", endpoint="http://localhost:8000")
        assert ref.name == "test-svc"
        assert ref.endpoint == "http://localhost:8000"
        assert ref.priority == 1
        assert ref.healthy_status is True

    def test_neuron_pool_init(self):
        """NeuronPool initializes."""
        pool = NeuronPool()
        assert pool.list_names() == []

    def test_entity_type_alias(self):
        """EntityType alias works."""
        assert EntityType is not None

    def test_relation_type_alias(self):
        """RelationType alias works."""
        assert RelationType is not None
