"""Abstract base connector and sync result types.

Every platform connector implements the BaseConnector interface.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from iris.models import KnowledgeArtifact


@dataclass
class SyncResult:
    """Result of a sync operation."""

    connector_name: str
    items_found: int = 0
    success: bool = True
    errors: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "items_found": self.items_found,
            "success": self.success,
            "errors": self.errors,
            "message": self.message,
        }


class BaseConnector(ABC):
    """Abstract base class for all platform connectors.

    Each connector implements read operations for its platform.
    Write/sync capabilities are added in V0.2.
    """

    name: str = ""
    display_name: str = ""
    connection_kind: str = "knowledge_source"
    protocol: str = "iris.connector.v1"
    capabilities: tuple[str, ...] = ("discover", "search", "read")
    data_classification: str = "private"

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this connector can operate (auth, deps, paths exist)."""
        ...

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> Sequence[KnowledgeArtifact]:
        """List items from the platform, with optional pagination.

        Override in platform-specific connectors. Default returns empty list.
        The extra keyword params (tag, folder, subdir, chat_id) are
        connector-specific and ignored by connectors that don't support them.
        """
        return []

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        """Get a single item by its platform ID.

        Override in platform-specific connectors. Default returns None.
        """
        return None

    def search(self, query: str, limit: int = 10) -> Sequence[KnowledgeArtifact]:
        """Search platform content by query string.

        Override in platform-specific connectors. Default returns empty list.
        """
        return []

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Return connector health/configuration/count status."""
        ...

    def external_descriptor(self) -> dict[str, Any]:
        """Expose a credential-free descriptor for the External Connection Fabric."""
        try:
            available = bool(self.is_available())
        except Exception as exc:  # pragma: no cover - defensive boundary for third-party adapters
            available = False
            availability_error = type(exc).__name__
        else:
            availability_error = None

        try:
            health = self.status()
        except Exception as exc:  # pragma: no cover - defensive boundary for third-party adapters
            health = {"error": type(exc).__name__}

        if availability_error:
            health = {**health, "availability_error": availability_error}

        return {
            "id": f"iris:{self.name}",
            "kind": self.connection_kind,
            "provider": self.name,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "data_classification": self.data_classification,
            "provenance": {"adapter": "kairon.iris", "connector": self.name},
            "lifecycle": "active" if available else "degraded",
            "health": {"available": available, "details": health},
            "owner": "kairon.iris",
            "version": "1",
            # This is an opaque reference, never a credential value. The
            # scene admission layer must still match it to an operator grant.
            "permission_ref": f"credential://iris/{self.name}",
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Pull latest data from platform (default: unsupported message)."""
        return SyncResult(
            connector_name=self.name,
            success=False,
            message="Sync not yet implemented for this connector (V0.2).",
        )

    def create_item(self, **kwargs: Any) -> Any:
        """Create a new item on the platform.

        Subclasses that support write operations should override this.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support create_item")

    def delete_item(self, item_id: str, **kwargs: Any) -> bool:
        """Delete an item from the platform by ID.

        Subclasses that support write operations should override this.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support delete_item")

    def update_item(self, item_id: str, data: dict[str, Any]) -> Any:
        """Update an existing item on the platform.

        Subclasses that support write operations should override this.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support update_item")

    def export(self, fmt: str = "json") -> str:
        """Export connector data in specified format."""
        items = self.list_items(limit=1000)
        if fmt == "json":
            import json

            return json.dumps(
                [item.to_dict() for item in items],
                ensure_ascii=False,
                indent=2,
            )
        if fmt == "md":
            lines = [f"# {self.display_name} Export\n"]
            for item in items:
                title = item.title or "Untitled"
                lines.append(f"## {title}")
                raw = item.to_dict()
                content = raw.get("content", "") or ""
                if content:
                    lines.append(content)
                lines.append("")
            return "\n".join(lines)
        raise ValueError(f"Unsupported format: {fmt}")


# ── Shared utilities ──────────────────────────────────────────────


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract frontmatter fields from markdown content.

    Returns dict with 'tags', 'created', 'aliases', 'title', and raw string.
    """
    result: dict[str, Any] = {"tags": [], "created": "", "aliases": [], "title": ""}
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return result

    fm = fm_match.group(1)
    result["raw"] = fm

    tag_match = re.search(r"tags:\s*\[(.*?)\]", fm)
    if tag_match:
        result["tags"] = [t.strip().strip("\"'") for t in tag_match.group(1).split(",")]
    else:
        block_match = re.search(r"tags:\s*\n((?:\s+-\s+.*\n?)+)", fm)
        if block_match:
            result["tags"] = [t.strip().lstrip("- ") for t in block_match.group(1).split("\n") if t.strip()]

    for key in ("created", "date", "created_at"):
        date_match = re.search(rf"{key}:\s*['\"]?(\d{{4}}-\d{{2}}-\d{{2}})", fm)
        if date_match:
            result["created"] = date_match.group(1)
            break

    alias_match = re.search(r"aliases:\s*\[(.*?)\]", fm)
    if alias_match:
        result["aliases"] = [a.strip().strip("\"'") for a in alias_match.group(1).split(",")]
    else:
        block_match = re.search(r"aliases:\s*\n((?:\s+-\s+.*\n?)+)", fm)
        if block_match:
            result["aliases"] = [a.strip().lstrip("- ") for a in block_match.group(1).split("\n") if a.strip()]

    title_match = re.search(r"^title:\s*(.+)$", fm, re.MULTILINE)
    if title_match:
        result["title"] = title_match.group(1).strip().strip("\"'")

    return result


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from content."""
    return re.sub(r"^---\n.*?\n---\n*", "", content, flags=re.DOTALL)
