"""Fact graph organ — in-memory fact graph with simple query interface.

Provides basic fact graph with SQLite persistence support.
"""

from __future__ import annotations

from ..fact_graph import FactGraph, get_fact_graph


def get_graph() -> FactGraph:
    """Return the singleton FactGraph instance."""
    return get_fact_graph()


__all__ = [
    "FactGraph",
    "get_graph",
    "get_fact_graph",
]
