"""Unified data models for all connector platforms.

Every piece of data from any platform is mapped to one of these types.
The KnowledgeArtifact base class provides eidos KnowledgeCard conversion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class KnowledgeArtifact:
    """Base class for all connector artifacts.

    Every artifact can be converted to an eidos KnowledgeCard
    for schema validation and cross-platform compatibility.
    """

    id: str = ""
    title: str = ""
    platform: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (for JSON output, eidos validation)."""
        return asdict(self)

    def to_knowledge_card(self) -> dict[str, Any]:
        """Convert to eidos KnowledgeCard-compatible dict.

        Subclasses should override to provide platform-specific mapping.
        Returns a dict matching eidos KnowledgeCard schema:
          id, title, content, source, source_type, schema_type,
          tags, relations, created_at, updated_at
        """
        return {
            "id": f"{self.platform}/{self.id}",
            "title": self.title,
            "content": "",
            "source": self.platform,
            "source_type": self.platform,
            "schema_type": "KnowledgeCard",
            "tags": [],
            "relations": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Note(KnowledgeArtifact):
    """A note from any platform (WPS Note, Obsidian, NotebookLM)."""

    content: str = ""
    tags: list[str] = field(default_factory=list)
    source_path: str = ""
    platform_notebook: str = ""

    def to_knowledge_card(self) -> dict[str, Any]:
        return {
            "id": f"{self.platform}/{self.id}",
            "title": self.title,
            "content": self.content,
            "source": self.source_path or self.platform,
            "source_type": self.platform,
            "schema_type": "KnowledgeCard",
            "tags": self.tags,
            "relations": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Highlight(KnowledgeArtifact):
    """A highlight or annotation (WeChat Read, Zhihu favorites)."""

    text: str = ""
    source_url: str = ""
    chapter: str = ""
    annotation: str = ""

    def to_knowledge_card(self) -> dict[str, Any]:
        content = self.text
        if self.annotation:
            content += f"\n\n---\nNote: {self.annotation}"
        return {
            "id": f"{self.platform}/highlight/{self.id}",
            "title": self.title or f"Highlight from {self.source_url[:50]}",
            "content": content,
            "source": self.source_url or self.platform,
            "source_type": f"{self.platform}_highlight",
            "schema_type": "KnowledgeCard",
            "tags": ["highlight", f"platform:{self.platform}"],
            "relations": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Article(KnowledgeArtifact):
    """An article (Zhihu column, WeChat official account)."""

    content: str = ""
    url: str = ""
    author: str = ""
    summary: str = ""

    def to_knowledge_card(self) -> dict[str, Any]:
        card_content = self.summary or self.content[:500] if self.content else ""
        return {
            "id": f"{self.platform}/article/{self.id}",
            "title": self.title,
            "content": card_content,
            "source": self.url or self.platform,
            "source_type": f"{self.platform}_article",
            "schema_type": "KnowledgeCard",
            "tags": ["article", f"platform:{self.platform}"],
            "relations": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Bookmark(KnowledgeArtifact):
    """A bookmark or saved link."""

    url: str = ""
    description: str = ""

    def to_knowledge_card(self) -> dict[str, Any]:
        return {
            "id": f"bookmark/{self.id}",
            "title": self.title,
            "content": self.description or self.url,
            "source": self.url or self.platform,
            "source_type": "bookmark",
            "schema_type": "KnowledgeCard",
            "tags": ["bookmark", f"platform:{self.platform}"],
            "relations": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SyncState:
    """Sync state for a connector."""

    connector_name: str
    last_sync_at: str = ""
    item_count: int = 0
    status: str = "idle"
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
