from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Must expose NKS capabilities via MCP protocol"
Summary: "NKSMCPBridge - MCP protocol bridge for NKS"
Tags:
- nks
- mcp
- gateway
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Nks Mcp Bridge ≡ Module
# 内涵 ≝ {Nks, Mcp, Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, NksMcpBridge)}
# 功能 ⊢ {Nks_Mcp, Mcp_Bridge, Bridge_Init}
# =============================================================================

import importlib
import logging
from pathlib import Path as P  # noqa: N817
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from eidos.organs.nks.graph_store import Entity, GraphStore
    from eidos.organs.nks.impact_analyzer import ImpactAnalyzer
    from eidos.organs.nks.query_engine import GraphQueryEngine


def _lazy_nks_imports() -> tuple[Any | None, Any | None, Any | None, Any | None]:
    """Lazy import to avoid cross-organ coupling with D-Memory."""
    try:
        graph_store_module = importlib.import_module("organs.D_Memory.organs.nks.graph_store")
        impact_analyzer_module = importlib.import_module("organs.D_Memory.organs.nks.impact_analyzer")
        query_engine_module = importlib.import_module("organs.D_Memory.organs.nks.query_engine")
        GraphStore = graph_store_module.GraphStore  # noqa: N806
        Entity = graph_store_module.Entity  # noqa: N806
        ImpactAnalyzer = impact_analyzer_module.ImpactAnalyzer  # noqa: N806
        GraphQueryEngine = query_engine_module.GraphQueryEngine  # noqa: N806
        return GraphStore, Entity, GraphQueryEngine, ImpactAnalyzer
    except (ImportError, ModuleNotFoundError, AttributeError) as exc:
        _log.warning("NKS core modules unavailable via canonical import path: %s", exc)
        return None, None, None, None


