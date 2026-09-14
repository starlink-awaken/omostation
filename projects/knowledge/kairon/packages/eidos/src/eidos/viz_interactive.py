"""Interactive graph exploration — explore ontology types interactively.

Usage:
    from eidos.viz_interactive import explore
    explore("domain")  # Interactive exploration prompt
"""

from __future__ import annotations

from typing import Any


def explore(meta_type: str = "") -> None:
    """Interactive ontology graph exploration.

    Shows nodes and edges for a given meta_type, lets user drill down.
    """
    from eidos.meta import list_types
    from eidos.viz import render

    types = list_types()
    nodes = []
    edges: list[dict[str, Any]] = []

    for t in types:
        if not meta_type or t["meta_type"] == meta_type:
            nodes.append({"id": t["type_name"], "label": t["type_name"], "type": t["meta_type"]})

    if not nodes:
        print(f"No types found for meta_type: {meta_type}")
        return

    print(f"Found {len(nodes)} types for meta_type='{meta_type}'")
    print()
    print(render("graph", nodes=nodes, edges=edges, title=meta_type))
    print()
    print("Drill down: eidos viz schema <TypeName>")


def kos_path() -> str:
    """Get the KOS CLI path."""
    import os
    from pathlib import Path

    return str(Path(os.path.expanduser("~/Workspace/kos/kos-cli.py")))
