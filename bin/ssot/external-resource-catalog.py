#!/usr/bin/env python3
"""Project and optionally observe dynamically discovered external resources.

The default command is a read-only bridge from Agora's discovery boundary to
human surfaces. ``--observe`` sends the safe projection through OMO's CLI
broker for append-only persistence; it never invokes provider business methods
or accepts credentials.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "external-resource-catalog/v1"


class ExternalResourceCatalogInputError(ValueError):
    """Raised when the catalog projection cannot be built safely."""


_OMO_COMMAND_TIMEOUT_SECONDS = 15


def _load_agora(root: Path):
    agora_src = root / "projects/agora/src"
    if not agora_src.exists():
        raise ExternalResourceCatalogInputError(
            f"Agora source is unavailable: {agora_src}"
        )
    try:
        module_path = agora_src / "agora/external_connections.py"
        spec = importlib.util.spec_from_file_location(
            "agora_external_connections_projection", module_path
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load Agora external connection boundary")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return (
            module.build_external_resource_catalog_snapshot,
            module.diff_external_resource_catalog_snapshots,
            module.discover_entry_points,
            module.evaluate_external_resource_catalog_snapshot,
        )
    except (ImportError, OSError) as exc:
        raise ExternalResourceCatalogInputError(
            "Agora external connection boundary is unavailable"
        ) from exc


def collect_external_resources(
    root: Path,
    *,
    entry_points: Iterable[Any] | None = None,
    now: datetime | None = None,
    health_ttl_seconds: int = 900,
    probe: bool = True,
    previous_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect an external-resource snapshot through Agora's boundary."""
    root = root.resolve()
    build_snapshot, diff_snapshots, discover, _ = _load_agora(root)
    records = discover(entry_points, probe=probe, mark_unprobed=not probe)
    snapshot = build_snapshot(
        records,
        now=now or datetime.now(UTC),
        health_ttl_seconds=health_ttl_seconds,
    )
    if snapshot.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError("unexpected catalog schema")
    if previous_snapshot is not None:
        snapshot["changes"] = diff_snapshots(previous_snapshot, snapshot)
    return snapshot


def evaluate_external_resources(
    root: Path,
    snapshot: Mapping[str, Any],
    *,
    capability: str,
    scene_binding: Mapping[str, Any],
    trace_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a safe catalog through Agora's shared decision contract."""
    root = root.resolve()
    _, _, _, evaluate_snapshot = _load_agora(root)
    return evaluate_snapshot(
        snapshot,
        capability,
        scene_binding,
        trace_id=trace_id,
        now=now or datetime.now(UTC),
    )


def _omo_command(root: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "omo.cli", *args]


def _omo_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    omo_src = str(root / "projects/omo/src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{omo_src}{os.pathsep}{existing}" if existing else omo_src
    )
    return environment


def _run_omo(
    root: Path, args: tuple[str, ...], *, input_text: str | None = None
) -> dict[str, Any]:
    completed = subprocess.run(
        _omo_command(root, *args),
        cwd=root,
        env=_omo_environment(root),
        input=input_text,
        capture_output=True,
        text=True,
        timeout=_OMO_COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise ExternalResourceCatalogInputError(
            completed.stderr.strip() or "OMO external resource observer is unavailable"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalResourceCatalogInputError(
            "OMO external resource observer returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalResourceCatalogInputError(
            "OMO external resource observer must return an object"
        )
    return payload


def observe_external_resources(
    root: Path,
    *,
    entry_points: Iterable[Any] | None = None,
    now: datetime | None = None,
    health_ttl_seconds: int = 900,
    probe: bool = True,
    previous_snapshot: Mapping[str, Any] | None = None,
    actor: str = "external-resource-observer",
    source_ref: str = "root:external-resource-catalog:observe",
) -> dict[str, Any]:
    """Observe a safe catalog through OMO's brokered persistence boundary."""
    root = root.resolve()
    if previous_snapshot is None:
        latest = _run_omo(root, ("external-resources", "latest", "--json"))
        previous_observation = latest.get("observation")
        if isinstance(previous_observation, Mapping):
            previous_snapshot = previous_observation.get("catalog")
    catalog = collect_external_resources(
        root,
        entry_points=entry_points,
        now=now,
        health_ttl_seconds=health_ttl_seconds,
        probe=probe,
        previous_snapshot=previous_snapshot,
    )
    result = _run_omo(
        root,
        (
            "external-resources",
            "observe",
            "--stdin",
            "--actor",
            actor,
            "--source-ref",
            source_ref,
        ),
        input_text=json.dumps(catalog, ensure_ascii=False, sort_keys=True),
    )
    observation = result.get("observation")
    if not isinstance(observation, Mapping):
        raise ExternalResourceCatalogInputError("OMO did not return an observation")
    return {
        "schema": "external-resource-observation-result/v1",
        "mode": "governed_observation",
        "catalog": catalog,
        "observation": observation,
        "status": result.get("status", "recorded"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--health-ttl-seconds", type=int, default=900)
    parser.add_argument(
        "--no-health-probe",
        action="store_true",
        help="只发现 descriptor，不调用显式只读 health_probe",
    )
    parser.add_argument(
        "--previous-snapshot",
        type=Path,
        help="读取上一份只读目录快照并附加变化报告，不写入任何状态",
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        help="通过 OMO CLI broker 追加受治理观察记录",
    )
    parser.add_argument("--actor", default="external-resource-observer")
    parser.add_argument(
        "--source-ref", default="root:external-resource-catalog:observe"
    )
    args = parser.parse_args(argv)
    try:
        previous_snapshot = None
        if args.previous_snapshot:
            try:
                previous_snapshot = json.loads(
                    args.previous_snapshot.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise ExternalResourceCatalogInputError(
                    f"cannot read previous snapshot: {args.previous_snapshot}"
                ) from exc
        if args.observe:
            payload = observe_external_resources(
                args.root,
                health_ttl_seconds=args.health_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
                actor=args.actor,
                source_ref=args.source_ref,
            )
        else:
            payload = collect_external_resources(
                args.root,
                health_ttl_seconds=args.health_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
            )
    except (ExternalResourceCatalogInputError, ValueError) as exc:
        print(f"external-resource-catalog: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
