"""Basic tests for adapters."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kronos.adapters import to_knowledge_card, to_knowledge_card_from_browser_fetch


class TestToKnowledgeCard:
    def test_minimal(self):
        card = to_knowledge_card({"title": "Test", "summary": "A test"}, "https://example.com")
        assert card["title"] == "Test"
        assert card["source"] == "https://example.com"
        assert "KC-" in card["id"]

    def test_empty_extraction(self):
        card = to_knowledge_card({}, "source")
        assert card["title"] is not None
        assert isinstance(card["tags"], list)

    def test_with_content(self):
        card = to_knowledge_card({"title": "T", "summary": "S", "key_points": ["K1"]}, "url", content="Custom")
        assert "Custom" in card["content"]

    def test_source_type_mapping(self):
        card = to_knowledge_card({"title": "T", "summary": "S", "content_type": "论文"}, "url")
        assert card["source_type"] == "paper"


class TestBrowserFetchCard:
    def test_basic(self):
        card = to_knowledge_card_from_browser_fetch("https://x.com", "# Hello", "Test Title")
        assert card["title"] == "Test Title"
        assert card["source"] == "https://x.com"
        assert "KC-" in card["id"]

    def test_empty_title(self):
        card = to_knowledge_card_from_browser_fetch("https://x.com", "", "")
        assert card["title"] == "Untitled"
