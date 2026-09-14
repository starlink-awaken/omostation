"""E2E tests for bidirectional sync between Obsidian and WPS Note.

Uses a temporary Obsidian vault and mocks the WPS MCP client
to test the full sync cycle without hitting real cloud services.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from iris.config import IrisConfig
from iris.connectors.obsidian import ObsidianConnector
from iris.connectors.wpsnote import WPSNoteConnector
from iris.sync.engine import SyncEngine

# ── Helpers ────────────────────────────────────────────────────────


def _create_vault(files: dict[str, str]) -> Path:
    """Create a temporary Obsidian vault with given files."""
    tmp = Path(tempfile.mkdtemp())
    for rel_path, content in files.items():
        full = tmp / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp


def _make_id_map_path() -> Path:
    """Create a unique temp path for id_map isolation per test."""
    return Path(tempfile.mktemp(suffix="_id_map.json"))  # noqa: S306


def _cleanup(vault: Path, id_map_path: Path | None = None):
    """Clean up temp files after test."""
    import shutil

    shutil.rmtree(vault)
    if id_map_path and id_map_path.exists():
        id_map_path.unlink()


# ── Tests ──────────────────────────────────────────────────────────


class TestE2ESync:
    """End-to-end sync tests using mocked WPS client."""

    def _make_connectors(self, vault: Path | None = None) -> tuple:
        """Create Obsidian and WPS connectors with shared config."""
        # Isolated config file — never write to ~/.iris/config.json
        cfg_path = Path(tempfile.mkdtemp()) / "iris-config.json"
        config = IrisConfig(config_path=cfg_path)
        test_vault = vault or _create_vault({})
        config.set("obsidian.vault", str(test_vault))
        config.set("wpsnote.api_key", "test-key-e2e")
        obsidian = ObsidianConnector(config)
        wpsnote = WPSNoteConnector(config)
        return obsidian, wpsnote, config

    def _make_engine(self, obsidian, wpsnote, config, id_map_path=None):
        return SyncEngine(obsidian, wpsnote, config=config, id_map_path=id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_empty_sync(self, mock_mcp_cls):
        """Sync with no items on either side should produce no changes."""
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {
            "content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]
        }
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault({})
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)
            engine = self._make_engine(obsidian, wpsnote, config, id_map_path)
            result = engine.sync_bidirectional()
            d = result.to_dict()
            assert d["synced"] == 0
            assert d["created"] == 0
            assert d["updated"] == 0
            assert d["deleted"] == 0
            assert d["success"] is True
        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_obsidian_create_syncs_to_wps(self, mock_mcp_cls):
        """A new note in Obsidian should be created in WPS Note."""
        mock_client = MagicMock()
        mock_client.call_tool.side_effect = [
            {"content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]},
        ]
        mock_client.list_tools.return_value = [{"name": "list_notes"}, {"name": "create_note"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault(
            {
                "test-note.md": "---\ntitle: Test Note\n---\nHello from Obsidian",
            }
        )
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            with patch.object(wpsnote, "is_available", return_value=True):
                engine = self._make_engine(obsidian, wpsnote, config, id_map_path)

                with patch.object(wpsnote, "create_item") as mock_create:
                    mock_create.return_value = {
                        "note_id": "wps-created-123",
                        "title": "Test Note",
                        "link_url": "https://kdocs.cn/link",
                    }

                    result = engine.sync_bidirectional()

            d = result.to_dict()
            assert d["synced"] == 1
            assert d["created"] == 1
            assert d["success"] is True

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs.get("title") == "Test Note"
        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_wpsnote_create_syncs_to_obsidian(self, mock_mcp_cls):
        """A new note in WPS Note should be created in Obsidian vault."""
        mock_client = MagicMock()
        mock_client.list_tools.return_value = [{"name": "list_notes"}, {"name": "create_note"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault({})
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            from iris.models import Note

            with (
                patch.object(wpsnote, "is_available", return_value=True),
                patch.object(wpsnote, "list_items") as mock_list,
                patch.object(wpsnote, "get_item") as mock_get,
            ):
                mock_list.return_value = [
                    Note(
                        id="wps-note-1",
                        title="WPS Created Note",
                        platform="wpsnote",
                        content="<p>Content from WPS</p>",
                        updated_at="2026-05-28T10:00:00",
                    )
                ]

                mock_get.return_value = Note(
                    id="wps-note-1",
                    title="WPS Created Note",
                    platform="wpsnote",
                    content="<p>Content from WPS</p>",
                    updated_at="2026-05-28T10:00:00",
                )

                engine = self._make_engine(obsidian, wpsnote, config, id_map_path)
                result = engine.sync_bidirectional()

            d = result.to_dict()
            assert d["synced"] == 1, f"Expected synced=1, got {d}"
            assert d["created"] == 1, f"Expected created=1, got {d}"
            assert d["success"] is True

            vault_files = list(vault.rglob("*.md"))
            assert len(vault_files) >= 1
        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_dry_run_does_not_write(self, mock_mcp_cls):
        """Dry run should detect changes but not apply them."""
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {
            "content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]
        }
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault(
            {
                "dry-note.md": "---\ntitle: Dry Run\n---\nShould not create",
            }
        )
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            with patch.object(wpsnote, "is_available", return_value=True):
                engine = self._make_engine(obsidian, wpsnote, config, id_map_path)

                with patch.object(wpsnote, "create_item") as mock_create:
                    result = engine.sync_bidirectional(dry_run=True)

            d = result.to_dict()
            assert d["created"] == 1  # Detected as new
            assert d["synced"] == 1
            mock_create.assert_not_called()  # Not actually created
        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_id_mapping_persistence(self, mock_mcp_cls):
        """ID mapping should persist after sync and enable detection of updates."""
        mock_client = MagicMock()
        mock_client.call_tool.side_effect = [
            {"content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]},
        ]
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault(
            {
                "persist-note.md": "---\ntitle: Persist Note\n---\nInitial content",
            }
        )
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            with patch.object(wpsnote, "is_available", return_value=True):
                with patch.object(wpsnote, "create_item") as mock_create:
                    mock_create.return_value = {
                        "note_id": "persist-wps-id",
                        "title": "Persist Note",
                        "link_url": "https://kdocs.cn/link",
                    }

                    engine = self._make_engine(obsidian, wpsnote, config, id_map_path)
                    result1 = engine.sync_bidirectional()

            assert result1.created == 1

            # Verify the mapping was stored
            obs_path = "persist-note.md"
            wps_id = engine.id_map.get_wpsnote_id(obs_path)
            assert wps_id == "persist-wps-id"

            path = engine.id_map.get_obsidian_path("persist-wps-id")
            assert path == obs_path

        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_error_isolation(self, mock_mcp_cls):
        """An error processing one change should not affect others."""
        mock_client = MagicMock()
        mock_client.call_tool.side_effect = [
            {"content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]},
        ]
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault(
            {
                "good-note.md": "---\ntitle: Good Note\n---\nThis should sync",
                "bad-note.md": "---\ntitle: Bad Note\n---\nThis will fail",
            }
        )
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            with patch.object(wpsnote, "is_available", return_value=True):
                with patch.object(wpsnote, "create_item") as mock_create:
                    mock_create.side_effect = [
                        Exception("Simulated failure for bad-note"),
                        {
                            "note_id": "good-wps-id",
                            "title": "Good Note",
                            "link_url": "https://kdocs.cn/link",
                        },
                    ]

                    engine = self._make_engine(obsidian, wpsnote, config, id_map_path)
                    result = engine.sync_bidirectional()

            d = result.to_dict()
            assert d["synced"] == 1  # Only one succeeded
            assert d["created"] == 1
            assert len(d["errors"]) == 1  # One error recorded
            assert "Simulated failure" in d["errors"][0]
            assert d["success"] is False  # Overall has errors

        finally:
            _cleanup(vault, id_map_path)

    @patch("iris.connectors.wpsnote.McpClient")
    def test_idempotent_sync(self, mock_mcp_cls):
        """Running sync twice should not produce duplicate content."""
        mock_client = MagicMock()
        mock_client.call_tool.side_effect = [
            {"content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]},
            {"content": [{"type": "text", "text": json.dumps({"notes": [], "has_more": False})}]},
        ]
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        vault = _create_vault(
            {
                "idempotent.md": "---\ntitle: Idempotent\n---\nRun twice, no duplicates",
            }
        )
        id_map_path = _make_id_map_path()
        try:
            obsidian, wpsnote, config = self._make_connectors(vault)

            call_count = 0

            def create_item_side_effect(**kwargs):
                nonlocal call_count
                call_count += 1
                return {
                    "note_id": f"wps-created-{call_count}",
                    "title": kwargs.get("title", ""),
                    "link_url": "https://kdocs.cn/link",
                }

            with patch.object(wpsnote, "is_available", return_value=True):
                with patch.object(wpsnote, "create_item") as mock_create:
                    mock_create.side_effect = create_item_side_effect

                    engine = self._make_engine(obsidian, wpsnote, config, id_map_path)

                    # First sync should create the item
                    result1 = engine.sync_bidirectional()
                    assert result1.created == 1

                    create_count_after_first = mock_create.call_count

                    # Second sync should detect no changes
                    result2 = engine.sync_bidirectional()
                    assert result2.created == 0
                    assert result2.updated == 0

                    # create_item should NOT have been called again
                    assert mock_create.call_count == create_count_after_first

        finally:
            _cleanup(vault, id_map_path)
