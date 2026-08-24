#!/usr/bin/env python3
"""search — query the knowledge graph by keyword or reference.

Phase 2 of the Knowledge Indexing plan.

Usage:
  python3 bin/kb/search.py "drift"                        # keyword search
  python3 bin/kb/search.py --refs bin/gac/drift-sweep.py   # reverse lookup
  python3 bin/kb/search.py --type adr "concurrent"        # filter by type
  python3 bin/kb/search.py --json "drift"                  # JSON output
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
GRAPH_PATH = WORKSPACE / ".kb" / "graph.json"


def _load_graph(path: Path = GRAPH_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"nodes": [], "edges": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"nodes": [], "edges": []}


def _keyword_search(graph: dict, query: str, node_type: str | None = None) -> list[dict]:
    """Rank nodes by keyword match: title/name > docstring/description > path."""
    q = query.lower()
    scored: list[tuple[int, dict]] = []
    for n in graph.get("nodes", []):
        if node_type and n.get("type") != node_type:
            continue
        score = 0
        # Title / name / id exact substring
        for field in ("title", "name", "id"):
            val = str(n.get(field, "")).lower()
            if q in val:
                score += 10 if field in ("title", "name") else 5
                break
        # Description / docstring
        for field in ("description", "docstring"):
            val = str(n.get(field, "")).lower()
            if q in val:
                score += 3
                break
        # Path
        if q in n.get("path", "").lower():
            score += 1
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [n for _, n in scored]


def _ref_search(graph: dict, ref_path: str) -> list[dict]:
    """Find all nodes that reference the given script path."""
    results = []
    ref_lower = ref_path.lower()
    # Build lookup by both plain id and prefixed id
    node_by_id: dict[str, dict] = {}
    for n in graph.get("nodes", []):
        node_by_id[n.get("id", "")] = n
        nid = n.get("id", "")
        ntype = n.get("type", "")
        if nid and not nid.startswith(f"{ntype}:"):
            node_by_id[f"{ntype}:{nid}"] = n
    for e in graph.get("edges", []):
        target = str(e.get("to", "")).lower()
        if ref_lower in target:
            src_id = e["from"]
            src_node = node_by_id.get(src_id)
            if src_node:
                results.append({
                    "node": src_node,
                    "relation": e.get("relation", ""),
                })
            else:
                results.append({"node": {"id": src_id, "type": "unknown"}, "relation": e.get("relation", "")})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument("--refs", help="Reverse lookup: find nodes referencing this script")
    parser.add_argument("--type", dest="node_type", help="Filter by node type (adr/script/runbook/skill/doc/scene-card)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--graph", type=Path, default=GRAPH_PATH, help="Graph file path")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    args = parser.parse_args(argv)

    graph = _load_graph(args.graph)
    if not graph.get("nodes"):
        print("No knowledge graph found. Run: python3 bin/kb/knowledge-graph.py")
        return 1

    if args.refs:
        results = _ref_search(graph, args.refs)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"Nodes referencing {args.refs}: {len(results)}")
            for r in results[:args.limit]:
                n = r["node"]
                print(f"  [{n['type']}] {n['id']} — {n.get('title', '')[:60]} ({r['relation']})")
        return 0

    if not args.query:
        parser.print_help()
        return 1

    results = _keyword_search(graph, args.query, args.node_type)
    limited = results[:args.limit]

    if args.json:
        print(json.dumps(limited, ensure_ascii=False, indent=2))
    else:
        print(f"Search '{args.query}': {len(results)} results (showing {len(limited)})")
        for n in limited:
            title = n.get("title") or n.get("docstring") or n.get("description") or ""
            print(f"  [{n['type']:<10}] {n['id']:<40} {title[:50]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())