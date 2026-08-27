#!/usr/bin/env python3
"""Workspace-owned replacement for the legacy Documents minute watcher."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_MARKERS = ("domain-sync.py", "bridge-refresh.py", "session-brief.py", "weekly-verdict-generator.py")


@dataclass(frozen=True)
class WatchGroup:
    name: str
    paths: tuple[Path, ...]
    command: tuple[str, ...]
    environment: Mapping[str, str] = field(default_factory=dict)


def _owner_job(name: str, documents: Path, workspace: Path, evidence: str) -> tuple[str, ...]:
    return (
        sys.executable,
        str(ROOT / "bin/gac/documents-domain-owner-job.py"),
        name,
        "--json",
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        evidence,
    )


def watch_groups(documents_root: Path, workspace_root: Path) -> tuple[WatchGroup, ...]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    registry = documents / "@公共/_control/L4-DOMAIN-REGISTRY.yaml"
    manifest_paths = (registry, *sorted(documents.glob("@*/DOMAIN.yaml")), *sorted((documents / "@工作文档").glob("*/DOMAIN.yaml")))
    common = {"PYTHONPATH": os.pathsep.join((str(ROOT / "projects/omo/src"), str(ROOT / "projects/bus-foundation/src")))}
    return (
        WatchGroup(
            "domain-manifests",
            tuple(manifest_paths),
            (
                sys.executable,
                str(ROOT / "bin/gac/documents-domain-index.py"),
                "check",
                "--domain-registry",
                str(registry),
                "--index-path",
                str(documents / "@驾驶舱/_control/DOMAIN-INDEX.md"),
            ),
        ),
        WatchGroup(
            "workspace-state",
            (workspace / ".omo/state", workspace / "data/cards/cards.db"),
            _owner_job("bridge-preflight", documents, workspace, ".omo/_delivery/documents-plane/bridge-preflight-watch.json"),
        ),
        WatchGroup(
            "inbox-router",
            (documents / "_inbox",),
            (
                sys.executable,
                str(ROOT / "bin/mof/generate-brief.py"),
                "--write",
                "--if-changed",
            ),
            {"OMOSTATION_WORKSPACE_ROOT": str(workspace), "OMOSTATION_BRIEF_OUTPUT": str(workspace / "BRIEF.md")},
        ),
        WatchGroup("weekly-verdict", (workspace / "data/cards/cards.db",), (), common),
    )


WATCH_GROUPS = watch_groups(Path.home() / "Documents", Path(os.environ.get("WORKSPACE_ROOT", ROOT)))


def latest_mtime(paths: tuple[Path, ...]) -> float:
    latest = 0.0
    for path in paths:
        try:
            if path.is_file():
                latest = max(latest, path.stat().st_mtime)
            elif path.is_dir():
                latest = max((item.stat().st_mtime for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts), default=latest)
        except OSError:
            continue
    return latest


def dispatch_once(
    groups: tuple[WatchGroup, ...],
    *,
    stamps_path: Path,
    runner: Callable[[str, tuple[str, ...]], int],
) -> list[dict[str, object]]:
    try:
        stamps = json.loads(stamps_path.read_text(encoding="utf-8")) if stamps_path.is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        stamps = {}
    events: list[dict[str, object]] = []
    for group in groups:
        current = latest_mtime(group.paths)
        if current <= float(stamps.get(group.name, 0.0)):
            continue
        if group.command:
            code = runner(group.name, group.command)
            events.append({"group": group.name, "status": "ok" if code == 0 else "findings", "exit_code": code})
        else:
            events.append({"group": group.name, "status": "pending", "exit_code": None, "reason": "no Workspace verdict owner registered"})
        stamps[group.name] = current
    if events:
        stamps_path.parent.mkdir(parents=True, exist_ok=True)
        stamps_path.write_text(json.dumps(stamps, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--stamps", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    workspace = args.workspace_root.expanduser().resolve()
    stamps = (args.stamps or workspace / "runtime/.watch-dispatch-stamps.json").expanduser().resolve()
    groups = watch_groups(args.documents_root, workspace)

    def run(name: str, command: tuple[str, ...]) -> int:
        group = next(item for item in groups if item.name == name)
        environment = {**os.environ, "WORKSPACE_ROOT": str(workspace), **group.environment}
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, env=environment, check=False)
        tail = (result.stdout.strip().splitlines() or ["(no output)"])[-1]
        print(f"[workspace-watch {datetime.now(UTC).isoformat()}] {name}: {tail}", file=sys.stderr if args.json else sys.stdout)
        return result.returncode

    events = dispatch_once(groups, stamps_path=stamps, runner=run)
    payload = {"schema": "workspace.watch-dispatch.v1", "events": events, "status": "ok" if not events or all(event["status"] in {"ok", "pending"} for event in events) else "findings"}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
