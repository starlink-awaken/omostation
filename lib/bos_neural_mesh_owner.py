"""Fail-closed Workspace owner for the legacy BOS Neural Mesh entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "documents.bos-neural-mesh-owner.v1"
DEFAULT_LEGACY_RUNNER = Path("@公共/_runtime/bos-neural-mesh-runner.py")
DEFAULT_LEGACY_STATE = Path("@公共/_runtime/bos-neural-mesh-state.sqlite")


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "unavailable",
        "invoked": False,
        "connector_invocations": 0,
        "findings": [message],
        "errors": [message],
        "summary": {},
    }


def inspect_bos_owner(
    documents_root: Path,
    workspace_root: Path,
    *,
    legacy_runner: Path | None = None,
    legacy_state_db: Path | None = None,
) -> dict[str, Any]:
    """Inspect BOS retirement readiness without running any legacy connector."""
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or not workspace.is_dir():
        return _unavailable("Documents and Workspace roots must be regular directories")
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        return _unavailable("Documents and Workspace roots must not overlap")

    old_runner = (documents / DEFAULT_LEGACY_RUNNER if legacy_runner is None else legacy_runner).expanduser().resolve()
    old_state = (documents / DEFAULT_LEGACY_STATE if legacy_state_db is None else legacy_state_db).expanduser().resolve()
    workspace_state = (workspace / "runtime/bos-neural-mesh-state.sqlite").resolve()
    findings: list[str] = []
    if old_runner.is_file():
        findings.append("legacy BOS runner remains in Documents and is not an accepted Workspace owner")
    if old_state.exists():
        findings.append("legacy BOS state DB remains in Documents and requires a verified migration/rollback")
    findings.append("BOS connector execution is fail-closed until every step has an accepted Workspace owner")
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "legacy_runner": "present" if old_runner.is_file() else "absent",
        "legacy_runner_path": str(old_runner),
        "legacy_state_db": "present" if old_state.exists() else "absent",
        "legacy_state_db_path": str(old_state),
        "state_db": str(workspace_state),
        "state_owner": "workspace",
        "invoked": False,
        "connector_invocations": 0,
        "writes_documents": False,
        "findings": findings,
        "errors": [],
        "summary": {"legacy_runner": "present" if old_runner.is_file() else "absent", "legacy_state_db": "present" if old_state.exists() else "absent", "execution": "blocked"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = inspect_bos_owner(args.documents_root, args.workspace_root)
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
