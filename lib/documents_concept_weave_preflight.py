"""Workspace-owned, read-only health preflight for the concept corpus."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = "documents.concept-weave-preflight.v1"
WRITE_CAPABLE_OPERATIONS = ["mesh", "bridge", "exec-bridge", "inbox-todo"]
_LINK = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")
_REVIEWED = re.compile(r"(?mi)^\s*last-reviewed[:：]\s*(\d{4}-\d{2}-\d{2})")


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "unavailable",
        "concept_root": None,
        "summary": {"concept_files": 0, "orphan_files": 0, "decay_candidates": 0, "link_edges": 0},
        "write_capable_operations": WRITE_CAPABLE_OPERATIONS,
        "write_capable_status": "deferred",
        "findings": [message],
        "errors": [message],
    }


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file() and not path.is_symlink() and path.name not in {"README.md", "INDEX.md"})


def audit(documents_root: Path, *, workspace_root: Path, concept_root_relative: str, today: date) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return _unavailable("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        return _unavailable("Workspace root must be a regular directory")
    relative = Path(concept_root_relative)
    if relative.is_absolute() or ".." in relative.parts:
        return _unavailable("concept-root-relative must be relative and non-traversing")
    root = (documents / relative).resolve()
    try:
        root.relative_to(documents)
    except ValueError:
        return _unavailable("concept root escapes Documents root")
    if not root.is_dir() or root.is_symlink():
        return _unavailable("concept root must be a regular directory")

    paths = _files(root)
    path_set = {path.resolve() for path in paths}
    incoming: dict[Path, int] = {path: 0 for path in paths}
    link_edges = 0
    for source in paths:
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for target in _LINK.findall(text):
            if "://" in target or target.startswith(("#", "/")):
                continue
            link_edges += 1
            resolved = (source.parent / target).resolve()
            if resolved in path_set:
                incoming[resolved] += 1
    orphan = [str(path.relative_to(root)) for path, count in incoming.items() if count == 0]
    decay: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")[:4096]
        except (OSError, UnicodeError):
            continue
        match = _REVIEWED.search(text)
        if match:
            try:
                if (today - date.fromisoformat(match.group(1))).days > 90:
                    decay.append(str(path.relative_to(root)))
            except ValueError:
                decay.append(str(path.relative_to(root)))
    findings = []
    if orphan:
        findings.append(f"orphan concepts: {len(orphan)}")
    if decay:
        findings.append(f"decay candidates: {len(decay)}")
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "concept_root": concept_root_relative,
        "summary": {"concept_files": len(paths), "orphan_files": len(orphan), "decay_candidates": len(decay), "link_edges": link_edges},
        "orphan_files": orphan,
        "decay_files": decay,
        "write_capable_operations": WRITE_CAPABLE_OPERATIONS,
        "write_capable_status": "deferred",
        "findings": findings,
        "errors": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--concept-root-relative", default="@学习进化/_knowledge/50-concepts")
    parser.add_argument("--today")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        payload = _unavailable("--today must be ISO date")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else payload["status"])
        return 2
    payload = audit(args.documents_root, workspace_root=args.workspace_root, concept_root_relative=args.concept_root_relative, today=today)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload.get('summary', {}).get('concept_files', 0)} concepts")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
