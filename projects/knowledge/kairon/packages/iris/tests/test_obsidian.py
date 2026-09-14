"""Integration tests for Obsidian connector.

Uses a temporary vault directory with carefully crafted .md files.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import tempfile
from pathlib import Path

import pytest
from iris.base import parse_frontmatter, strip_frontmatter
from iris.config import IrisConfig
from iris.connectors.obsidian import (
    ObsidianConnector,
    _generate_frontmatter,
    _slugify,
    _yaml_value,
)


def _create_test_vault(files: dict[str, str]) -> Path:
    """Create a temporary Obsidian vault with given files."""
    tmp = Path(tempfile.mkdtemp())
    for rel_path, content in files.items():
        full = tmp / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp


class TestFrontmatterParsing:
    def test_inline_tags(self):
        content = "---\ntitle: Test\ntags: [a, b, c]\n---\nBody"
        result = parse_frontmatter(content)
        assert result["tags"] == ["a", "b", "c"]
        assert result["title"] == "Test"

    def test_block_tags(self):
        content = "---\ntags:\n  - python\n  - ai\n  - test\n---\nBody"
        result = parse_frontmatter(content)
        assert result["tags"] == ["python", "ai", "test"]

    def test_mixed_tags(self):
        """Block format with single value."""
        content = "---\ntags:\n  - python\n---\nBody"
        result = parse_frontmatter(content)
        assert result["tags"] == ["python"]

    def test_block_aliases(self):
        content = "---\naliases:\n  - alias1\n  - alias2\n---\nBody"
        result = parse_frontmatter(content)
        assert result["aliases"] == ["alias1", "alias2"]

    def test_no_frontmatter(self):
        content = "Just a body\nNo frontmatter\n"
        result = parse_frontmatter(content)
        assert result["tags"] == []

    def test_empty_frontmatter(self):
        content = "---\n---\nBody"
        result = parse_frontmatter(content)
        assert result["tags"] == []

    def test_title_from_frontmatter(self):
        content = '---\ntitle: "My Note"\n---\nBody'
        result = parse_frontmatter(content)
        assert result["title"] == "My Note"

    def test_created_date(self):
        content = "---\ncreated: 2024-01-15\n---\nBody"
        result = parse_frontmatter(content)
        assert result["created"] == "2024-01-15"

    def test_date_field(self):
        content = "---\ndate: 2024-06-01\n---\nBody"
        result = parse_frontmatter(content)
        assert result["created"] == "2024-06-01"


class TestStripFrontmatter:
    def test_strips_frontmatter(self):
        content = "---\ntitle: Test\n---\nBody text"
        assert strip_frontmatter(content) == "Body text"

    def test_no_frontmatter(self):
        content = "Just body"
        assert strip_frontmatter(content) == "Just body"


class TestObsidianConnector:
    def test_is_available_with_vault(self):
        vault = _create_test_vault({"test.md": "# Hello"})
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            assert conn.is_available() is True
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_is_available_no_vault(self):
        config = IrisConfig()
        config.set("obsidian.vault", "/tmp/nonexistent-vault-12345")
        conn = ObsidianConnector(config)
        assert conn.is_available() is False

    def test_list_items_returns_notes(self):
        vault = _create_test_vault(
            {
                "note1.md": "# Note 1",
                "sub/note2.md": "# Note 2",
            }
        )
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            items = conn.list_items(limit=10)
            assert len(items) == 2
            assert items[0].platform == "obsidian"
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_list_items_limit(self):
        vault = _create_test_vault({f"note{i}.md": f"# Note {i}" for i in range(10)})
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            items = conn.list_items(limit=3)
            assert len(items) == 3
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_get_item_by_id(self):
        vault = _create_test_vault({"mynote.md": "# My Note"})
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            items = conn.list_items(limit=10)
            assert len(items) == 1
            note_id = items[0].id
            # Retrieve by ID
            note = conn.get_item(note_id)
            assert note is not None
            assert note.title == "mynote"
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_get_item_unknown_id_returns_none(self):
        vault = _create_test_vault({"a.md": "# A"})
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            assert conn.get_item("nonexistent") is None
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_get_item_path_traversal_blocked(self):
        vault = _create_test_vault({"safe.md": "# Safe"})
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            # These should all return None (not escape vault)
            assert conn.get_item("..--..--etc--passwd") is None
            assert conn.get_item("..--..--..--tmp--foo") is None
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_search_finds_content(self):
        vault = _create_test_vault(
            {
                "match.md": "# Match\nkeyword is here",
                "nomatch.md": "# No Match\nnothing",
            }
        )
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        try:
            conn = ObsidianConnector(config)
            results = conn.search("keyword")
            assert len(results) == 1
            assert results[0].title == "match"
        finally:
            import shutil

            shutil.rmtree(vault)


class TestSlugify:
    def test_basic_slug(self):
        assert _slugify("My Note") == "my-note"

    def test_preserves_chinese(self):
        slug = _slugify("我的笔记")
        assert slug == "我的笔记"

    def test_removes_special_chars(self):
        slug = _slugify("foo: bar / baz?")
        assert slug == "foo-bar-baz"

    def test_empty_string(self):
        assert _slugify("  ") == "untitled"


class TestYamlValue:
    def test_plain_string(self):
        assert _yaml_value("hello") == "hello"

    def test_empty_string(self):
        assert _yaml_value("") == '""'

    def test_quotes_when_needed(self):
        assert _yaml_value("hello: world") == '"hello: world"'
        assert _yaml_value("a#b") == '"a#b"'

    def test_no_extra_quotes_for_simple(self):
        assert _yaml_value("hello world") == "hello world"


class TestGenerateFrontmatter:
    def test_minimal(self):
        fm = _generate_frontmatter(title="Test")
        assert fm.startswith("---")
        assert fm.endswith("---")
        assert "title: Test" in fm

    def test_with_tags_block(self):
        fm = _generate_frontmatter(title="My Note", tags=["tag1", "tag2"])
        lines = fm.split("\n")
        assert "title: My Note" in lines
        assert "tags:" in lines
        assert "  - tag1" in lines
        assert "  - tag2" in lines

    def test_with_dates(self):
        fm = _generate_frontmatter(title="Note", created_at="2024-01-15", updated_at="2024-06-01")
        assert "created_at: 2024-01-15" in fm
        assert "updated_at: 2024-06-01" in fm

    def test_with_iris_id(self):
        fm = _generate_frontmatter(title="Note", iris_id="abc123")
        assert "iris_id: abc123" in fm

    def test_with_status_deleted(self):
        fm = _generate_frontmatter(title="Note", status="deleted")
        assert "status: deleted" in fm


# ------------------------------------------------------------------
# Write-operation tests
# ------------------------------------------------------------------


class TestObsidianConnectorWrite:
    """Tests for create_item, update_item, and delete_item.

    All operations are performed on temporary vault directories.
    """

    def _make_conn(self, vault: Path) -> ObsidianConnector:
        config = IrisConfig()
        config.set("obsidian.vault", str(vault))
        return ObsidianConnector(config)

    # --- create_item ---

    def test_create_item_basic(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Hello World", content="This is the body.")
            assert note.title == "Hello World"
            assert "This is the body." in note.content
            assert note.tags == []

            # File should exist
            full_path = vault / "hello-world.md"
            assert full_path.exists()
            content = full_path.read_text()
            assert "Hello World" in content
            assert "This is the body." in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_with_tags(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Tagged Note", content="Body", tags=["python", "obsidian"])
            assert note.tags == ["python", "obsidian"]
            content = (vault / "tagged-note.md").read_text()
            assert "  - python" in content
            assert "  - obsidian" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_with_custom_path(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(
                title="Deep Note",
                content="Content",
                path="subfolder/my_note.md",
            )
            full_path = vault / "subfolder" / "my_note.md"
            assert full_path.exists()
            assert note.source_path == str(full_path.resolve())
            assert note.platform_notebook == "subfolder"
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_duplicate_raises(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            conn.create_item(title="Unique")
            with pytest.raises(FileExistsError):
                conn.create_item(title="Unique")
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_path_traversal_blocked(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            with pytest.raises(ValueError, match="Path traversal detected"):
                conn.create_item(title="Bad", path="../escape.md")
            with pytest.raises(ValueError, match="Path traversal detected"):
                conn.create_item(title="Bad", path="../../etc/passwd")
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_sets_iris_id(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="IdTest")
            assert note.id != ""
            content = (vault / "idtest.md").read_text()
            assert f"iris_id: {note.id}" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_without_content(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Empty Content")
            assert note.content != ""
            assert "---" in note.content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_create_item_chinese_title(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="我的笔记", content="你好世界")
            assert note.title == "我的笔记"
            full_path = vault / "我的笔记.md"
            assert full_path.exists()
            content = full_path.read_text()
            assert "你好世界" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    # --- update_item ---

    def test_update_item_title(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Original", content="Body")
            updated = conn.update_item(note.id, {"title": "Updated Title"})
            assert updated is not None
            assert updated.title == "Updated Title"
            content = (vault / "original.md").read_text()
            assert "title: Updated Title" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_update_item_content(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Note", content="Old content")
            updated = conn.update_item(note.id, {"content": "New content here"})
            assert updated is not None
            assert "New content here" in updated.content
            assert "Old content" not in updated.content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_update_item_tags(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Note", content="Body", tags=["a", "b"])
            updated = conn.update_item(note.id, {"tags": ["x", "y", "z"]})
            assert updated is not None
            assert updated.tags == ["x", "y", "z"]
            content = (vault / "note.md").read_text()
            assert "  - x" in content
            assert "  - y" in content
            assert "  - z" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_update_item_partial(self):
        """Only title changed, content and tags preserved."""
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="Original", content="Body text", tags=["tag1"])
            updated = conn.update_item(note.id, {"title": "Renamed"})
            assert updated is not None
            assert updated.title == "Renamed"
            assert "Body text" in updated.content
            assert "tag1" in updated.tags
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_update_item_nonexistent_returns_none(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            result = conn.update_item("bogus-id-that-doesnt-exist", {"title": "Nope"})
            assert result is None
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_update_item_sets_updated_at(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="TimeTest", content="Body")
            updated = conn.update_item(note.id, {"title": "Patched"})
            assert updated is not None
            assert updated.updated_at != ""
            assert updated.updated_at >= updated.created_at
        finally:
            import shutil

            shutil.rmtree(vault)

    # --- delete_item (soft) ---

    def test_delete_item_soft(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="ToDelete", content="Will be deleted")
            result = conn.delete_item(note.id, soft=True)
            assert result is True

            # File should still exist but have status: deleted
            full_path = vault / "todelete.md"
            assert full_path.exists()
            content = full_path.read_text()
            assert "status: deleted" in content
            assert "Will be deleted" in content
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_delete_item_soft_nonexistent(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            result = conn.delete_item("nonexistent-id", soft=True)
            assert result is False
        finally:
            import shutil

            shutil.rmtree(vault)

    # --- delete_item (hard) ---

    def test_delete_item_hard(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="HardDelete", content="Gone")
            result = conn.delete_item(note.id, soft=False)
            assert result is True

            # File should be moved to _trash/
            assert not (vault / "harddelete.md").exists()
            assert (vault / "_trash" / "harddelete.md").exists()
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_delete_item_hard_nonexistent(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            result = conn.delete_item("nonexistent-id", soft=False)
            assert result is False
        finally:
            import shutil

            shutil.rmtree(vault)

    def test_delete_item_hard_with_subfolder(self):
        vault = Path(tempfile.mkdtemp())
        conn = self._make_conn(vault)
        try:
            note = conn.create_item(title="SubDelete", content="Body", path="deep/note.md")
            result = conn.delete_item(note.id, soft=False)
            assert result is True
            assert (vault / "_trash" / "deep" / "note.md").exists()
        finally:
            import shutil

            shutil.rmtree(vault)
