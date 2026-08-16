"""Graphify bridge adapter — wraps graphify Python API for Minerva knowledge graph."""


def build_code_graph(repo_path: str = ".") -> dict:
    """Build a code knowledge graph using graphify and return entities + relations.

    Uses graphify v0.7.10+ Python API. Falls back gracefully if graphify is not installed.
    """
    try:
        import graphify  # noqa: F401  # type: ignore[reportMissingImports]
        from graphify.analyze import analyze_repo  # type: ignore[reportMissingImports]
        from graphify.extract import extract_symbols  # noqa: F401  # type: ignore[reportMissingImports]
    except ImportError:
        return {"entities": [], "relations": [], "error": "graphify not installed"}

    try:
        results = analyze_repo(repo_path)
    except Exception:
        return {"entities": [], "relations": [], "error": "graphify analysis failed"}

    entities = []
    relations = []

    for node in results.get("nodes", []):
        entities.append(
            {
                "id": f"code-{node.get('name', '')}",
                "name": node.get("name", ""),
                "type": node.get("type", "Module"),
                "properties": {
                    "path": node.get("path", ""),
                    "language": node.get("language", ""),
                    "lines": node.get("lines", 0),
                },
            }
        )

    for edge in results.get("edges", []):
        relations.append(
            {
                "source_id": f"code-{edge.get('source', '')}",
                "target_id": f"code-{edge.get('target', '')}",
                "relation_type": edge.get("type", "IMPORTS"),
            }
        )

    return {"entities": entities, "relations": relations}
