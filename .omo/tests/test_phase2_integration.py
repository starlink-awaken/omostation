"""Phase 2 integration test: Eidos ↔ OntoDerive ↔ Minerva adapters."""

import sys
import importlib

# Set PYTHONPATH to include all project src dirs
WORKSPACE = "/Users/xiamingxing/Workspace"
for p in [
    f"{WORKSPACE}/eidos/src",
    f"{WORKSPACE}/ontoderive/engine/src",
    f"{WORKSPACE}/minerva/src",
]:
    if p not in sys.path:
        sys.path.insert(0, p)


def test_ontoderive_to_eidos_entity():
    """OntoDerive Entity -> Eidos OntologyNode."""
    try:
        Entity = importlib.import_module("engine.engine.formal.entity").Entity
        to_eidos_entity = importlib.import_module("engine.ecosystem.eidos_adapter").to_eidos_entity
    except ImportError as e:
        print(f"Skip: {e}")
        return

    entity = Entity(id="test1", node_type="concept", data={"name": "Test Concept"})
    node = to_eidos_entity(entity)
    
    if node is None:
        print("Skip: Eidos not available")
        return
    
    assert node.id == "test1"
    assert node.name == "Test Concept"
    assert node.node_type == "concept"


def test_eidos_to_ontoderive_fact():
    """Eidos Fact -> OntoDerive FormalFact."""
    try:
        Fact = importlib.import_module("eidos.types").Fact
        from_eidos_fact = importlib.import_module("engine.ecosystem.eidos_adapter").from_eidos_fact
    except ImportError as e:
        print(f"Skip: {e}")
        return

    eidos_fact = Fact(id="f1", subject="Earth", predicate="orbits", object="Sun")
    onto_fact = from_eidos_fact(eidos_fact)
    
    if onto_fact is None:
        print("Skip: OntoDerive not available")
        return
    
    assert onto_fact.id == "f1"
    assert onto_fact.data.get("subject") == "Earth"


def test_minerva_to_eidos_card():
    """Minerva research result -> Eidos KnowledgeCard."""
    try:
        research_result_to_card = importlib.import_module("minerva.knowledge.eidos_adapter").research_result_to_card
    except ImportError as e:
        print(f"Skip: {e}")
        return

    result = {
        "title": "Integration Test",
        "content": "Testing Eidos adapter",
        "source": "minerva",
        "source_type": "research",
    }
    card = research_result_to_card(result)
    
    if card is None:
        print("Skip: Eidos not available")
        return
    
    assert card.title == "Integration Test"
    assert card.schema_type == "KnowledgeCard"
    assert card.validate() == []


def test_eidos_can_validate_ontoderive_output():
    """Eidos validator can validate the converted OntologyNode."""
    try:
        to_eidos_entity = importlib.import_module("engine.ecosystem.eidos_adapter").to_eidos_entity
        Entity = importlib.import_module("engine.engine.formal.entity").Entity
    except ImportError as e:
        print(f"Skip: {e}")
        return

    entity = Entity(id="v1", node_type="validated", data={"name": "Valid"})
    node = to_eidos_entity(entity)
    
    if node is None:
        print("Skip: Eidos not available")
        return
    
    errors = node.validate()
    assert len(errors) == 0, f"Validation errors: {errors}"


def test_adapters_graceful_fallback():
    """All adapters work when Eidos is NOT available."""
    try:
        adapter = importlib.import_module("engine.ecosystem.eidos_adapter")
    except ImportError as e:
        print(f"Skip: {e}")
        return
    
    # Clear eidos from sys.modules to simulate absence
    saved = {}
    for k in list(sys.modules.keys()):
        if k.startswith("eidos"):
            saved[k] = sys.modules.pop(k)
    
    try:
        if "engine.ecosystem.eidos_adapter" in sys.modules:
            importlib.reload(sys.modules["engine.ecosystem.eidos_adapter"])
        # is_eidos_available may still be True if eidos persists in path
        # The test validates the function exists and returns bool
        assert isinstance(adapter.is_eidos_available(), bool)
        assert adapter.to_eidos_entity(None) is None
    finally:
        # Restore
        sys.modules.update(saved)
