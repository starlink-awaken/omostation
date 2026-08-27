"""Workspace-owned, read-only preflight for the Documents signal ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "documents.signals-preflight.v1"
MACHINE_SOURCES = ("aggregated", "scenario_engine", "distributed.", "lifecycle.")


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "unavailable",
        "signals_file": None,
        "signals": [],
        "findings": [message],
        "errors": [message],
        "summary": {"human": 0, "machine": 0, "total": 0},
    }


def _is_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _parse_entries(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
        # SIGNALS.md is YAML wrapped by document markers, not a YAML stream.
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            lines = lines[1:]
        if lines and lines[-1].strip() == "---":
            lines = lines[:-1]
        value = yaml.safe_load("\n".join(lines))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [], [f"SIGNALS.md unavailable or invalid: {exc}"]
    if value is None:
        return [], []
    if not isinstance(value, dict) or not isinstance(value.get("signals"), list):
        return [], ["SIGNALS.md must contain a signals list"]
    entries: list[dict[str, Any]] = []
    findings: list[str] = []
    for index, entry in enumerate(value["signals"]):
        if not isinstance(entry, dict):
            findings.append(f"signals[{index}] must be a mapping")
            continue
        source = entry.get("source")
        if not isinstance(source, str) or not source:
            findings.append(f"signals[{index}] missing string source")
        entries.append(entry)
    return entries, findings


def _is_machine(entry: dict[str, Any]) -> bool:
    source = str(entry.get("source", ""))
    return any(source == marker or source.startswith(marker) for marker in MACHINE_SOURCES)


def audit(documents_root: Path, *, workspace_root: Path) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return _unavailable("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        return _unavailable("Workspace root must be a regular directory")
    signals_path = documents / "@驾驶舱" / "_control" / "SIGNALS.md"
    if not _is_regular_file(signals_path):
        return _unavailable("SIGNALS.md must be a regular file")
    entries, parse_findings = _parse_entries(signals_path)
    machine = sum(_is_machine(entry) for entry in entries)
    human = len(entries) - machine
    findings = [*parse_findings]
    if machine:
        findings.append(f"{machine} machine signal(s) remain in Documents SIGNALS.md")
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "signals_file": str(signals_path),
        "signals": [
            {"source": entry.get("source"), "type": entry.get("type"), "ts": entry.get("ts"), "machine": _is_machine(entry)}
            for entry in entries
        ],
        "findings": findings,
        "errors": [],
        "summary": {"human": human, "machine": machine, "total": len(entries)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = audit(args.documents_root, workspace_root=args.workspace_root)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload['summary']['total']} signals")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
