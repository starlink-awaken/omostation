"""Connector registry — auto-discovers and manages all connectors."""

from __future__ import annotations

from typing import Any

from iris.base import BaseConnector


class ConnectorRegistry:
    """Registry for all platform connectors.

    Connectors register themselves by name. The registry provides
    lookup, listing, and batch operations.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        """Register a connector instance."""
        if not connector.name:
            raise ValueError("Connector must have a non-empty name")
        self._connectors[connector.name] = connector

    def get(self, name: str) -> BaseConnector | None:
        """Get connector by name."""
        return self._connectors.get(name)

    def list_all(self) -> list[BaseConnector]:
        """List all registered connectors."""
        return list(self._connectors.values())

    def list_names(self) -> list[str]:
        """List all registered connector names."""
        return list(self._connectors.keys())

    def unregister(self, name: str) -> None:
        """Remove a connector from the registry."""
        self._connectors.pop(name, None)

    def status_all(self) -> list[dict[str, Any]]:
        """Get status dict for all connectors."""
        results = []
        for name, conn in self._connectors.items():
            try:
                available = conn.is_available()
                s = conn.status()
                results.append(
                    {
                        "name": conn.name,
                        "display_name": conn.display_name,
                        "available": available,
                        **s,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "name": name,
                        "display_name": getattr(conn, "display_name", name),
                        "available": False,
                        "error": str(e),
                    }
                )
        return results

    def __len__(self) -> int:
        return len(self._connectors)

    def __contains__(self, name: str) -> bool:
        return name in self._connectors
