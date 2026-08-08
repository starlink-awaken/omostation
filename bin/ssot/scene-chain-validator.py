#!/usr/bin/env python3
"""Validate scene card downstream_refs — check targets exist and detect cycles.

Reads all scene cards in docs/scene-cards/, builds a directed graph from
downstream_refs, and reports:
- Missing target scenes (downstream_refs pointing to non-existent scene_id)
- Circular dependencies (cycles in the chain graph)
- Chain topology summary (source/sink/intermediate nodes)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_scene_cards(cards_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all scene cards, keyed by scene_id."""
    import yaml

    cards: dict[str, dict[str, Any]] = {}
    for path in sorted(cards_dir.glob("*.yaml")) if cards_dir.is_dir() else []:
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            body = docs[-1] if docs else {}
            if isinstance(body, dict) and body.get("scene_id"):
                cards[body["scene_id"]] = body
        except Exception:
            continue
    return cards


def build_chain_graph(cards: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Build adjacency list: scene_id → [downstream scene_ids]."""
    graph: dict[str, list[str]] = {}
    for scene_id, card in cards.items():
        downstream = card.get("downstream_refs", [])
        targets = []
        for ref in downstream if isinstance(downstream, list) else []:
            if isinstance(ref, dict):
                target = ref.get("scene", "")
                if target:
                    targets.append(target)
        graph[scene_id] = targets
    return graph


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles using DFS with coloring (white/gray/black)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    cycles: list[list[str]] = []
    path: list[str] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        path.pop()
        color[node] = BLACK

    for node in sorted(graph):
        if color[node] == WHITE:
            dfs(node)
    return cycles


def validate(root: Path) -> dict[str, Any]:
    cards_dir = root / "docs" / "scene-cards"
    cards = _load_scene_cards(cards_dir)
    graph = build_chain_graph(cards)

    # Check for missing targets
    all_ids = set(cards.keys())
    missing: list[dict[str, str]] = []
    for source, targets in graph.items():
        for target in targets:
            if target not in all_ids:
                missing.append({"from": source, "to": target, "reason": "target scene_id not found"})

    # Detect cycles
    cycles = detect_cycles(graph)

    # Classify nodes
    has_incoming = set()
    for targets in graph.values():
        has_incoming.update(targets)
    sources = [n for n in graph if n not in has_incoming]
    sinks = [n for n, targets in graph.items() if not targets]
    intermediates = [n for n in graph if n in has_incoming and n not in sinks]

    return {
        "schema": "scene-chain-validation/v1",
        "total_scenes": len(cards),
        "total_edges": sum(len(t) for t in graph.values()),
        "missing_targets": missing,
        "cycles": cycles,
        "topology": {
            "sources": sorted(sources),
            "sinks": sorted(sinks),
            "intermediates": sorted(intermediates),
        },
        "graph": graph,
        "valid": len(missing) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = validate(args.root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Scene Chain Validation: {'✅ VALID' if result['valid'] else '❌ ISSUES FOUND'}")
        print(f"  Scenes: {result['total_scenes']}, Edges: {result['total_edges']}")
        print(f"  Sources: {', '.join(result['topology']['sources'])}")
        print(f"  Sinks: {', '.join(result['topology']['sinks'])}")
        if result["missing_targets"]:
            print(f"  Missing targets ({len(result['missing_targets'])}):")
            for m in result["missing_targets"]:
                print(f"    {m['from']} → {m['to']}: {m['reason']}")
        if result["cycles"]:
            print(f"  Feedback loops ({len(result['cycles'])}):")
            for c in result["cycles"]:
                print(f"    {' → '.join(c)}")
            print("  (feedback loops are architecturally valid — not blocking)")
        if not result["missing_targets"] and not result["cycles"]:
            print("  All downstream_refs resolve, no cycles.")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
