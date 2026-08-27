"""Workspace-owned readiness check for the legacy Documents KOS schedule."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "documents.kos-preflight.v1"
LEGACY_EXECUTABLE = Path("/usr/local/bin/kos")
DEFAULT_DOMAINS = (
    "@学习进化",
    "@工作文档",
    "@驾驶舱",
    "@公共",
    "@个人",
    "@创意创作",
    "@OPC",
    "@家庭生活",
)


def _unavailable(message: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "status": "unavailable", "findings": [message], "errors": [message], "summary": {}}


def inspect_kos_schedule(
    documents_root: Path,
    workspace_root: Path,
    *,
    executable: Path | None = None,
    domain_relative: tuple[str, ...] = DEFAULT_DOMAINS,
) -> dict[str, Any]:
    """Check KOS schedule prerequisites without running ingest or writing Documents."""
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or not workspace.is_dir():
        return _unavailable("Documents and Workspace roots must be regular directories")
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        return _unavailable("Documents and Workspace roots must not overlap")
    command = (workspace / "bin/gac/kos" if executable is None else executable).expanduser().resolve()
    command_state = "ready" if command.is_file() and command.stat().st_mode & 0o111 else "missing"
    existing = [relative for relative in domain_relative if (documents / relative).is_dir()]
    missing = [relative for relative in domain_relative if relative not in existing]
    findings: list[str] = []
    if command_state == "missing":
        findings.append(f"legacy KOS executable is unavailable: {command}")
    if missing:
        findings.append(f"configured source domains are missing: {', '.join(missing)}")
    findings.append("ingest execution deferred until a verified Workspace KOS owner is selected")
    return {
        "schema": SCHEMA,
        "status": "findings" if findings else "ok",
        "documents_root": str(documents),
        "workspace_root": str(workspace),
        "legacy_executable": str(LEGACY_EXECUTABLE),
        "workspace_executable": str(command),
        "execution": "not_invoked",
        "writes_documents": False,
        "legacy_log_target": str(documents / "@驾驶舱/_generated/governance-cron.log"),
        "workspace_log_target": str(workspace / "runtime/cron/kos.stdout.log"),
        "summary": {"executable": command_state, "source_domains": len(existing), "missing_domains": len(missing), "writes_documents": False},
        "findings": findings,
        "errors": [],
    }


def run_kos_ingest(
    documents_root: Path,
    workspace_root: Path,
    *,
    domain_relative: tuple[str, ...] = DEFAULT_DOMAINS,
) -> int:
    """Run the canonical KOS ingest owner with Documents as read-only input."""
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or not workspace.is_dir():
        print(json.dumps(_unavailable("Documents and Workspace roots must be regular directories"), ensure_ascii=False))
        return 2
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        print(json.dumps(_unavailable("Documents and Workspace roots must not overlap"), ensure_ascii=False))
        return 2
    kairon_root = Path(__file__).resolve().parents[1] / "projects" / "knowledge" / "kairon"
    kos_cli = kairon_root / "packages" / "kos" / "kos-cli.py"
    if not kos_cli.is_file():
        print(json.dumps(_unavailable(f"canonical KOS CLI is missing: {kos_cli}"), ensure_ascii=False))
        return 2
    env = os.environ.copy()
    env["KOS_HOME"] = str(workspace / "kos")
    exit_code = 0
    results: list[dict[str, object]] = []
    for relative in domain_relative:
        source = documents / relative
        if not source.is_dir():
            results.append({"source": relative, "status": "missing"})
            exit_code = 1
            continue
        completed = subprocess.run(
            ["uv", "run", "--directory", str(kairon_root), "python", str(kos_cli), "ingest", str(source)],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
            check=False,
        )
        results.append({"source": relative, "status": "ok" if completed.returncode == 0 else "failed", "exit_code": completed.returncode})
        if completed.returncode != 0:
            exit_code = 1
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
    print(json.dumps({"schema": SCHEMA, "status": "ok" if exit_code == 0 else "findings", "execution": "ingest", "writes_documents": False, "results": results}, ensure_ascii=False, sort_keys=True))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--ingest", action="store_true", help="run canonical KOS ingest after readiness checks")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.ingest:
        return run_kos_ingest(args.documents_root, args.workspace_root)
    result = inspect_kos_schedule(args.documents_root, args.workspace_root, executable=args.executable)
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
