#!/usr/bin/env python3
"""knowledge-graph — scan workspace assets and build a knowledge graph.

Phase 1 of the Knowledge Indexing plan (docs/plans/knowledge-indexing-plan.md).

Scans:
  - ADRs (.omo/_knowledge/decisions/*.md)
  - Scripts (bin/**/*.py, bin/**/*.sh)
  - Runbooks (docs/operations/runbook-*.md)
  - Skills (.agents/skills/*/SKILL.md)
  - Scene cards (docs/scene-cards/*.yaml)
  - Operations docs (docs/operations/*.md)

Extracts nodes (typed entities) and edges (cross-references) and writes
.kb/graph.json.

Usage:
  python3 bin/kb/knowledge-graph.py            # build graph
  python3 bin/kb/knowledge-graph.py --json     # also print summary to stdout
  python3 bin/kb/knowledge-graph.py --output /tmp/graph.json  # custom output
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
OUTPUT_DIR = WORKSPACE / ".kb"
BIN_REF_RE = re.compile(r"\b(bin/[a-z][a-z0-9_-]*/[A-Za-z0-9_./-]+\.(?:py|sh))\b")
ADR_REF_RE = re.compile(r"ADR-(\d{2,4})")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _title_from_heading(text: str) -> str:
    """Extract first # heading."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _extract_bin_refs(text: str) -> list[str]:
    return sorted(set(BIN_REF_RE.findall(text)))


def _extract_adr_refs(text: str) -> list[str]:
    return sorted(set(f"ADR-{m}" for m in ADR_REF_RE.findall(text)))


# ── Node extractors ──────────────────────────────────────────────────────────

def _scan_adrs(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    adr_dir = root / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.is_dir():
        return nodes, edges
    for f in sorted(adr_dir.glob("*.md")):
        text = _read(f)
        num_match = re.match(r"(\d{2,4})-", f.name)
        adr_id = f"ADR-{num_match.group(1)}" if num_match else f.stem
        title = _title_from_heading(text)
        status = ""
        for line in text.splitlines()[:20]:
            if line.strip().startswith("status:"):
                status = line.split(":", 1)[1].strip().strip("'\"")
                break
        nodes.append({"type": "adr", "id": adr_id, "path": str(f.relative_to(root)), "title": title, "status": status})
        for ref in _extract_bin_refs(text):
            edges.append({"from": f"adr:{adr_id}", "to": f"script:{ref}", "relation": "references"})
    return nodes, edges


def _scan_scripts(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return nodes, edges
    for f in sorted(bin_dir.rglob("*")):
        if f.suffix not in (".py", ".sh"):
            continue
        parts = f.parts
        if "_archive" in parts or "__pycache__" in parts or "_archived" in parts:
            continue
        rel = str(f.relative_to(root))
        name = f.stem
        text = _read(f)
        docstring = ""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith('"""') and i + 1 < len(lines):
                docstring = lines[i + 1].strip()
                break
        category = f.parts[1] if len(parts) > 2 else "root"
        nodes.append({"type": "script", "id": f"script:{rel}", "path": rel, "name": name, "category": category, "docstring": docstring[:120]})
    return nodes, edges


def _scan_runbooks(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    ops_dir = root / "docs" / "operations"
    if not ops_dir.is_dir():
        return nodes, edges
    for f in sorted(ops_dir.glob("runbook-*.md")):
        text = _read(f)
        title = _title_from_heading(text)
        rid = f.stem.replace("runbook-", "")
        nodes.append({"type": "runbook", "id": f"runbook:{rid}", "path": str(f.relative_to(root)), "title": title})
        for ref in _extract_bin_refs(text):
            edges.append({"from": f"runbook:{rid}", "to": f"script:{ref}", "relation": "references"})
    return nodes, edges


def _scan_skills(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    skills_dir = root / ".agents" / "skills"
    if not skills_dir.is_dir():
        return nodes, edges
    for d in sorted(skills_dir.iterdir()):
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        text = _read(skill_md)
        name = d.name
        desc = ""
        for line in text.splitlines():
            if line.strip().startswith("description:") or line.strip().startswith('- "'):
                desc = line.split(":", 1)[-1].strip().strip('"').strip()
                break
        nodes.append({"type": "skill", "id": f"skill:{name}", "path": str(skill_md.relative_to(root)), "name": name, "description": desc[:150]})
        for ref in _extract_bin_refs(text):
            edges.append({"from": f"skill:{name}", "to": f"script:{ref}", "relation": "references"})
    return nodes, edges


def _scan_scene_cards(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    cards_dir = root / "docs" / "scene-cards"
    if not cards_dir.is_dir():
        return nodes, edges
    import yaml
    for f in sorted(cards_dir.glob("*.yaml")):
        try:
            docs = [d for d in yaml.safe_load_all(_read(f)) if isinstance(d, dict)]
            body = docs[-1] if docs else {}
        except Exception:
            body = {}
        sid = body.get("scene_id", f.stem)
        title = docs[0].get("title", "") if docs else ""
        journey = body.get("journey_id", "")
        nodes.append({"type": "scene-card", "id": f"scene:{sid}", "path": str(f.relative_to(root)), "title": title, "journey_id": journey})
    return nodes, edges


def _scan_ops_docs(root: Path) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    ops_dir = root / "docs" / "operations"
    if not ops_dir.is_dir():
        return nodes, edges
    for f in sorted(ops_dir.glob("*.md")):
        if f.name.startswith("runbook-"):
            continue  # already scanned as runbooks
        text = _read(f)
        title = _title_from_heading(text)
        did = f"doc:{f.stem}"
        nodes.append({"type": "doc", "id": did, "path": str(f.relative_to(root)), "title": title})
        for ref in _extract_bin_refs(text):
            edges.append({"from": did, "to": f"script:{ref}", "relation": "references"})
    return nodes, edges


# ── Main ─────────────────────────────────────────────────────────────────────

SCANNERS = [
    ("adr", _scan_adrs),
    ("script", _scan_scripts),
    ("runbook", _scan_runbooks),
    ("skill", _scan_skills),
    ("scene-card", _scan_scene_cards),
    ("doc", _scan_ops_docs),
]


def build_graph(root: Path) -> dict[str, Any]:
    all_nodes: list[dict] = []
    all_edges: list[dict] = []
    type_counts: dict[str, int] = {}

    for scanner_name, scanner_fn in SCANNERS:
        nodes, edges = scanner_fn(root)
        all_nodes.extend(nodes)
        all_edges.extend(edges)
        type_counts[scanner_name] = len(nodes)

    # Deduplicate edges
    seen_edges: set[tuple] = set()
    unique_edges = []
    for e in all_edges:
        key = (e["from"], e["to"], e["relation"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds"),
        "workspace": str(root),
        "summary": {
            "total_nodes": len(all_nodes),
            "total_edges": len(unique_edges),
            "by_type": type_counts,
        },
        "nodes": all_nodes,
        "edges": unique_edges,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "graph.json", help="Output path")
    parser.add_argument("--json", action="store_true", help="Print summary to stdout")
    args = parser.parse_args(argv)

    graph = build_graph(WORKSPACE)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, args.output)

    if args.json:
        print(json.dumps(graph["summary"], ensure_ascii=False, indent=2))
    else:
        s = graph["summary"]
        print(f"Knowledge graph built: {args.output}")
        print(f"  nodes: {s['total_nodes']}")
        print(f"  edges: {s['total_edges']}")
        for t, c in sorted(s.get("by_type", {}).items()):
            print(f"    {t}: {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())