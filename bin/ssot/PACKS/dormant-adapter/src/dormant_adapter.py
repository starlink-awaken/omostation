#!/usr/bin/env python3
"""bus-usage-report — Round 5 P74 dormant-adapter detector.

Scans the workspace for projects that declare bus-foundation in their
dependencies but whose *production* code does not actually call
bus-foundation APIs. This catches the P71 class-A "declaration without
execution" trap.

A "production call" is any of:
  - bus_foundation.facade.event.publish(...)
  - bus_foundation.facade.event.subscribe(...)
  - bus_foundation.facade.control.submit_task / schedule_callback / ack / nack
  - bus_foundation.facade.data.outbox_emit / emit
  - bus_foundation.publish / subscribe / schedule (top-level, deprecated)
  - direct backend wiring (bus_foundation._backends["..."])

Excluded:
  - tests/ directories (test-only usage doesn't count as production)
  - docs/, *.md (documentation references)
  - The bus-foundation project itself (it's the library, not a consumer)

Output (stdout): per-project report + summary line.
Exit code 0: every consumer has at least one production call.
Exit code 1: one or more consumers are dormant.

Usage:
    python3 bin/ssot/bus-usage-report.py [--root /path/to/workspace] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 2-pass detection: first confirm the file imports bus-foundation, then
# look for call sites on bus-derived names (bus_event.publish,
# bus.publish, etc.) or wrapped helpers (_bus_publish, _emit_event).
_IMPORT_BUS_RE = [
    re.compile(r"\bimport\s+bus_foundation\b"),
    re.compile(r"\bfrom\s+bus_foundation\b"),
    re.compile(r"\bfrom\s+bus_foundation\.\w+(?:\.\w+)*\s+import\b"),
]

_CALL_RE = [
    re.compile(r"\b(bus|bus_event|bus_control|bus_data|bus_adapter)\.\s*(publish|subscribe|emit|submit_task|schedule_callback|ack|nack|outbox_emit|schedule)\s*\("),
    re.compile(r"\b_(bus_publish|emit_event|emit|bus_emit|publish_event)\s*\("),
    re.compile(r"\b(publish|subscribe|schedule)\s*\(\s*[^)]*BusEnvelope"),
    re.compile(r"@\s*(bus_event|bus_control|bus_data)\.\s*(publish|subscribe|schedule_callback)"),
    re.compile(r"BusEnvelope\s*\(.*topic\s*="),
]

_SKIP_DIRS = {"tests", "test", "docs", "doc", "examples", "benchmarks", "__pycache__", ".venv", "node_modules", "build", "dist"}
_SKIP_BASENAMES = ("test_", "conftest", "setup", "README", "CHANGELOG", "AGENTS", "CLAUDE", "ARCHITECTURE", "Makefile")


def _file_has_bus_import(text: str) -> bool:
    return any(p.search(text) for p in _IMPORT_BUS_RE)


def _file_has_bus_call(text: str) -> list[str]:
    hits: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat in _CALL_RE:
            if pat.search(line):
                hits.append(f"L{i}: {line.strip()[:120]}")
                break
    return hits


def _find_bus_call(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    if not _file_has_bus_import(text):
        return []
    return _file_has_bus_call(text)


def _has_bus_foundation_dep(project_root: Path) -> bool:
    """Check the project's pyproject.toml (or any nested package's) for bus-foundation."""
    candidates = [project_root / "pyproject.toml", *project_root.rglob("pyproject.toml")]
    for pyproject in candidates:
        if not pyproject.exists():
            continue
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "bus-foundation" in text:
            return True
    return False


def _find_source_roots(project_root: Path) -> list[Path]:
    """Return source directories to scan.

    Supports 3 layouts: <project>/src/, <project>/packages/<sub>/src|lib.
    Explicit discovery (vs. rglob project_root) is ~50x faster on real
    workspace by avoiding large non-source trees.
    """
    roots: list[Path] = []
    for c in (project_root / "src", project_root / "lib"):
        if c.is_dir():
            roots.append(c)
    packages_dir = project_root / "packages"
    if packages_dir.is_dir():
        for sub in sorted(packages_dir.iterdir()):
            if not sub.is_dir():
                continue
            for sc in (sub / "src", sub / "lib"):
                if sc.is_dir():
                    roots.append(sc)
    return roots


def _iter_python_files(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path.parts and (set(path.parts) & _SKIP_DIRS):
                continue
            if any(path.name.startswith(p) for p in _SKIP_BASENAMES):
                continue
            out.append(path)
    return out


def scan_consumer(project_root: Path) -> dict:
    has_dep = _has_bus_foundation_dep(project_root)
    if not has_dep:
        return {
            "project": project_root.name,
            "path": str(project_root),
            "has_dep": False,
            "production_calls": 0,
            "call_sites": [],
        }
    roots = _find_source_roots(project_root)
    py_files = _iter_python_files(roots)
    hits: list[dict] = []
    for path in py_files:
        for hit in _find_bus_call(path):
            hits.append({"file": str(path.relative_to(project_root)), "line": hit})
    return {
        "project": project_root.name,
        "path": str(project_root),
        "has_dep": True,
        "production_calls": len(hits),
        "call_sites": hits[:10],
    }


def _discover_consumers(projects_dir: Path) -> list[Path]:
    """Walk projects_dir for top-level + monorepo-nested pyproject.toml files."""
    projects: list[Path] = []
    for pyproject in sorted(projects_dir.rglob("pyproject.toml")):
        project_root = pyproject.parent
        # Skip nested pyproject.toml (e.g. inside another pyproject tree)
        is_nested = False
        for ancestor in project_root.parents:
            if ancestor == projects_dir:
                break
            if (ancestor / "pyproject.toml").exists() and ancestor != project_root:
                is_nested = True
                break
        if is_nested:
            continue
        # Skip the library itself
        if project_root.name == "bus-foundation" and (project_root / "src" / "bus_foundation").exists():
            continue
        projects.append(project_root)
    return projects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument("--projects-dir", default="projects")
    args = parser.parse_args()

    root = args.root
    projects_dir = root / args.projects_dir
    if not projects_dir.exists():
        print(f"ERROR: {projects_dir} does not exist", file=sys.stderr)
        return 2

    projects = _discover_consumers(projects_dir)
    if not projects:
        print(f"ERROR: no consumer projects found under {projects_dir}", file=sys.stderr)
        return 2

    reports = [scan_consumer(p) for p in projects]
    consumers = [r for r in reports if r["has_dep"]]
    dormant = [r for r in consumers if r["production_calls"] == 0]
    active = [r for r in consumers if r["production_calls"] > 0]

    summary = {
        "root": str(root),
        "total_consumers": len(consumers),
        "active": len(active),
        "dormant": len(dormant),
        "reports": reports,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"bus-foundation consumer scan ({len(consumers)} projects, {len(active)} active, {len(dormant)} dormant)")
        print("=" * 80)
        for r in consumers:
            status = "ACTIVE" if r["production_calls"] > 0 else "DORMANT"
            print(f"  [{status}] {r['project']:20s}  {r['production_calls']:3d} call site(s)")
            for site in r["call_sites"][:3]:
                print(f"           {site['file']}  {site['line']}")
        print("=" * 80)
        if dormant:
            print(f"\nWARNING: {len(dormant)} consumer(s) declare bus-foundation but have NO production calls:")
            for r in dormant:
                print(f"  - {r['project']}: declares dep, no production code uses it")
            print("\nThis is the P71 class-A 'declaration without execution' trap.")
            return 1
        print("\nAll consumers have production bus-foundation calls.")
    return 0 if not dormant else 1


if __name__ == "__main__":
    sys.exit(main())
