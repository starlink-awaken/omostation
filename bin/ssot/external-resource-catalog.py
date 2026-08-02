#!/usr/bin/env python3
"""Project dynamically discovered external resources without activating them.

The command is a read-only bridge from Agora's discovery boundary to human
surfaces. It emits safe descriptors, health freshness and explicit errors;
it never invokes providers, writes OMO state or accepts credentials.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "external-resource-catalog/v1"


class ExternalResourceCatalogInputError(ValueError):
    """Raised when the catalog projection cannot be built safely."""


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
            module.discover_entry_points,
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
) -> dict[str, Any]:
    """Collect an external-resource snapshot through Agora's boundary."""
    root = root.resolve()
    build_snapshot, discover = _load_agora(root)
    records = discover(entry_points)
    snapshot = build_snapshot(
        records,
        now=now or datetime.now(UTC),
        health_ttl_seconds=health_ttl_seconds,
    )
    if snapshot.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError("unexpected catalog schema")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--health-ttl-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    try:
        payload = collect_external_resources(
            args.root, health_ttl_seconds=args.health_ttl_seconds
        )
    except (ExternalResourceCatalogInputError, ValueError) as exc:
        print(f"external-resource-catalog: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
