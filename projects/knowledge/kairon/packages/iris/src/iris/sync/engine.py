"""SyncEngine — the bidirectional sync orchestrator.

Ties together IdMapping, FormatConverter, ChangeTracker, and ConflictResolver
to orchestrate a full bidirectional sync between Obsidian and WPS Note.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from iris.base import BaseConnector
from iris.config import IrisConfig
from iris.models import KnowledgeArtifact, Note
from iris.sync.changes import Change, ChangeTracker, ChangeType
from iris.sync.conflict import ConflictResolver
from iris.sync.format import FormatConverter
from iris.sync.id_map import IdMapping

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a bidirectional sync operation."""

    synced: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "synced": self.synced,
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "success": len(self.errors) == 0,
        }


class SyncEngine:
    """Orchestrates bidirectional sync between Obsidian and WPS Note.

    Flow:
      1. Detect changes on both sides
      2. Process Obsidian → WPS changes (create/update/delete)
      3. Process WPS → Obsidian changes (create/update/delete)
      4. Resolve conflicts
      5. Update ID mapping
    """

    def __init__(
        self,
        obsidian_connector: BaseConnector,
        wpsnote_connector: BaseConnector,
        config: IrisConfig | None = None,
        id_map_path: str | Path | None = None,
        conflict_strategy: str = "last_write_wins",
    ):
        self._obsidian = obsidian_connector
        self._wpsnote = wpsnote_connector
        self._config = config or IrisConfig()

        self.id_map = IdMapping(store_path=id_map_path)
        self.format_converter = FormatConverter()
        self.change_tracker = ChangeTracker(obsidian_connector, wpsnote_connector, self.id_map)
        self.conflict_resolver = ConflictResolver(strategy=conflict_strategy)

    def sync_bidirectional(self, dry_run: bool = False) -> SyncResult:
        """Execute a full bidirectional sync cycle.

        Args:
            dry_run: If True, preview changes without writing.

        Returns:
            SyncResult with statistics.
        """
        result = SyncResult(
            timestamp=datetime.now(UTC).isoformat(),
        )

        try:
            # Step 1: Detect changes
            logger.info("Detecting changes...")
            obsidian_changes, wpsnote_changes = self.change_tracker.detect_changes()

            if dry_run:
                logger.info(
                    "DRY RUN: Obsidian changes: %d, WPS Note changes: %d",
                    len(obsidian_changes),
                    len(wpsnote_changes),
                )
                result.synced = len(obsidian_changes) + len(wpsnote_changes)
                result.created = sum(1 for c in obsidian_changes + wpsnote_changes if c.type == ChangeType.CREATED)
                result.updated = sum(1 for c in obsidian_changes + wpsnote_changes if c.type == ChangeType.UPDATED)
                result.deleted = sum(1 for c in obsidian_changes + wpsnote_changes if c.type == ChangeType.DELETED)
                return result

            # Step 2: Process Obsidian → WPS Note changes
            logger.info("Processing Obsidian → WPS Note: %d changes", len(obsidian_changes))
            for change in obsidian_changes:
                try:
                    self._process_obsidian_change(change, result)
                except Exception as e:
                    msg = f"Failed to process Obsidian change '{change.item_title}': {e}"
                    logger.exception(msg)
                    result.errors.append(msg)

            # Step 3: Process WPS Note → Obsidian changes
            logger.info("Processing WPS Note → Obsidian: %d changes", len(wpsnote_changes))
            for change in wpsnote_changes:
                try:
                    self._process_wpsnote_change(change, result)
                except Exception as e:
                    msg = f"Failed to process WPS Note change '{change.item_title}': {e}"
                    logger.exception(msg)
                    result.errors.append(msg)

            logger.info(
                "Sync complete: %d synced, %d created, %d updated, %d deleted, %d errors",
                result.synced,
                result.created,
                result.updated,
                result.deleted,
                len(result.errors),
            )

        except Exception as e:
            msg = f"Sync engine error: {e}"
            logger.exception(msg)
            result.errors.append(msg)

        return result

    # ── Change processing: Obsidian → WPS Note ────────────────────

    def _process_obsidian_change(self, change: Change, result: SyncResult) -> None:
        """Process a single change on the Obsidian side, applying it to WPS Note."""
        if change.type == ChangeType.CREATED:
            # Get the full Obsidian item
            item = self._obsidian.get_item(change.item_id)
            if item is None:
                result.errors.append(f"Obsidian item {change.item_id} not found after change detection")
                return

            # Get the relative path for the ID mapping
            obs_path = self._get_item_path(item)

            # Convert Markdown body to WPS XML
            body = self._get_markdown_body(cast(Note, item).content)
            xml_content = self.format_converter.markdown_to_xml(body)

            # Create in WPS Note
            wps_result = self._wpsnote.create_item(
                title=item.title,
                content=xml_content,
                tags=item.tags if hasattr(item, "tags") and item.tags else None,  # type: ignore[reportAttributeAccessIssue]
            )

            if isinstance(wps_result, dict) and wps_result.get("note_id"):
                wps_id = wps_result["note_id"]
                self.id_map.set_mapping(obs_path, wps_id)
                result.created += 1
                result.synced += 1
                logger.info("  CREATED Obsidian→WPS: '%s' → %s", item.title, wps_id)

        elif change.type == ChangeType.UPDATED:
            # Get the Obsidian item
            item = self._obsidian.get_item(change.item_id)
            if item is None:
                # Item was deleted between detection and processing — treat as deletion
                obs_path = change.item_id
                wps_id = self.id_map.get_wpsnote_id(obs_path)
                if wps_id:
                    self._wpsnote.delete_item(wps_id)
                    self.id_map.remove(obs_path)
                    result.deleted += 1
                    result.synced += 1
                return

            obs_path = self._get_item_path(item)
            wps_id = self.id_map.get_wpsnote_id(obs_path)
            if wps_id is None:
                # Mapping doesn't exist — try creating instead
                self._process_obsidian_change(
                    Change(ChangeType.CREATED, "obsidian", change.item_id, change.item_title, change.timestamp),
                    result,
                )
                return

            # Convert and update
            body = self._get_markdown_body(cast(Note, item).content)
            xml_content = self.format_converter.markdown_to_xml(body)

            update_data: dict[str, Any] = {"content": xml_content}
            if item.title:
                update_data["title"] = item.title

            self._wpsnote.update_item(wps_id, update_data)
            result.updated += 1
            result.synced += 1
            logger.info("  UPDATED Obsidian→WPS: '%s'", item.title)

        elif change.type == ChangeType.DELETED:
            # The Obsidian item was deleted — remove from WPS Note too
            obs_path = change.item_id
            wps_id = self.id_map.get_wpsnote_id(obs_path)
            if wps_id:
                try:
                    self._wpsnote.delete_item(wps_id)
                except Exception as e:
                    logger.warning("Failed to delete WPS note %s: %s", wps_id, e)
                self.id_map.remove(obs_path)
                result.deleted += 1
                result.synced += 1
                logger.info("  DELETED Obsidian→WPS: %s", obs_path)

    # ── Change processing: WPS Note → Obsidian ────────────────────

    def _process_wpsnote_change(self, change: Change, result: SyncResult) -> None:
        """Process a single change on the WPS Note side, applying it to Obsidian."""
        if change.type == ChangeType.CREATED:
            # Get the full WPS Note item
            item = self._wpsnote.get_item(change.item_id)
            if item is None:
                result.errors.append(f"WPS Note item {change.item_id} not found after change detection")
                return

            # Convert XML content to Markdown
            xml_content = cast(Note, item).content
            md_body = self.format_converter.xml_to_markdown(xml_content)

            # Generate a valid Obsidian path
            from iris.connectors.obsidian import _slugify

            slug = _slugify(item.title)
            obs_path = f"sync/{slug}.md"

            # Create in Obsidian vault
            # Provide both frontmatter and body
            tags = item.tags if hasattr(item, "tags") and item.tags else None  # type: ignore[reportAttributeAccessIssue]
            try:
                self._obsidian.create_item(
                    title=item.title,
                    content=md_body,
                    tags=tags,
                    path=obs_path,
                )
                result.created += 1
                logger.info("  CREATED WPS→Obsidian: '%s' → %s", item.title, obs_path)
            except FileExistsError:
                # Path already present (prior partial sync) — adopt mapping without overwrite
                self.id_map.set_mapping(obs_path, change.item_id)
                result.synced += 1
                logger.info("  ADOPTED existing Obsidian path for WPS→Obsidian: '%s' → %s", item.title, obs_path)
                return

            # Record the mapping
            self.id_map.set_mapping(obs_path, change.item_id)
            result.synced += 1

        elif change.type == ChangeType.UPDATED:
            # Get the WPS Note item
            item = self._wpsnote.get_item(change.item_id)
            if item is None:
                # Was deleted between detection and processing
                obs_path = cast("str", self.id_map.get_obsidian_path(change.item_id))
                if obs_path:
                    # Find the Obsidian item by path
                    self._delete_obsidian_by_path(obs_path)
                    self.id_map.remove(obs_path)
                    result.deleted += 1
                    result.synced += 1
                return

            # Get the corresponding Obsidian path
            obs_path = cast("str", self.id_map.get_obsidian_path(change.item_id))
            if obs_path is None:
                # No mapping — treat as create
                self._process_wpsnote_change(
                    Change(ChangeType.CREATED, "wpsnote", change.item_id, change.item_title, change.timestamp),
                    result,
                )
                return

            # Convert XML to Markdown
            xml_content = cast(Note, item).content
            md_body = self.format_converter.xml_to_markdown(xml_content)

            # Find Obsidian item ID from path
            obsidian_id = self._find_obsidian_id_by_path(obs_path)
            if obsidian_id is None:
                result.errors.append(f"Obsidian path {obs_path} not found for update")
                return

            # Update the Obsidian note
            update_data: dict[str, Any] = {"content": md_body, "title": item.title}
            self._obsidian.update_item(obsidian_id, update_data)
            result.updated += 1
            result.synced += 1
            logger.info("  UPDATED WPS→Obsidian: '%s'", item.title)

        elif change.type == ChangeType.DELETED:
            # WPS Note item was deleted — remove from Obsidian too
            obs_path = cast("str", self.id_map.get_obsidian_path(change.item_id))
            if obs_path:
                self._delete_obsidian_by_path(obs_path)
                self.id_map.remove(obs_path)
                result.deleted += 1
                result.synced += 1
                logger.info("  DELETED WPS→Obsidian: %s", obs_path)

    # ── Internal helpers ──────────────────────────────────────────

    def _get_item_path(self, item: KnowledgeArtifact) -> str:
        """Extract the relative vault path from an Obsidian Note.

        Uses the base64-encoded ID to decode the path.
        """
        import base64

        try:
            padded = item.id + "=" * (-len(item.id) % 4)
            rel_path = base64.urlsafe_b64decode(padded.encode()).decode()
            return rel_path
        except Exception:
            return getattr(item, "source_path", None) or item.id

    def _get_markdown_body(self, full_content: str) -> str:
        """Strip frontmatter and return just the markdown body."""
        from iris.base import strip_frontmatter

        return strip_frontmatter(full_content)

    def _find_obsidian_id_by_path(self, rel_path: str) -> str | None:
        """Find an Obsidian item ID by its relative vault path."""
        import base64

        try:
            encoded = base64.urlsafe_b64encode(rel_path.encode()).decode().rstrip("=")
            # Verify the item exists
            item = self._obsidian.get_item(encoded)
            if item is not None:
                return encoded
        except Exception:
            pass
        return None

    def _delete_obsidian_by_path(self, rel_path: str) -> bool:
        """Delete an Obsidian note by its relative vault path."""
        import base64

        try:
            encoded = base64.urlsafe_b64encode(rel_path.encode()).decode().rstrip("=")
            return self._obsidian.delete_item(encoded, soft=True)
        except Exception:
            return False
