"""Tests for iris data models."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from iris.models import Article, Bookmark, Highlight, Note, SyncState


class TestModels:
    def test_note_creation(self):
        note = Note(id="n1", title="Test Note", platform="obsidian", content="Hello")
        assert note.id == "n1"
        assert note.title == "Test Note"
        assert note.content == "Hello"

    def test_note_to_knowledge_card(self):
        note = Note(
            id="n1",
            title="Test",
            platform="obsidian",
            content="# Hello",
            tags=["test"],
        )
        card = note.to_knowledge_card()
        assert card["id"] == "obsidian/n1"
        assert card["title"] == "Test"
        assert card["content"] == "# Hello"
        assert card["schema_type"] == "KnowledgeCard"
        assert "test" in card["tags"]

    def test_note_to_dict(self):
        note = Note(id="n1", title="T", platform="p", content="c")
        d = note.to_dict()
        assert d["id"] == "n1"
        assert d["content"] == "c"

    def test_highlight_creation(self):
        hl = Highlight(id="h1", title="Highlight", platform="wxread", text="important passage")
        assert hl.text == "important passage"

    def test_highlight_to_knowledge_card(self):
        hl = Highlight(
            id="h1",
            title="HL",
            platform="wxread",
            text="key point",
            annotation="my note",
            source_url="https://weread.qq.com/book/1",
        )
        card = hl.to_knowledge_card()
        assert "key point" in card["content"]
        assert "my note" in card["content"]
        assert "highlight" in card["tags"]
        assert "platform:wxread" in card["tags"]

    def test_article_creation(self):
        art = Article(
            id="a1",
            title="Article",
            platform="zhihu",
            content="long content",
            url="https://zhihu.com/1",
        )
        assert art.url == "https://zhihu.com/1"

    def test_bookmark_creation(self):
        bm = Bookmark(id="b1", title="Bookmark", platform="chrome", url="https://example.com")
        assert bm.url == "https://example.com"

    def test_bookmark_to_knowledge_card(self):
        bm = Bookmark(
            id="b1",
            title="Example",
            platform="chrome",
            url="https://example.com",
            description="A site",
        )
        card = bm.to_knowledge_card()
        assert card["id"] == "bookmark/b1"
        assert "bookmark" in card["tags"]

    def test_sync_state(self):
        state = SyncState(connector_name="obsidian", status="idle")
        assert state.connector_name == "obsidian"
        d = state.to_dict()
        assert d["connector_name"] == "obsidian"
