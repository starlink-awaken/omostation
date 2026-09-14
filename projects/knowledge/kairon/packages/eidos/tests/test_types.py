# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from eidos.types.fact import Fact
from eidos.types.knowledge_card import KnowledgeCard, Relation
from eidos.types.ontology_node import OntologyNode


def test_knowledge_card_create_and_validate():
    card = KnowledgeCard(
        id="kc-1",
        title="Test Card",
        content="Some content",
        source="docs/test.md",
        source_type="file",
        schema_type="KnowledgeCard",
    )

    assert card.validate() == []


def test_knowledge_card_roundtrip():
    card = KnowledgeCard(
        id="kc-1",
        title="Test Card",
        content="Some content",
        source="docs/test.md",
        source_type="file",
        schema_type="KnowledgeCard",
        tags=["a", "b"],
        created_at="2026-05-20T00:00:00Z",
        updated_at="2026-05-20T00:00:00Z",
    )

    assert KnowledgeCard.from_dict(card.to_dict()) == card


def test_knowledge_card_with_relations():
    card = KnowledgeCard(
        id="kc-1",
        title="Test Card",
        content="Some content",
        source="docs/test.md",
        source_type="file",
        schema_type="KnowledgeCard",
        relations=[Relation(target_id="n-1", relation_type="related_to", label="see also")],
    )

    assert card.to_dict()["relations"][0]["target_id"] == "n-1"


def test_invalid_knowledge_card_missing_id():
    card = KnowledgeCard(
        id="",
        title="Test Card",
        content="Some content",
        source="docs/test.md",
        source_type="file",
        schema_type="KnowledgeCard",
    )

    assert "id is required" in card.validate()


def test_fact_create_and_roundtrip():
    fact = Fact(id="f-1", subject="Earth", predicate="is", object="round")

    assert Fact.from_dict(fact.to_dict()) == fact
    assert fact.validate() == []


def test_ontology_node_create_and_roundtrip():
    node = OntologyNode(
        id="o-1",
        name="Thing",
        node_type="concept",
        properties={"rank": 1},
        aliases=["Item"],
        description="A concept node",
    )

    assert OntologyNode.from_dict(node.to_dict()) == node
    assert node.validate() == []
