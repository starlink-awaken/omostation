#!/usr/bin/env python3
"""Produce a verifiable receipt for topological affected-project calculation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "affected-graph-receipt/v1"
WORKSPACE_ROOT_PROJECT = "workspace-root"
DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


class AffectedGraphError(ValueError):
    """Raised when an affected graph cannot be proved from the layer contract."""


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def load_layer_contract(workspace_root: Path) -> tuple[dict[str, Any], bytes]:
    path = workspace_root / "docs" / "layer-contract.yaml"
    if not path.is_file():
        raise AffectedGraphError(f"layer contract does not exist: {path}")
    raw = path.read_bytes()
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise AffectedGraphError(f"invalid layer contract: {path}")
    return payload, raw


def get_project_layers(layer_contract: dict[str, Any]) -> dict[str, str]:
    project_layers: dict[str, str] = {}
    for layer, info in layer_contract.get("layers", {}).items():
        for project in info.get("projects", []):
            project_layers[str(project)] = str(layer)
    return project_layers


def build_dependency_graph(
    layer_contract: dict[str, Any], project_layers: dict[str, str]
) -> dict[str, set[str]]:
    graph = {project: set() for project in project_layers}
    downstream_layers = {layer: set() for layer in layer_contract.get("layers", {})}
    rules = layer_contract.get("dependency_rules", {}).get("allowed_directions", [])
    for rule in rules:
        for downstream in rule.get("from", []):
            for upstream in rule.get("to", []):
                downstream_layers.setdefault(str(upstream), set()).add(str(downstream))
    for upstream_project, upstream_layer in project_layers.items():
        for downstream_layer in downstream_layers.get(upstream_layer, set()):
            graph[upstream_project].update(
                project
                for project, layer in project_layers.items()
                if layer == downstream_layer
            )
    return graph


def calculate_affected(
    changed_projects: list[str],
    layer_contract: dict[str, Any],
) -> list[str]:
    project_layers = get_project_layers(layer_contract)
    known_projects = set(project_layers) | {WORKSPACE_ROOT_PROJECT}
    unknown = set(changed_projects) - known_projects
    if unknown:
        raise AffectedGraphError("unknown project(s): " + ", ".join(sorted(unknown)))
    graph = build_dependency_graph(layer_contract, project_layers)
    affected = set(changed_projects)
    queue = [
        project for project in changed_projects if project != WORKSPACE_ROOT_PROJECT
    ]
    while queue:
        current = queue.pop(0)
        for downstream in graph[current]:
            if downstream not in affected:
                affected.add(downstream)
                queue.append(downstream)
    return sorted(affected)


def create_receipt(
    changed_projects: list[str], workspace_root: str | Path
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    changed = sorted(set(changed_projects))
    if not changed:
        raise AffectedGraphError("at least one changed project is required")
    layer_contract, contract_bytes = load_layer_contract(workspace)
    unsigned = {
        "schema": SCHEMA,
        "changed_projects": changed,
        "affected_projects": calculate_affected(changed, layer_contract),
        "layer_contract_digest": hashlib.sha256(contract_bytes).hexdigest(),
    }
    return {
        **unsigned,
        "receipt_hash": hashlib.sha256(canonical_json(unsigned).encode()).hexdigest(),
    }


def write_receipt_exclusive(
    output: str | Path, workspace_root: str | Path, serialized: str
) -> Path:
    workspace = Path(workspace_root).resolve()
    output_ref = str(output)
    relative = Path(output_ref)
    if (
        not output_ref
        or relative.is_absolute()
        or "//" in output_ref
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.as_posix() != output_ref
    ):
        raise AffectedGraphError(
            "receipt output must be canonical workspace-relative"
        )
    candidate = (workspace / relative).absolute()

    current = workspace
    for part in relative.parent.parts:
        current = current / part
        if current.is_symlink():
            raise AffectedGraphError("receipt output parent must not contain symlinks")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.parent.resolve() != candidate.parent.absolute():
        raise AffectedGraphError("receipt output parent must not contain symlinks")
    if os.path.lexists(candidate):
        raise AffectedGraphError(f"receipt output already exists: {candidate}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="x",
            encoding="utf-8",
            dir=candidate.parent,
            prefix=f".{candidate.name}.",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_path, candidate)
    except FileExistsError as exc:
        raise AffectedGraphError(f"receipt output already exists: {candidate}") from exc
    except OSError as exc:
        raise AffectedGraphError(f"cannot publish receipt output: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-projects", nargs="+", required=True)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Workspace root containing docs/layer-contract.yaml",
    )
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = create_receipt(args.changed_projects, args.workspace_root)
        serialized = canonical_json(receipt)
        if args.output:
            write_receipt_exclusive(args.output, args.workspace_root, serialized)
    except AffectedGraphError as exc:
        print(f"affected-graph: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(serialized)
    else:
        for project in receipt["affected_projects"]:
            print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
