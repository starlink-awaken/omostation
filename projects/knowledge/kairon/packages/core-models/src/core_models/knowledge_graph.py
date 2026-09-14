"""Alias module: re-exports KnowledgeGraph, GraphNode, GraphEdge for adapter compatibility.

Import path: from core_models.knowledge_graph import KnowledgeGraph, GraphNode, GraphEdge
"""

from __future__ import annotations

from core_models.models import Entity, KnowledgeGraph, Relation

# Type aliases — consumers use these as TYPE_HINTs.
GraphNode = Entity
GraphEdge = Relation

__all__ = ["KnowledgeGraph", "GraphNode", "GraphEdge"]
