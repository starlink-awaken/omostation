"""Basic tests for dispatcher."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kronos.dispatcher import vault_write, wps_blockquote, wps_heading, wps_highlight, wps_key_points, wps_summary_note


class TestVaultWrite:
    def test_vault_write(self):
        result = vault_write("文章", "test-title", "# Test Body")
        assert result["title"] == "test-title"
        assert result["size"] > 0
        assert "path" in result

    def test_vault_write_empty(self):
        result = vault_write("", "", "")
        assert result["title"] is not None


class TestWpsHelpers:
    def test_blockquote(self):
        q = wps_blockquote("https://example.com")
        assert "example.com" in q
        assert "blockquote" in q

    def test_heading(self):
        h = wps_heading("Test")
        assert "h2" in h
        assert "Test" in h

    def test_highlight(self):
        h = wps_highlight("Important")
        assert "highlightBlock" in h
        assert "Important" in h

    def test_key_points(self):
        xml = wps_key_points(["Point 1", "Point 2"])
        assert "Point 1" in xml
        assert "Point 2" in xml

    def test_summary_note(self):
        note = wps_summary_note("Title", "Summary", ["K1"], "https://x.com")
        assert "Title" in note or "Summary" in note or "K1" in note
        assert "Summary" in note
        assert "K1" in note
