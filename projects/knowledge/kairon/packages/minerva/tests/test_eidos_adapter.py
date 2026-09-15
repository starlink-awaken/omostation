"""Unit tests for Minerva Eidos adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_research_result_to_card_with_content():
    """Research result with 'content' field converts correctly."""
    from minerva.knowledge.eidos_adapter import research_result_to_card

    result = {
        "title": "AI Research",
        "content": "This is the full content",
        "source": "minerva:research",
        "source_type": "research",
        "tags": ["AI"],
    }
    card = research_result_to_card(result)

    if card is None:
        import pytest

        pytest.skip("Eidos not available")

    assert card.title == "AI Research"
    assert card.content == "This is the full content"
    assert card.source_type == "research"
    assert card.schema_type == "KnowledgeCard"
    assert "AI" in card.tags
    assert card.validate() == []


def test_research_result_with_snippet_fallback():
    """Research result with only 'snippet' field uses it as content."""
    from minerva.knowledge.eidos_adapter import research_result_to_card

    result = {
        "title": "Summary Only",
        "snippet": "This is a short snippet",
        "source": "test",
    }
    card = research_result_to_card(result)

    if card is None:
        import pytest

        pytest.skip("Eidos not available")

    assert card.content == "This is a short snippet"


def test_research_result_content_priority():
    """content field takes priority over snippet when both present."""
    from minerva.knowledge.eidos_adapter import research_result_to_card

    result = {
        "title": "Both Fields",
        "content": "Full content here",
        "snippet": "Short snippet",
        "source": "test",
    }
    card = research_result_to_card(result)

    if card is None:
        import pytest

        pytest.skip("Eidos not available")

    assert card.content == "Full content here"


def test_entity_to_node():
    """Minerva Entity -> Eidos OntologyNode"""
    from minerva.knowledge.eidos_adapter import entity_to_node

    class MockEntity:
        id = "ent1"
        name = "Quantum Computing"
        type = "concept"
        properties = {"field": "physics"}
        aliases = ["QC", "quantum"]
        description = ""

    entity = MockEntity()
    node = entity_to_node(entity)

    if node is None:
        import pytest

        pytest.skip("Eidos not available")

    assert node.id == "ent1"
    assert node.name == "Quantum Computing"
    assert node.node_type == "concept"
    assert node.properties.get("field") == "physics"
    assert "QC" in node.aliases


def test_entity_to_node_empty_properties():
    """Entity with empty/Nones properties produces valid node."""
    from minerva.knowledge.eidos_adapter import entity_to_node

    class MinimalEntity:
        id = "min1"
        name = "Minimal"
        type = "entity"
        properties = None
        aliases = []

    entity = MinimalEntity()
    node = entity_to_node(entity)

    if node is None:
        import pytest

        pytest.skip("Eidos not available")

    assert node.id == "min1"
    assert node.validate() == []


def test_export_cards_to_json(tmp_path):
    """Export creates valid JSON file."""
    from minerva.knowledge.eidos_adapter import export_cards_to_json, research_result_to_card

    result = {"title": "Export Test", "content": "Test", "source": "test"}
    card = research_result_to_card(result)

    if card is None:
        import pytest

        pytest.skip("Eidos not available")

    output = tmp_path / "cards.json"
    count = export_cards_to_json([card], str(output))

    assert count == 1
    assert output.exists()
    import json

    data = json.loads(output.read_text())
    assert len(data) == 1
    assert data[0]["title"] == "Export Test"


def test_is_eidos_available():
    """is_eidos_available returns bool."""
    from minerva.knowledge.eidos_adapter import is_eidos_available

    assert isinstance(is_eidos_available(), bool)
