"""Workspace-owned, read-only convergence preflight for Documents domains."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "documents.convergence-preflight.v1"
_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "unavailable",
        "checks": {},
        "findings": [message],
        "errors": [message],
        "summary": {"checks": 0, "passed": 0, "findings": 0},
    }


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _read(path: Path) -> str | None:
    try:
        if not _regular_file(path):
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _registry_domains(registry: Path, documents: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    try:
        raw = yaml.safe_load(registry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [], [f"domain registry unavailable: {exc}"]
    if not isinstance(raw, dict) or not isinstance(raw.get("manifests"), list):
        return [], ["domain registry must contain a manifests list"]
    domains: list[tuple[str, Path]] = []
    findings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["manifests"]):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("path"), str):
            findings.append(f"registry manifests[{index}] must contain string id and path")
            continue
        domain_id = item["id"]
        if domain_id in seen:
            findings.append(f"duplicate domain id: {domain_id}")
            continue
        seen.add(domain_id)
        relative = Path(item["path"])
        manifest = (registry.parent / relative).resolve()
        try:
            manifest.relative_to(documents)
        except ValueError:
            findings.append(f"domain {domain_id} path escapes Documents root")
            continue
        if manifest.name != "DOMAIN.yaml":
            findings.append(f"domain {domain_id} path must end in DOMAIN.yaml")
            continue
        domains.append((domain_id, manifest.parent))
    return domains, findings


def _check_required(documents: Path) -> list[str]:
    required = (
        "CLAUDE_GLOBAL.md",
        "CLAUDE.md",
        "@公共/_control/CLAUDE-公约.md",
        "@公共/_control/DOMAIN-META-MODEL.md",
        "@公共/_control/REGISTRY.md",
    )
    return [f"missing required control document: {item}" for item in required if not _regular_file(documents / item)]


def _check_domains(domains: list[tuple[str, Path]]) -> list[str]:
    findings: list[str] = []
    for domain_id, root in domains:
        for relative in ("DOMAIN.yaml", "CLAUDE.md", "_control/STATE.md"):
            if not _regular_file(root / relative):
                findings.append(f"{domain_id}: missing {relative}")
    return findings


def _check_broken_links(documents: Path) -> list[str]:
    findings: list[str] = []
    ignored = {".git", "_archive", "_storage", "存档", "_generated", ".history"}
    try:
        paths = sorted(path for path in documents.rglob("*.md") if not any(part in ignored for part in path.parts))
    except OSError as exc:
        return [f"markdown scan unavailable: {exc}"]
    for source in paths:
        text = _read(source)
        if text is None:
            continue
        for target in _MARKDOWN_LINK.findall(text):
            if "://" in target or target.startswith(("#", "/")):
                continue
            candidate = (source.parent / target).resolve()
            try:
                candidate.relative_to(documents)
            except ValueError:
                continue
            if not candidate.exists():
                findings.append(f"broken reference: {source.relative_to(documents)} -> {target}")
    return findings


def _check_entities(documents: Path) -> list[str]:
    root = documents / "@公共" / "_entities"
    if not root.is_dir():
        return []
    findings: list[str] = []
    try:
        paths = sorted(root.rglob("*.yaml"))
    except OSError as exc:
        return [f"entity scan unavailable: {exc}"]
    for path in paths:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            findings.append(f"entity invalid: {path.relative_to(documents)}: {exc}")
            continue
        if not isinstance(value, (dict, list)):
            findings.append(f"entity must be mapping or list: {path.relative_to(documents)}")
    return findings


def audit(documents_root: Path, *, workspace_root: Path, registry_path: Path | None = None) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return _unavailable("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        return _unavailable("Workspace root must be a regular directory")
    registry = (registry_path or documents / "@公共/_control/L4-DOMAIN-REGISTRY.yaml").expanduser().resolve()
    if not _regular_file(registry):
        return _unavailable("domain registry must be a regular file")

    domains, registry_findings = _registry_domains(registry, documents)
    checks = {
        "required_controls": _check_required(documents),
        "registry": registry_findings,
        "domain_entrypoints": _check_domains(domains),
        "broken_references": _check_broken_links(documents),
        "entity_consistency": _check_entities(documents),
    }
    findings = [item for values in checks.values() for item in values]
    passed = sum(not values for values in checks.values())
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "registry": str(registry),
        "domains": [domain_id for domain_id, _ in domains],
        "checks": checks,
        "findings": findings,
        "errors": [],
        "summary": {"checks": len(checks), "passed": passed, "findings": len(findings)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--domain-registry", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = audit(args.documents_root, workspace_root=args.workspace_root, registry_path=args.domain_registry)
    if args.evidence and payload["status"] != "unavailable":
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload['summary']['findings']} findings")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
