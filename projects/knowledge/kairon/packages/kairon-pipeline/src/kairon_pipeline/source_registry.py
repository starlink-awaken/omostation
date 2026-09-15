from __future__ import annotations

"""
Source registry for the D-Harvest pipeline.

Provides ``SourceRegistry`` which maps source IDs to their connection
details and provides a ``resolve`` method to fetch ``RawContent`` objects.
"""

from typing import Any

from kairon_pipeline.source_connectors import RawContent


class SourceRegistry:
    """Registry of known data sources for harvesting.

    Each source is keyed by a unique string identifier and holds
    connection metadata (URI, content type, auth, etc.).
    """

    def __init__(self) -> None:
        self._sources: dict[str, dict[str, Any]] = {}

    def register(self, source_id: str, config: dict[str, Any]) -> None:
        """Register a new source with *source_id* and *config*."""
        self._sources[source_id] = dict(config)

    def unregister(self, source_id: str) -> bool:
        """Remove a registered source.  Returns ``True`` if it existed."""
        return self._sources.pop(source_id, None) is not None

    def get(self, source_id: str) -> dict[str, Any] | None:
        """Return the config for a registered source, or ``None``."""
        return self._sources.get(source_id)

    def list_sources(self) -> list[str]:
        """Return all registered source IDs."""
        return list(self._sources.keys())

    async def resolve(self, source_id: str) -> RawContent:
        """Resolve a source ID into ``RawContent``.

        This is a stub that returns a placeholder.  TODO: implement actual
        HTTP / filesystem / DB fetching based on the source config.
        """
        config = self._sources.get(source_id, {})
        return RawContent(
            uri=config.get("uri", f"source://{source_id}"),
            data=config.get("data", f"Mock content for source '{source_id}'"),
            content_type=config.get("content_type", "text/plain"),
            metadata={
                "source_id": source_id,
                "config": config,
            },
        )
