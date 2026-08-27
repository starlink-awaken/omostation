#!/usr/bin/env python3
"""Workspace-owned, read-only readiness check for the legacy Documents bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "documents.bridge-preflight.v1"
_BRIDGE_BEGIN = "AUTOGEN:WORKSPACE-BRIDGE BEGIN"
_CARDS_BEGIN = "AUTOGEN:CARDS-VIEW BEGIN"


def _base(status: str, *, sources: dict[str, Any], markers: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "sources": sources,
        "markers": markers,
        "summary": {
            "sources_ready": sum(item.get("status") == "ready" for item in sources.values()),
            "markers_ready": sum(item.get("status") == "ready" for item in markers.values()),
        },
        "errors": sorted(set(errors or [])),
    }


def _roots(documents_root: Path, workspace_root: Path) -> tuple[Path, Path, list[str]]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or not workspace.is_dir():
        return documents, workspace, ["Documents and Workspace roots must be directories"]
    if documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        return documents, workspace, ["Documents and Workspace roots must be disjoint"]
    return documents, workspace, []


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def inspect(documents_root: Path, workspace_root: Path, dashboard_relative: str) -> dict[str, Any]:
    documents, workspace, errors = _roots(documents_root, workspace_root)
    if errors:
        return _base("unavailable", sources={}, markers={}, errors=errors)
    dashboard = documents / dashboard_relative
    source_paths = {
        "system_state": workspace / ".omo/state/system.yaml",
        "health_state": workspace / ".omo/state/health.yaml",
        "cards_store": workspace / "data/cards/cards.db",
    }
    sources = {
        name: {"status": "ready" if _regular_file(path) else "missing"}
        for name, path in source_paths.items()
    }
    markers = {"workspace_bridge": {"status": "missing"}, "cards_view": {"status": "missing"}}
    if _regular_file(dashboard):
        try:
            text = dashboard.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return _base("unavailable", sources=sources, markers=markers, errors=[f"dashboard unreadable: {exc}"])
        markers = {
            "workspace_bridge": {"status": "ready" if text.count(_BRIDGE_BEGIN) == 1 else "missing"},
            "cards_view": {"status": "ready" if text.count(_CARDS_BEGIN) == 1 else "missing"},
        }
    else:
        markers = {name: {"status": "missing"} for name in markers}
    result = _base("ready" if all(item["status"] == "ready" for item in (*sources.values(), *markers.values())) else "findings", sources=sources, markers=markers)
    result["dashboard"] = {"relative": dashboard_relative, "status": "ready" if _regular_file(dashboard) else "missing"}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--dashboard-relative", default="@驾驶舱/_control/DASHBOARD.md")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = inspect(args.documents_root, args.workspace_root, args.dashboard_relative)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _base("unavailable", sources={}, markers={}, errors=["evidence must be under Workspace and outside Documents"])
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else "unavailable: invalid evidence path")
            return 2
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: bridge preflight")
    return 0 if payload["status"] == "ready" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
