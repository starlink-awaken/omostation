"""Graphify 分析器 — 语义知识图谱

v0.8.14 API: graphify CLI entry point via `graphify .` or `python -m graphify`
Output: writes to graphify-out/ directory (GRAPH_REPORT.md, graph.json, graph.html)
"""

import json
import subprocess
from pathlib import Path

from codeanalyze.core.registry import ToolInfo  # type: ignore[import-not-found]


def analyze(repo_path: str = ".", tool: ToolInfo | None = None) -> dict:
    """运行 Graphify，返回实体-关系字典。

    Graphify v0.8.14 以 CLI 为核心入口。适配器调用 graphify CLI，
    从 graphify-out/graph.json 读取结果。
    """
    root = Path(repo_path).resolve()
    graph_out = root / "graphify-out"
    json_path = graph_out / "graph.json"

    # Check if already analyzed
    if json_path.exists():
        data = json.loads(json_path.read_text("utf-8"))
        return _extract_from_results(data)

    # Run graphify CLI
    try:
        result = subprocess.run(
            ["python3", "-m", "graphify"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
        )
    except FileNotFoundError:
        return {"error": "graphify not found. Run: pip install graphifyy"}

    # Check for output file
    if json_path.exists():
        data = json.loads(json_path.read_text("utf-8"))
        return _extract_from_results(data)

    # No JSON output; try markdown report
    md_path = graph_out / "GRAPH_REPORT.md"
    if md_path.exists():
        md_path.read_text("utf-8", errors="ignore")[:500]
        return {"error": f"graphify ran but no JSON output (GRAPH_REPORT.md available at {md_path})"}

    # Check stderr for clues
    stderr = (result.stderr or "")[:200]
    stdout = (result.stdout or "")[:200]
    error_msg = "graphify produced no output"
    if stderr:
        error_msg = f"graphify: {stderr}"
    elif stdout and "error" in stdout.lower():
        error_msg = f"graphify: {stdout}"
    return {"error": error_msg}


def _extract_from_results(data: dict) -> dict:
    """Normalize graphify v0.8.14 output to entities/relations dict.

    graphify v0.8.14 JSON format (NetworkX export):
    {nodes: [{id, label, norm_label, file_type, source_file, source_location, community, ...}],
     links: [{source, target, key, ...}],
     directed, multigraph, graph, hyperedges, built_at_commit}
    """
    entities = []
    seen_ids = set()
    for node in data.get("nodes", []):
        node_id = node.get("id", "") or node.get("norm_label", "") or node.get("label", "")
        if not node_id:
            continue
        eid = f"code-{node_id}"
        if eid in seen_ids:
            continue
        seen_ids.add(eid)

        entities.append(
            {
                "id": eid,
                "name": node.get("norm_label", "") or node.get("label", node_id),
                "type": _map_file_type(node.get("file_type", "")),
                "properties": {
                    "path": node.get("source_file", ""),
                    "language": node.get("file_type", ""),
                    "community": node.get("community", ""),
                    "source_location": node.get("source_location", ""),
                },
            }
        )

    relations = []
    for link in data.get("links", []):
        src = f"code-{link.get('source', '')}"
        tgt = f"code-{link.get('target', '')}"
        rel_type = link.get("type", "IMPORTS")
        if not isinstance(rel_type, str) or rel_type == "":
            rel_type = "IMPORTS"
        relations.append(
            {
                "source": src,
                "target": tgt,
                "type": rel_type,
                "confidence": "EXTRACTED",
            }
        )

    return {"entities": entities, "relations": relations, "error": None}


def _map_file_type(ft: str) -> str:
    """Map graphify file_type to entity type."""
    mapping = {
        "code": "Module",
        "file": "File",
        "directory": "Directory",
        "document": "Document",
        "doc": "Document",
        "image": "Image",
        "video": "Video",
        "audio": "Audio",
        "rationale": "Concept",
        "concept": "Concept",
    }
    return mapping.get(ft, "Artifact")


def get_report_path(repo_path: str = ".") -> Path | None:
    p = Path(repo_path).resolve() / "graphify-out" / "GRAPH_REPORT.md"
    return p if p.exists() else None


def get_graph_html(repo_path: str = ".") -> Path | None:
    p = Path(repo_path).resolve() / "graphify-out" / "graph.html"
    return p if p.exists() else None
