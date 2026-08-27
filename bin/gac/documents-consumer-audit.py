#!/usr/bin/env python3
"""Audit active consumers of the Documents execution plane without running them."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import subprocess
import sys
from collections.abc import Iterator
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any
from xml.parsers.expat import ExpatError

import yaml

SCHEMA = "documents.consumer-audit.v1"
_PATH_DELIMITERS = "\"'`;&)|<>\n"
_HOME_MARKER = re.compile(r"(?:\$HOME|~)/Documents(?:/([^\"'`;&)|<>\n]+))?")


def _load_families(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [], [f"migration registry unavailable: {exc}"]
    if not isinstance(raw, dict) or not isinstance(raw.get("families"), list):
        return [], ["migration registry must contain a families list"]
    families: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, family in enumerate(raw["families"]):
        if not isinstance(family, dict) or not isinstance(family.get("id"), str):
            errors.append(f"families[{index}] must have a string id")
            continue
        globs = family.get("source_globs")
        if not isinstance(globs, list) or not all(isinstance(item, str) and item for item in globs):
            errors.append(f"family {family['id']} source_globs must be a non-empty string list")
            continue
        families.append({"id": family["id"], "source_globs": globs})
    return families, errors


def _relative_path(value: str, documents_root: Path) -> str | None:
    candidate = value.strip().rstrip("\"'`;&)|<>")
    root_text = str(documents_root)
    if candidate == root_text:
        return "."
    if candidate.startswith(root_text + "/"):
        return candidate[len(root_text) + 1 :]
    match = _HOME_MARKER.fullmatch(candidate)
    if match:
        return match.group(1) or "."
    if candidate.startswith("Documents/"):
        return candidate.removeprefix("Documents/")
    if candidate.startswith("@") and ("/" in candidate and any(ord(char) > 127 for char in candidate.split("/", 1)[0])):
        return candidate
    if candidate.startswith("_inbox/"):
        return candidate
    return None


def _is_execution_candidate(relative: str) -> bool:
    """Ignore ordinary content references; retain paths that can execute or hold state."""
    return any(
        marker in relative
        for marker in ("/_runtime/", "/_scripts/", "/tools/", "/.kems/", "/family-dashboard-app/")
    ) or relative.endswith((".py", ".py3", ".sh", ".js", ".ts", ".sqlite", ".sqlite3", ".db"))


def _paths_in_text(text: str, documents_root: Path) -> Iterator[str]:
    root_text = str(documents_root)
    start = 0
    while True:
        index = text.find(root_text, start)
        if index < 0:
            break
        end = index + len(root_text)
        while end < len(text) and text[end] not in _PATH_DELIMITERS:
            end += 1
        relative = _relative_path(text[index:end], documents_root)
        if relative is not None:
            yield relative
        start = end

    for match in _HOME_MARKER.finditer(text):
        relative = match.group(1) or "."
        yield relative

    for match in re.finditer(r"(?<![\w/])((?:@[^\s/'\"]+|_inbox)/[^\s'\"`;&)|<>]+)", text):
        relative = _relative_path(match.group(1), documents_root)
        if relative is not None:
            yield relative


def _family_for(relative: str, families: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    matches = [
        family["id"]
        for family in families
        if any(fnmatchcase(relative, pattern) for pattern in family["source_globs"])
    ]
    return (matches[0] if len(matches) == 1 else None), matches


def _consumer_id(source: str, kind: str, relative: str, fragment: str) -> str:
    payload = "\x1f".join((source, kind, relative, fragment.strip()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _consumer(source: str, kind: str, relative: str, fragment: str, families: list[dict[str, Any]]) -> dict[str, Any]:
    family, matches = _family_for(relative, families)
    return {
        "consumer_id": _consumer_id(source, kind, relative, fragment),
        "source": source,
        "kind": kind,
        "active": True,
        "relative_path": relative,
        "command_fragment": fragment.strip(),
        "family": family,
        "family_matches": matches,
    }


def _active_lines(text: str) -> Iterator[str]:
    logical = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not logical and (not line.strip() or line.lstrip().startswith("#")):
            continue
        logical += line
        if logical.endswith("\\"):
            logical = logical[:-1] + " "
            continue
        yield logical
        logical = ""
    if logical:
        yield logical


def _scan_text(
    path_label: str,
    kind: str,
    text: str,
    documents_root: Path,
    families: list[dict[str, Any]],
    *,
    commands_only: bool = False,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for line in _active_lines(text):
        if commands_only:
            fragments = re.findall(r"`([^`]+)`", line)
            command_like = line.lstrip().startswith(("$", "python", "python3", "bash", "sh ", "uv ", "cd ", "exec ", "/"))
            if fragments:
                lines = fragments
            elif command_like:
                lines = [line]
            else:
                continue
        else:
            lines = [line]
        for candidate in lines:
            for relative in sorted(set(_paths_in_text(candidate, documents_root))):
                if not _is_execution_candidate(relative):
                    continue
                found.append(_consumer(path_label, kind, relative, candidate, families))
    return found


def _scan_crontab(
    path: Path | None,
    documents_root: Path,
    families: list[dict[str, Any]],
    text: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if text is None and path is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return [], [f"crontab unavailable: {exc}"]
    if text is None:
        return [], ["crontab unavailable: no snapshot"]
    return _scan_text("crontab", "crontab", text, documents_root, families), []


def _walk_files(root: Path, suffixes: tuple[str, ...], names: tuple[str, ...] = ()) -> tuple[list[Path], list[str]]:
    if not root.exists():
        return [], [f"source root unavailable: {root}"]
    if not root.is_dir():
        return [], [f"source root is not a directory: {root}"]
    try:
        return sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not any(part == "disabled" or part.startswith(".archived") for part in path.parts)
            and (path.suffix in suffixes or path.name in names)
        ), []
    except OSError as exc:
        return [], [f"source root unreadable: {root}: {exc}"]


def _scan_launch_agents(root: Path, documents_root: Path, families: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    paths, errors = _walk_files(root, (".plist",))
    consumers: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = plistlib.loads(path.read_bytes())
        except (OSError, ValueError, ExpatError, plistlib.InvalidFileException) as exc:
            errors.append(f"LaunchAgent invalid: {path}: {exc}")
            continue
        values: list[str] = []
        for key in ("Program", "ProgramArguments"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                values.extend(item for item in value if isinstance(item, str))
        for value in values:
            for relative in sorted(set(_paths_in_text(value, documents_root))):
                consumers.append(_consumer(str(path), "launchagent", relative, value, families))
    return consumers, errors


def _scan_tree(
    root: Path,
    kind: str,
    documents_root: Path,
    families: list[dict[str, Any]],
    suffixes: tuple[str, ...],
    names: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], list[str]]:
    paths, errors = _walk_files(root, suffixes, names)
    consumers: list[dict[str, Any]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"source unreadable: {path}: {exc}")
            continue
        consumers.extend(_scan_text(str(path), kind, text, documents_root, families, commands_only=True))
    return consumers, errors


def audit(
    *,
    documents_root: Path,
    registry: Path,
    crontab: Path | None,
    launch_agents_root: Path,
    scheduled_root: Path,
    crontab_text: str | None = None,
) -> dict[str, Any]:
    documents_root = documents_root.expanduser().resolve()
    families, errors = _load_families(registry.expanduser().resolve())
    consumers: list[dict[str, Any]] = []
    found, source_errors = _scan_crontab(
        crontab.expanduser().resolve() if crontab is not None else None,
        documents_root,
        families,
        crontab_text,
    )
    consumers.extend(found)
    errors.extend(source_errors)
    found, source_errors = _scan_launch_agents(launch_agents_root.expanduser().resolve(), documents_root, families)
    consumers.extend(found)
    errors.extend(source_errors)
    found, source_errors = _scan_tree(
        scheduled_root.expanduser().resolve(), "scheduled-skill", documents_root, families, (".md", ".yaml", ".yml")
    )
    consumers.extend(found)
    errors.extend(source_errors)
    found, source_errors = _scan_tree(
        documents_root, "domain-gateway", documents_root, families, (".md",), ("CLAUDE.md", "AGENTS.md")
    )
    consumers.extend(found)

    unique: dict[str, dict[str, Any]] = {item["consumer_id"]: item for item in consumers}
    consumers = [unique[key] for key in sorted(unique)]
    unmatched = [item for item in consumers if item["family"] is None]
    errors.extend(
        f"{item['consumer_id']}: unmatched migration family for {item['relative_path']} ({item['kind']})"
        for item in unmatched
    )
    status = "unavailable" if errors and not consumers else ("violations" if errors else "ok")
    return {
        "schema": SCHEMA,
        "status": status,
        "documents_root": str(documents_root),
        "registry": str(registry.expanduser().resolve()),
        "consumer_ids": [item["consumer_id"] for item in consumers],
        "consumers": consumers,
        "summary": {
            "total": len(consumers),
            "active": sum(1 for item in consumers if item["active"]),
            "unmatched": len(unmatched),
            "families": {
                family: sum(1 for item in consumers if item["family"] == family)
                for family in sorted({item["family"] for item in consumers if item["family"]})
            },
        },
        "errors": sorted(set(errors)),
    }


def _current_crontab(path: Path) -> tuple[Path | None, str | None, list[str]]:
    if path != Path("-"):
        return path, None, []
    try:
        result = subprocess.run(["crontab", "-l"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, [f"current crontab unavailable: {exc}"]
    if result.returncode != 0:
        return None, None, [f"current crontab unavailable: {result.stderr.strip() or result.returncode}"]
    return None, result.stdout, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--registry", type=Path, default=Path(__file__).resolve().parents[2] / ".omo/_truth/registry/documents-content-plane-migrations.yaml")
    parser.add_argument("--crontab", type=Path, default=Path("-"))
    parser.add_argument("--launch-agents-root", type=Path, default=Path.home() / "Library/LaunchAgents")
    parser.add_argument("--scheduled-root", type=Path, default=Path.home() / "Documents/Claude/Scheduled")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors: list[str] = []
    crontab, crontab_text, crontab_errors = _current_crontab(args.crontab)
    errors.extend(crontab_errors)
    if crontab_errors:
        payload = {"schema": SCHEMA, "status": "unavailable", "errors": sorted(set(crontab_errors)), "consumers": [], "consumer_ids": [], "summary": {"total": 0, "active": 0, "unmatched": 0, "families": {}}}
    else:
        payload = audit(
            documents_root=args.documents_root,
            registry=args.registry,
            crontab=crontab,
            crontab_text=crontab_text,
            launch_agents_root=args.launch_agents_root,
            scheduled_root=args.scheduled_root,
        )
        if errors:
            payload["errors"] = sorted(set([*payload.get("errors", []), *errors]))
            payload["status"] = "unavailable"

    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(Path(payload.get("documents_root", "."))):
            print(json.dumps({"schema": SCHEMA, "status": "unavailable", "errors": ["evidence must be under Workspace and outside Documents"]}, ensure_ascii=False))
            return 2
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload.get('status', 'unavailable')}: {payload.get('summary', {}).get('total', 0)} consumers")
    return 0 if payload.get("status") == "ok" else (1 if payload.get("status") == "violations" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
