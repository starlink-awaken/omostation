"""Knowledge Graph API — Neo4j graph data accessor for visualization."""

from __future__ import annotations

import asyncio
import os
from typing import Any


class GraphDataAccessor:
    """Fetch nodes and edges from Neo4j for D3.js visualization."""

    def __init__(self, uri: str = "", user: str = "neo4j", password: str = "") -> None:
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user
        self.password = password or os.environ.get("NEO4J_PASSWORD", "changeme")
        self._driver = None
        import atexit

        atexit.register(self.close)

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase  # type: ignore[reportMissingImports]

                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            except ImportError:
                return None
            except Exception:
                return None
        return self._driver

    async def get_graph_data(self, limit: int = 50) -> dict:
        """Fetch graph nodes and relationships for visualization.

        Returns: {"nodes": [...], "edges": [...]}
        """
        driver = self._get_driver()
        if driver is None:
            return {"nodes": [], "edges": [], "error": "Neo4j unavailable"}

        try:
            nodes, edges = await asyncio.to_thread(self._query_neo4j, driver, limit)
            return {"nodes": nodes, "edges": edges}
        except Exception:
            return {"nodes": [], "edges": [], "error": "Query failed"}

    def _query_neo4j(self, driver: Any, limit: int) -> tuple[list, list]:
        with driver.session() as session:
            node_result = session.run(
                "MATCH (n) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props LIMIT $limit",
                limit=limit,
            )
            nodes = []
            node_ids = set()
            for record in node_result:
                nid = str(record["id"])
                node_ids.add(nid)
                labels = record["labels"]
                props = record["props"] or {}
                name = props.get("name", props.get("title", labels[0] if labels else "Node"))
                nodes.append(
                    {
                        "id": nid,
                        "name": str(name)[:80],
                        "type": labels[0] if labels else "Unknown",
                        "color": _node_color(labels[0] if labels else ""),
                    }
                )

            edge_result = session.run(
                "MATCH (a)-[r]->(b) RETURN id(a) AS source, id(b) AS target, type(r) AS rel_type LIMIT $limit",
                limit=limit * 2,
            )
            edges = []
            for record in edge_result:
                src = str(record["source"])
                tgt = str(record["target"])
                if src in node_ids and tgt in node_ids:
                    edges.append(
                        {
                            "source": src,
                            "target": tgt,
                            "label": record["rel_type"],
                        }
                    )

            return nodes, edges


def _node_color(label: str) -> str:
    """Assign colors by node type."""
    colors = {
        "Entity": "#f5a623",
        "Concept": "#60a5fa",
        "Source": "#22c55e",
        "Person": "#ef4444",
        "Organization": "#a78bfa",
        "Topic": "#38bdf8",
        "Document": "#fb923c",
    }
    return colors.get(label, "#71717a")


# Singleton for /api/graph endpoint
graph_accessor = GraphDataAccessor()
