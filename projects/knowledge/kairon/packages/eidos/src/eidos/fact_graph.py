"""Fact graph — an in-memory graph of atomic facts.

Provides basic fact storage and retrieval. Advanced features (persistence,
complex querying, graph algorithms) are planned for future enhancement.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


class FactGraph:
    """In-memory fact graph for atomic fact storage and querying."""

    def __init__(self) -> None:
        self._facts: list[dict[str, Any]] = []

    def query(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Query facts from the graph."""
        return self._facts

    def _get_connection(self) -> Any:
        """Get a DB connection stub (context manager)."""
        return nullcontext()

    def add_fact(self, fact: dict[str, Any]) -> None:
        """Add a fact to the graph."""
        self._facts.append(fact)


def get_graph() -> FactGraph:
    """Return the singleton FactGraph instance."""
    return FactGraph()


def get_fact_graph() -> FactGraph:
    """Return the singleton FactGraph instance (alias)."""
    return FactGraph()


__all__ = [
    "FactGraph",
    "get_graph",
    "get_fact_graph",
]