class NKSMCPBridge:
    """
    NKSMCPBridge - MCP Protocol Bridge for NKS (Neural Knowledge System)

    Exposes NKS capabilities via Model Context Protocol (MCP) for Agent integration.
    Provides 5 core tools for knowledge graph exploration:
    - nks_query_entity: Search for entities by name pattern
    - nks_get_call_graph: Get call graph for functions
    - nks_analyze_change_impact: Analyze impact of code changes
    - nks_get_file_architecture: Get file architecture summary
    - nks_find_related_entities: Find related entities

    All tools return JSON-serializable results for MCP compatibility.
    """

    def __init__(
        self,
        graph_store: GraphStore | None = None,
        query_engine: GraphQueryEngine | None = None,
        impact_analyzer: ImpactAnalyzer | None = None,
    ) -> None:
        """
        Initialize NKSMCPBridge.

        Args:
            graph_store: GraphStore instance (optional)
            query_engine: GraphQueryEngine instance (optional)
            impact_analyzer: ImpactAnalyzer instance (optional)
        """
        self.status = "active"

        # Initialize or store components
        self._graph_store = graph_store
        self._query_engine = query_engine
        self._impact_analyzer = impact_analyzer

        # Lazy initialization tracking
        self._initialized = False

    @staticmethod
    def _deduct_metabolic_tax(amount: float) -> None:
        """Deduct metabolic tax for resource accounting (stub)."""
        _log.debug("Metabolic tax deducted: %s", amount)

    @staticmethod
    def _constraint_check(operation: str) -> None:
        """Check operational constraints (stub)."""
        _log.debug("Constraint checked for: %s", operation)

    def _ensure_initialized(self) -> None:
        """Lazy initialization of NKS components."""
        if self._initialized:
            return

        GraphStore, _Entity, GraphQueryEngine, ImpactAnalyzer = _lazy_nks_imports()  # noqa: N806

        # Initialize GraphStore if not provided
        if self._graph_store is None:
            if GraphStore is None:
                _log.error("Cannot initialize NKS bridge: GraphStore unavailable")
                return
            root_path = P(__file__).parent.parent.parent.parent
            db_path = root_path / "organs" / "D-Memory" / "data" / "nks_graph.db"
            self._graph_store = GraphStore(str(db_path))

        # Initialize QueryEngine if not provided
        if self._query_engine is None:
            if GraphQueryEngine is None:
                _log.error("Cannot initialize NKS bridge: GraphQueryEngine unavailable")
                return
            self._query_engine = GraphQueryEngine(self._graph_store)

        # Initialize ImpactAnalyzer if not provided
        if self._impact_analyzer is None:
            if ImpactAnalyzer is None:
                _log.error("Cannot initialize NKS bridge: ImpactAnalyzer unavailable")
                return
            self._impact_analyzer = ImpactAnalyzer(graph_store=self._graph_store)

        self._initialized = True

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get MCP tool definitions for all available tools.

        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "nks_query_entity",
                "description": "Search for entities in the knowledge graph by name pattern. Supports SQL LIKE patterns (e.g., '%user%' to match any entity containing 'user').",
                "parameters": {
                    "name_pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern for entity name matching (e.g., 'get_%', '%user%')",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Optional entity type filter (e.g., 'function', 'class', 'module')",
                        "default": None,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10,
                    },
                },
            },
            {
                "name": "nks_get_call_graph",
                "description": "Get the call graph for a function entity. Returns callers (upstream) and/or callees (downstream) up to specified depth.",
                "parameters": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function entity to analyze",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How many levels to traverse",
                        "default": 3,
                    },
                    "direction": {
                        "type": "string",
                        "description": "Direction to traverse: 'upstream' (callers), 'downstream' (callees), or 'both'",
                        "default": "both",
                        "enum": ["upstream", "downstream", "both"],
                    },
                },
            },
            {
                "name": "nks_analyze_change_impact",
                "description": "Analyze the impact of code changes. Returns risk score, affected entities, dependency chains, and suggested test files.",
                "parameters": {
                    "changed_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths that were changed",
                    },
                    "change_description": {
                        "type": "string",
                        "description": "Description of the changes (for context)",
                        "default": "",
                    },
                },
            },
            {
                "name": "nks_get_file_architecture",
                "description": "Get architecture summary for a source file including entities, relations, and connectivity metrics.",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file (relative to project root)",
                    },
                },
            },
            {
                "name": "nks_find_related_entities",
                "description": "Find entities related to a given entity through specified relation types.",
                "parameters": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the entity to find relations for",
                    },
                    "relation_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of relation types to filter (e.g., ['calls', 'imports', 'inherits'])",
                        "default": None,
                    },
                },
            },
        ]

    def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an MCP tool by name.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters dictionary

        Returns:
            Tool execution result as dictionary
        """
        self._ensure_initialized()
        self._constraint_check(f"mcp_tool:{tool_name}")

        handlers = {
            "nks_query_entity": self._handle_query_entity,
            "nks_get_call_graph": self._handle_get_call_graph,
            "nks_analyze_change_impact": self._handle_analyze_change_impact,
            "nks_get_file_architecture": self._handle_get_file_architecture,
            "nks_find_related_entities": self._handle_find_related_entities,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {
                "status": "error",
                "message": f"Unknown tool: {tool_name}",
            }

        try:
            result = handler(parameters)
            self._deduct_metabolic_tax(amount=0.5)
            return result
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            self._deduct_metabolic_tax(amount=0.1)
            return {
                "status": "error",
                "message": f"Tool execution failed: {str(e)}",
            }

    def _entity_to_dict(self, entity: Entity) -> dict[str, Any]:
        """Convert Entity to dictionary."""
        return {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "type": entity.properties.get("type", "unknown"),
            "properties": entity.properties,
            "source_files": entity.source_files,
            "is_canonical": entity.is_canonical,
        }

    def _handle_query_entity(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Handle nks_query_entity tool.

        Parameters:
            - name_pattern: SQL LIKE pattern
            - entity_type: Optional type filter
            - limit: Maximum results (default 10)
        """
        name_pattern = parameters.get("name_pattern", "%")
        entity_type = parameters.get("entity_type")
        limit = parameters.get("limit", 10)

        # Build property filter for entity type
        property_filter = None
        if entity_type:
            property_filter = {"type": entity_type}

        # Search entities
        gs = self._graph_store
        if gs is None:
            return {"status": "error", "message": "GraphStore not initialized"}
        entities = gs.search_entities(
            name_pattern=name_pattern,
            property_filter=property_filter,
            limit=limit,
        )

        return {
            "status": "success",
            "count": len(entities),
            "entities": [self._entity_to_dict(e) for e in entities],
        }

    def _handle_get_call_graph(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Handle nks_get_call_graph tool.

        Parameters:
            - function_name: Function entity name
            - depth: Traversal depth (default 3)
            - direction: 'upstream', 'downstream', or 'both'
        """
        function_name = parameters.get("function_name")
        depth = parameters.get("depth", 3)
        direction = parameters.get("direction", "both")

        if not function_name:
            return {"status": "error", "message": "function_name is required"}

        # Map direction to query engine format
        query_direction = direction
        if direction == "upstream":
            query_direction = "incoming"
        elif direction == "downstream":
            query_direction = "outgoing"

        # Find the function entity
        gs = self._graph_store
        if gs is None:
            return {"status": "error", "message": "GraphStore not initialized"}
        function_entity = gs.find_entity_by_name(function_name)
        if not function_entity:
            return {
                "status": "error",
                "message": f"Function not found: {function_name}",
            }

        # Get call graph
        try:
            qe = self._query_engine
            if qe is None:
                return {"status": "error", "message": "QueryEngine not initialized"}
            graph = qe.get_call_graph(
                function_id=function_entity.entity_id,
                depth=depth,
                direction=query_direction,
            )
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        # Convert graph to serializable format
        nodes = {}
        for node_id, node in graph.items():
            nodes[node_id] = {
                "entity_id": node_id,
                "name": node.entity.name,
                "type": node.entity.properties.get("type", "unknown"),
                "depth": node.depth,
                "callers": node.callers,
                "callees": node.callees,
            }

        return {
            "status": "success",
            "center_function": function_name,
            "node_count": len(nodes),
            "nodes": nodes,
        }

    def _handle_analyze_change_impact(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Handle nks_analyze_change_impact tool.

        Parameters:
            - changed_files: List of file paths
            - change_description: Optional description
        """
        changed_files = parameters.get("changed_files", [])
        change_description = parameters.get("change_description", "")

        if not changed_files:
            return {"status": "error", "message": "changed_files is required"}

        # Collect all impacted entities from all changed files
        all_changed_entities: list[Entity] = []
        all_direct_impacts: list[Entity] = []
        all_transitive_impacts: list[Entity] = []
        all_suggested_tests: set[str] = set()
        all_dependency_chains: list[list[str]] = []
        max_risk_score = 0.0

        for file_path in changed_files:
            try:
                ia = self._impact_analyzer
                if ia is None:
                    return {"status": "error", "message": "ImpactAnalyzer not initialized"}
                report = ia.analyze_file_change(file_path, "modify")

                # Merge results
                all_changed_entities.extend(report.changed_entities)
                all_direct_impacts.extend(report.direct_impacts)
                all_transitive_impacts.extend(report.transitive_impacts)
                all_suggested_tests.update(report.suggested_tests)
                all_dependency_chains.extend(report.dependency_chains)
                max_risk_score = max(max_risk_score, report.risk_score)

            except (OSError, TypeError, ValueError, AttributeError):
                # Log but continue with other files
                continue

        # Deduplicate entities
        changed_ids = {e.entity_id: e for e in all_changed_entities}
        direct_ids = {e.entity_id: e for e in all_direct_impacts}
        transitive_ids = {e.entity_id: e for e in all_transitive_impacts}

        # Remove overlaps
        for eid in changed_ids:
            direct_ids.pop(eid, None)
            transitive_ids.pop(eid, None)
        for eid in direct_ids:
            transitive_ids.pop(eid, None)

        # Determine risk level
        risk_level = "MINIMAL"
        if max_risk_score >= 0.8:
            risk_level = "CRITICAL"
        elif max_risk_score >= 0.6:
            risk_level = "HIGH"
        elif max_risk_score >= 0.4:
            risk_level = "MEDIUM"
        elif max_risk_score >= 0.2:
            risk_level = "LOW"

        return {
            "status": "success",
            "summary": {
                "changed_files": changed_files,
                "change_description": change_description,
                "risk_score": round(max_risk_score, 4),
                "risk_level": risk_level,
            },
            "impact": {
                "changed_entities": [self._entity_to_dict(e) for e in changed_ids.values()],
                "direct_impacts": [self._entity_to_dict(e) for e in direct_ids.values()],
                "transitive_impacts": [self._entity_to_dict(e) for e in transitive_ids.values()],
            },
            "counts": {
                "changed": len(changed_ids),
                "direct": len(direct_ids),
                "transitive": len(transitive_ids),
                "total_impact": len(direct_ids) + len(transitive_ids),
            },
            "suggested_tests": sorted(all_suggested_tests),
            "dependency_chains": all_dependency_chains[:10],  # Limit chains
        }

    def _handle_get_file_architecture(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Handle nks_get_file_architecture tool.

        Parameters:
            - file_path: Path to source file
        """
        file_path = parameters.get("file_path", "")

        if not file_path:
            return {"status": "error", "message": "file_path is required"}

        # Find candidate entities for this file
        gs = self._graph_store
        if gs is None:
            return {"status": "error", "message": "GraphStore not initialized"}
        candidates = gs.get_candidate_entities(source_file=file_path)

        if not candidates:
            return {
                "status": "success",
                "file_path": file_path,
                "message": "No entities found for this file",
                "entities": [],
                "relations": [],
                "metrics": {},
            }

        # Get canonical entities that originated from this file
        canonical_entities: list[Entity] = []
        for candidate in candidates:
            # Try to find canonical version
            canonical = gs.find_entity_by_name(candidate.name)
            if canonical and canonical.is_canonical:
                canonical_entities.append(canonical)

        # Collect all relations for these entities
        all_relations = []
        entity_ids = {e.entity_id for e in canonical_entities}

        for entity in canonical_entities:
            relations = gs.get_relations_for_entity(entity.entity_id, direction="both")
            for rel in relations:
                all_relations.append(
                    {
                        "relation_id": rel.relation_id,
                        "source_id": rel.source_id,
                        "target_id": rel.target_id,
                        "relation_type": rel.relation_type,
                        "confidence": rel.confidence,
                    }
                )

        # Calculate metrics
        incoming_count = sum(
            1 for r in all_relations if r["target_id"] in entity_ids and r["source_id"] not in entity_ids
        )
        outgoing_count = sum(
            1 for r in all_relations if r["source_id"] in entity_ids and r["target_id"] not in entity_ids
        )
        internal_count = sum(1 for r in all_relations if r["source_id"] in entity_ids and r["target_id"] in entity_ids)

        # Get entry points (no incoming from outside)
        entry_points = []
        for entity in canonical_entities:
            incoming_external = [
                r for r in all_relations if r["target_id"] == entity.entity_id and r["source_id"] not in entity_ids
            ]
            if not incoming_external:
                entry_points.append(entity.name)

        return {
            "status": "success",
            "file_path": file_path,
            "entities": [self._entity_to_dict(e) for e in canonical_entities],
            "entity_count": len(canonical_entities),
            "relations": all_relations,
            "relation_count": len(all_relations),
            "metrics": {
                "incoming_relations": incoming_count,
                "outgoing_relations": outgoing_count,
                "internal_relations": internal_count,
                "entry_points": entry_points,
                "entry_point_count": len(entry_points),
            },
        }

    def _handle_find_related_entities(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Handle nks_find_related_entities tool.

        Parameters:
            - entity_name: Entity name to find relations for
            - relation_types: Optional list of relation types
        """
        entity_name = parameters.get("entity_name", "")
        relation_types = parameters.get("relation_types")

        if not entity_name:
            return {"status": "error", "message": "entity_name is required"}

        # Find the entity
        gs = self._graph_store
        if gs is None:
            return {"status": "error", "message": "GraphStore not initialized"}
        entity = gs.find_entity_by_name(entity_name)
        if not entity:
            return {
                "status": "error",
                "message": f"Entity not found: {entity_name}",
            }

        # Get neighbors using query engine
        try:
            qe = self._query_engine
            if qe is None:
                return {"status": "error", "message": "QueryEngine not initialized"}
            neighbors = qe.get_neighbors(
                entity_id=entity.entity_id,
                direction="both",
                relation_types=relation_types,
            )
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        # Group by relation type
        by_relation: dict[str, list[dict[str, Any]]] = {}
        related_entities = []

        for neighbor_entity, relation in neighbors:
            relation_info = {
                "entity": self._entity_to_dict(neighbor_entity),
                "relation": {
                    "relation_id": relation.relation_id,
                    "relation_type": relation.relation_type,
                    "confidence": relation.confidence,
                    "direction": "outgoing" if relation.source_id == entity.entity_id else "incoming",
                },
            }
            related_entities.append(relation_info)

            # Group by type
            rel_type = relation.relation_type
            if rel_type not in by_relation:
                by_relation[rel_type] = []
            by_relation[rel_type].append(
                {
                    "name": neighbor_entity.name,
                    "type": neighbor_entity.properties.get("type", "unknown"),
                    "direction": relation_info["relation"]["direction"],
                }
            )

        return {
            "status": "success",
            "entity": self._entity_to_dict(entity),
            "related_count": len(related_entities),
            "related_entities": related_entities,
            "grouped_by_relation": by_relation,
        }

    def ping(self) -> bool:
        """
        Health check for NKSMCPBridge.

        Returns:
            True if all components are healthy
        """
        try:
            self._ensure_initialized()
            store_ok = self._graph_store.ping() if self._graph_store else False
            engine_ok = self._query_engine.ping() if self._query_engine else False
            analyzer_ok = self._impact_analyzer.ping() if self._impact_analyzer else False
            return store_ok and engine_ok and analyzer_ok
        except (OSError, ConnectionError, AttributeError):
            return False

    def _handle_mcp_list_tools(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle MCP list_tools request."""
        return {
            "status": "success",
            "tools": self.get_tool_definitions(),
        }

    def _handle_mcp_call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle MCP call_tool request."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        return self.execute_tool(tool_name, arguments)
