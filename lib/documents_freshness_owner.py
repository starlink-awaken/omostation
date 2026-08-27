#!/usr/bin/env python3
"""Workspace-owned, read-only freshness audit for Documents domain entrypoints."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "documents.freshness-audit.v1"
_CLAUDE_REVIEW = re.compile(r"下次审查[:：]\s*(\S+)")
_STATE_REVIEW = re.compile(r"(?im)^\s*last-reviewed[:：]\s*(\S+)")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _load_domain_paths(registry_path: Path, documents_root: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    try:
        if registry_path.is_symlink() or not registry_path.is_file():
            raise ValueError("domain registry must be a regular file")
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        return [], [f"domain registry unavailable: {exc}"]
    if not isinstance(raw, dict) or not isinstance(raw.get("manifests"), list) or not raw["manifests"]:
        return [], ["domain registry must contain a non-empty manifests list"]

    domains: list[tuple[str, Path]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["manifests"]):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("path"), str):
            errors.append(f"manifests[{index}] must contain string id and path")
            continue
        domain_id = item["id"]
        relative = Path(item["path"])
        if domain_id in seen:
            errors.append(f"duplicate domain id: {domain_id}")
            continue
        seen.add(domain_id)
        if relative.is_absolute() or ".." not in relative.parts and not relative.parts:
            errors.append(f"domain {domain_id} path must be relative")
            continue
        manifest = (registry_path.parent / relative).resolve()
        try:
            manifest.relative_to(documents_root)
        except ValueError:
            errors.append(f"domain {domain_id} path escapes Documents root")
            continue
        if manifest.name != "DOMAIN.yaml":
            errors.append(f"domain {domain_id} path must end in DOMAIN.yaml")
            continue
        domains.append((domain_id, manifest.parent))
    return sorted(domains), errors


def _domain_result(domain_id: str, domain_root: Path, today: date) -> dict[str, Any]:
    claude_text = _read_text(domain_root / "CLAUDE.md")
    state_text = _read_text(domain_root / "_control" / "STATE.md")
    claude_match = _CLAUDE_REVIEW.search(claude_text or "")
    state_match = _STATE_REVIEW.search(state_text or "")
    claude_raw = claude_match.group(1) if claude_match else None
    state_raw = state_match.group(1) if state_match else None
    claude_review = _parse_date(claude_raw)
    state_reviewed = _parse_date(state_raw)

    status = "ok"
    if claude_text is None or state_text is None or claude_raw is None or state_raw is None:
        status = "missing"
    elif (claude_review is None and claude_raw is not None) or (state_reviewed is None and state_raw is not None):
        status = "invalid"
    else:
        assert claude_review is not None and state_reviewed is not None
        if claude_review < today or state_reviewed < today:
            status = "stale"

    return {
        "domain_id": domain_id,
        "claude_review": claude_review.isoformat() if claude_review else None,
        "state_reviewed": state_reviewed.isoformat() if state_reviewed else None,
        "status": status,
        "claude_age_days": max((today - claude_review).days, 0) if claude_review else None,
        "state_age_days": max((today - state_reviewed).days, 0) if state_reviewed else None,
    }


def audit(documents_root: Path, *, registry_path: Path | None = None, today: date | None = None) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return {"schema": SCHEMA, "status": "unavailable", "domains": [], "errors": ["Documents root must be a regular directory"], "summary": {"total": 0, "ok": 0, "missing": 0, "invalid": 0, "stale": 0}}
    registry = (registry_path or documents / "@公共/_control/L4-DOMAIN-REGISTRY.yaml").expanduser().resolve()
    domains, errors = _load_domain_paths(registry, documents)
    observed = date.today() if today is None else today
    results = [_domain_result(domain_id, root, observed) for domain_id, root in domains]
    counts = {status: sum(item["status"] == status for item in results) for status in ("ok", "missing", "invalid", "stale")}
    status = "unavailable" if errors else ("findings" if counts["missing"] or counts["invalid"] or counts["stale"] else "ok")
    return {
        "schema": SCHEMA,
        "status": status,
        "documents_root": str(documents),
        "registry": str(registry),
        "domains": results,
        "summary": {"total": len(results), **counts},
        "errors": sorted(set(errors)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--domain-registry", type=Path)
    parser.add_argument("--today")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        observed = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        payload = {"schema": SCHEMA, "status": "unavailable", "domains": [], "errors": ["--today must be ISO date"], "summary": {"total": 0, "ok": 0, "missing": 0, "invalid": 0, "stale": 0}}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else "unavailable: invalid date")
        return 2

    payload = audit(args.documents_root, registry_path=args.domain_registry, today=observed)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        documents = Path(payload["documents_root"]).resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = {"schema": SCHEMA, "status": "unavailable", "domains": [], "errors": ["evidence must be under Workspace and outside Documents"], "summary": {"total": 0, "ok": 0, "missing": 0, "invalid": 0, "stale": 0}}
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else "unavailable: invalid evidence path")
            return 2
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload['summary']['total']} domains")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
