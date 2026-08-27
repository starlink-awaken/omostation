"""Workspace-owned, read-only replacement for the legacy daily health runner."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCHEMA = "documents.daily-health-preflight.v1"
DEFAULT_DOMAIN = "@工作文档/卫健委"


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "unavailable",
        "findings": [message],
        "errors": [message],
        "summary": {},
    }


def _validate_roots(documents: Path, workspace: Path) -> str | None:
    if not documents.is_dir() or documents.is_symlink():
        return "Documents root must be a regular directory"
    if not workspace.is_dir() or workspace.is_symlink():
        return "Workspace root must be a regular directory"
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        return "Documents and Workspace roots must not overlap"
    return None


def _regular_files(root: Path) -> list[Path]:
    try:
        return sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink())
    except OSError:
        return []


def _age_days(path: Path, today: date) -> int:
    modified = datetime.fromtimestamp(path.stat().st_mtime).date()
    return max((today - modified).days, 0)


def inspect_daily_health(
    documents_root: Path,
    workspace_root: Path,
    *,
    domain_relative: str = DEFAULT_DOMAIN,
    today: date | None = None,
) -> dict[str, Any]:
    """Read the legacy health inputs without invoking or writing Documents scripts."""
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    error = _validate_roots(documents, workspace)
    if error:
        return _unavailable(error)

    domain = (documents / domain_relative).resolve()
    try:
        domain.relative_to(documents)
    except ValueError:
        return _unavailable("domain-relative must remain below Documents root")
    if not domain.is_dir() or domain.is_symlink():
        return _unavailable("daily health domain is missing")

    observed = date.today() if today is None else today
    knowledge = domain / "_knowledge"
    inbox = domain / "_storage" / "01-Inbox"
    control = domain / "_control"
    stale_knowledge = [path for path in _regular_files(knowledge) if path.suffix == ".md" and _age_days(path, observed) > 30]
    stale_inbox = [path for path in _regular_files(inbox) if not path.name.startswith(".") and _age_days(path, observed) > 7]
    manifest = inbox / "inbox-manifest.md"
    try:
        pending_inbox = manifest.read_text(encoding="utf-8").count("📥 待分类") if manifest.is_file() else 0
    except (OSError, UnicodeError):
        pending_inbox = 0
    try:
        signal_count = (control / "signals.md").read_text(encoding="utf-8").count("signal-")
    except (OSError, UnicodeError):
        signal_count = 0

    summary = {
        "stale_knowledge": len(stale_knowledge),
        "stale_inbox": len(stale_inbox),
        "pending_inbox": pending_inbox,
        "signals": signal_count,
    }
    findings: list[str] = []
    if stale_knowledge:
        findings.append(f"{len(stale_knowledge)} knowledge files exceed 30 days")
    if stale_inbox:
        findings.append(f"{len(stale_inbox)} inbox files exceed 7 days")
    if pending_inbox:
        findings.append(f"{pending_inbox} inbox items remain unclassified")
    findings.append("legacy governance and dashboard writers were not invoked")
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "domain": str(domain),
        "observed_on": observed.isoformat(),
        "writes_documents": False,
        "dashboard_write": "deferred",
        "summary": summary,
        "findings": findings,
        "errors": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--domain-relative", default=DEFAULT_DOMAIN)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = inspect_daily_health(args.documents_root, args.workspace_root, domain_relative=args.domain_relative)
    if args.evidence and result["status"] != "unavailable":
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            result = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{result['status']}: {len(result['findings'])} findings")
    return 0 if result["status"] == "ok" else (1 if result["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
