#!/usr/bin/env python3
"""Project and optionally observe dynamically discovered external resources.

The default command is a read-only bridge from Agora's discovery boundary to
human surfaces. ``--observe`` sends the safe projection through OMO's CLI
broker for append-only persistence; it never invokes provider business methods
or accepts credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "external-resource-catalog/v1"
DIRECTORY_SCHEMA = "external-resource-directory/v1"


class ExternalResourceCatalogInputError(ValueError):
    """Raised when the catalog projection cannot be built safely."""


_OMO_COMMAND_TIMEOUT_SECONDS = 15
DEFAULT_CATALOG_TTL_SECONDS = 3600


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _directory_next_step(resource: Mapping[str, Any]) -> str:
    """Return a deterministic expansion action without mutating lifecycle state."""
    availability = str(resource.get("availability") or "").strip().lower()
    lifecycle = str(resource.get("lifecycle") or "").strip().lower()
    mode = str(resource.get("mode") or "").strip().lower()
    health = resource.get("health")
    health_status = str(health.get("status") or "").strip().lower() if isinstance(health, Mapping) else ""

    if availability in {"unavailable", "stale"} or health_status in {"unhealthy", "unknown", ""}:
        return "health_probe"
    if availability == "proposal_only" or mode == "proposal_only":
        return "proposal_or_evaluation"
    if lifecycle == "discovered":
        return "sandbox"
    if lifecycle == "sandbox":
        return "scene_card_and_permission_review"
    if lifecycle == "admitted":
        return "activation_review"
    if lifecycle == "degraded":
        return "health_recovery_or_quarantine"
    if lifecycle == "quarantined":
        return "quarantine_review"
    if lifecycle == "retired":
        return "retired"
    return "route_evaluation"


def build_external_resource_directory_snapshot(
    catalog: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Build a capability-oriented, read-only projection from one catalog.

    The catalog remains the discovery truth. This projection only answers which
    capabilities are represented, their current safe availability, and the next
    governed expansion step; it never loads providers or changes lifecycle.
    """
    if catalog.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError("directory requires an external-resource catalog")
    raw_resources = catalog.get("resources", [])
    if not isinstance(raw_resources, list):
        raise ExternalResourceCatalogInputError("catalog resources must be a list")

    resources: list[dict[str, Any]] = []
    capability_index: dict[str, dict[str, list[str]]] = {}
    kind_index: dict[str, list[str]] = {}
    next_steps: list[dict[str, str]] = []
    for item in raw_resources:
        if not isinstance(item, Mapping):
            raise ExternalResourceCatalogInputError("catalog resource must be an object")
        resource_id = str(item.get("id") or "").strip()
        if not resource_id:
            raise ExternalResourceCatalogInputError("catalog resource is missing id")
        capabilities = sorted(
            {str(capability).strip() for capability in item.get("capabilities", []) if str(capability).strip()}
        )
        availability = str(item.get("availability") or "unavailable").strip().lower()
        health = item.get("health") if isinstance(item.get("health"), Mapping) else {}
        resource = {
            "id": resource_id,
            "kind": str(item.get("kind") or "unknown"),
            "provider": str(item.get("provider") or "unknown"),
            "capabilities": capabilities,
            "lifecycle": str(item.get("lifecycle") or "unknown"),
            "availability": availability,
            "mode": str(item.get("mode") or ""),
            "data_classification": str(item.get("data_classification") or ""),
            "permission_ref": str(item.get("permission_ref") or ""),
            "health": {
                "status": str(health.get("status") or "unknown"),
                "observed_at": health.get("observed_at"),
                "source": health.get("source"),
            },
            "reason_codes": sorted(
                {str(reason).strip() for reason in item.get("reason_codes", []) if str(reason).strip()}
            ),
            "next_step": _directory_next_step(item),
        }
        resources.append(resource)
        kind_index.setdefault(resource["kind"], []).append(resource_id)
        for capability in capabilities:
            bucket = capability_index.setdefault(
                capability, {"resource_ids": [], "available_resource_ids": []}
            )
            bucket["resource_ids"].append(resource_id)
            if availability == "available":
                bucket["available_resource_ids"].append(resource_id)
        next_steps.append({"resource_id": resource_id, "next_step": resource["next_step"]})

    for bucket in capability_index.values():
        bucket["resource_ids"].sort()
        bucket["available_resource_ids"].sort()
    for resource_ids in kind_index.values():
        resource_ids.sort()
    catalog_state = dict(catalog)
    catalog_state.pop("observed_at", None)
    directory = {
        "schema": DIRECTORY_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "observed_at": (now or datetime.now(UTC)).isoformat(),
        "catalog_digest": str(catalog.get("catalog_digest") or _canonical_digest(catalog_state)),
        "resources": resources,
        "capability_index": capability_index,
        "kind_index": kind_index,
        "next_steps": sorted(next_steps, key=lambda item: item["resource_id"]),
        "summary": {
            "resource_count": len(resources),
            "capability_count": len(capability_index),
            "kind_count": len(kind_index),
            "available_count": sum(item["availability"] == "available" for item in resources),
            "proposal_only_count": sum(item["availability"] == "proposal_only" for item in resources),
            "unavailable_count": sum(item["availability"] in {"unavailable", "stale"} for item in resources),
            "next_step_counts": {
                step: sum(item["next_step"] == step for item in next_steps)
                for step in sorted({item["next_step"] for item in next_steps})
            },
        },
        "catalog_errors": list(catalog.get("errors", [])) if isinstance(catalog.get("errors"), list) else [],
        "changes": catalog.get("changes") if isinstance(catalog.get("changes"), Mapping) else None,
        "policy": {
            "source": "external-resource-catalog/v1",
            "side_effects": "disabled",
            "next_step_semantics": "human_or_governed_review_only",
        },
    }
    digest_state = dict(directory)
    digest_state.pop("observed_at", None)
    directory["directory_digest"] = _canonical_digest(digest_state)
    return directory


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
    catalog_ttl_seconds: int = DEFAULT_CATALOG_TTL_SECONDS,
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
        catalog_ttl_seconds=catalog_ttl_seconds,
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
    catalog_ttl_seconds: int = DEFAULT_CATALOG_TTL_SECONDS,
    probe: bool = True,
    previous_snapshot: Mapping[str, Any] | None = None,
    actor: str = "external-resource-observer",
    source_ref: str = "root:external-resource-catalog:observe",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Observe a safe catalog through OMO's brokered persistence boundary."""
    root = root.resolve()
    started_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    started_clock = time.perf_counter()
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
        catalog_ttl_seconds=catalog_ttl_seconds,
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
    resources = [item for item in catalog.get("resources", []) if isinstance(item, Mapping)]
    health_statuses = [
        str((item.get("health") or {}).get("status") or "").strip().lower()
        for item in resources
    ]
    availability = [str(item.get("availability") or "").strip().lower() for item in resources]
    probe_latencies = [
        float((item.get("health") or {}).get("latency_ms"))
        for item in resources
        if isinstance((item.get("health") or {}).get("latency_ms"), (int, float))
        and not isinstance((item.get("health") or {}).get("latency_ms"), bool)
    ]
    unavailable_count = sum(value in {"unavailable", "stale"} for value in availability)
    degraded_count = sum(
        value == "degraded" or health == "degraded"
        for value, health in zip(availability, health_statuses)
    )
    healthy_count = max(0, len(resources) - unavailable_count - degraded_count)
    errors = catalog.get("errors", [])
    error_count = len(errors) if isinstance(errors, list) else 0
    result_state = (
        "unavailable"
        if not resources
        else "degraded"
        if error_count or unavailable_count
        else "succeeded"
    )
    finished_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    catalog_digest = str(observation.get("catalog_digest") or "").strip()
    observation_run = _run_omo(
        root,
        ("external-resources", "record-observation-run", "--stdin"),
        input_text=json.dumps(
            {
                "schema": "external-resource-observation-run/v1",
                "run_id": run_id or f"external-observation-run:{catalog_digest[:32]}",
                "trace_id": f"external-observation:{catalog_digest[:24]}",
                "activation": "forbidden",
                "provider_business_invocation": False,
                "health_probe_invocation": probe,
                "started_at": started_at,
                "finished_at": finished_at,
                "catalog_observation_id": str(observation.get("observation_id") or ""),
                "catalog_digest": catalog_digest,
                "result_state": result_state,
                "summary": {
                    "resource_count": len(resources),
                    "healthy_count": healthy_count,
                    "degraded_count": degraded_count,
                    "unavailable_count": unavailable_count,
                    "error_count": error_count,
                    "probe_count": len(resources) if probe else 0,
                    "probe_failure_count": sum(
                        health in {"unhealthy", ""} or latency is None
                        for health, latency in zip(
                            health_statuses,
                            [
                                (item.get("health") or {}).get("latency_ms")
                                for item in resources
                            ],
                        )
                    )
                    if probe
                    else 0,
                },
                "latency": {
                    "duration_ms": round((time.perf_counter() - started_clock) * 1000, 3),
                    "probe_latency_ms_sum": round(sum(probe_latencies), 3) if probe_latencies else None,
                    "probe_latency_ms_max": round(max(probe_latencies), 3) if probe_latencies else None,
                },
                "cost": {
                    "state": "unmetered",
                    "amount": None,
                    "currency": "USD",
                    "basis": "catalog discovery and read-only health probes; provider billing not observed",
                },
                "actor": actor,
                "source_ref": source_ref,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    return {
        "schema": "external-resource-observation-result/v1",
        "mode": "governed_observation",
        "catalog": catalog,
        "observation": observation,
        "observation_run": observation_run.get("receipt"),
        "status": result.get("status", "recorded"),
        "observation_run_status": observation_run.get("status", "recorded"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--health-ttl-seconds", type=int, default=900)
    parser.add_argument(
        "--catalog-ttl-seconds",
        type=int,
        default=DEFAULT_CATALOG_TTL_SECONDS,
        help="目录快照在进入 activation preflight 前的最大有效时长",
    )
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
    parser.add_argument(
        "--directory",
        action="store_true",
        help="将只读目录转换为 capability directory，不执行观察或激活",
    )
    parser.add_argument("--actor", default="external-resource-observer")
    parser.add_argument(
        "--source-ref", default="root:external-resource-catalog:observe"
    )
    parser.add_argument("--run-id", help="稳定的只读观察运行标识，用于重试幂等")
    args = parser.parse_args(argv)
    try:
        if args.observe and args.directory:
            raise ExternalResourceCatalogInputError(
                "--directory cannot be combined with --observe"
            )
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
                catalog_ttl_seconds=args.catalog_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
                actor=args.actor,
                source_ref=args.source_ref,
                run_id=args.run_id,
            )
        else:
            catalog = collect_external_resources(
                args.root,
                health_ttl_seconds=args.health_ttl_seconds,
                catalog_ttl_seconds=args.catalog_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
            )
            payload = (
                build_external_resource_directory_snapshot(catalog)
                if args.directory
                else catalog
            )
    except (ExternalResourceCatalogInputError, ValueError) as exc:
        print(f"external-resource-catalog: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
