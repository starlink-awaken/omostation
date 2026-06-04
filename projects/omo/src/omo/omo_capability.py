#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .omo_io import write_text_atomic, write_yaml_atomic


CAPABILITY_TYPES = {
    "capability",
    "skill",
    "tool",
    "plugin",
    "connector",
    "cli",
    "package",
}
PROTOCOLS = {"cli", "mcp", "api", "local", "file", "doc"}
LIFECYCLES = {"active", "experimental", "deprecated", "external"}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _omo(root: Path) -> Path:
    return root / ".omo"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def _capability_record(
    capability_id: str,
    capability_type: str,
    protocol: str,
    entrypoint: str,
    description: str,
    tags: list[str],
    scenario_tags: list[str] | None = None,
    lifecycle: str = "active",
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "type": capability_type,
        "protocol": protocol,
        "entrypoint": entrypoint,
        "lifecycle": lifecycle,
        "metadata": {
            "description": description,
            "version": "local",
            "tags": tags,
            "scenario_tags": scenario_tags or tags[:2],
            "source": source or entrypoint,
        },
    }


def _validate_capability(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "type", "protocol", "entrypoint", "lifecycle", "metadata"):
        if field not in record:
            errors.append(f"missing:{field}")
    if record.get("type") not in CAPABILITY_TYPES:
        errors.append(f"invalid_type:{record.get('type')}")
    if record.get("protocol") not in PROTOCOLS:
        errors.append(f"invalid_protocol:{record.get('protocol')}")
    if record.get("lifecycle") not in LIFECYCLES:
        errors.append(f"invalid_lifecycle:{record.get('lifecycle')}")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata_not_mapping")
    else:
        if not metadata.get("description"):
            errors.append("metadata_missing_description")
        if not isinstance(metadata.get("tags", []), list):
            errors.append("metadata_tags_not_list")
        if not isinstance(metadata.get("scenario_tags", []), list):
            errors.append("metadata_scenario_tags_not_list")
    return errors


def _project_capabilities(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    packages_root = root / "projects" / "kairon" / "packages"
    if packages_root.exists():
        for package in sorted(
            path for path in packages_root.iterdir() if path.is_dir()
        ):
            package_id = package.name.replace("_", "-")
            records.append(
                _capability_record(
                    f"kairon.{package_id}",
                    "package",
                    "local",
                    str(package.relative_to(root)),
                    f"Kairon package capability: {package_id}",
                    ["kairon", "package", package_id],
                    ["research-pipeline", "workspace-governance"],
                )
            )

    for project_name in ("agentmesh", "gbrain", "SharedBrain"):
        project = root / "projects" / project_name
        if not project.exists():
            continue
        records.append(
            _capability_record(
                f"project.{project_name}",
                "capability",
                "local",
                str(project.relative_to(root)),
                f"Workspace project capability: {project_name}",
                ["project", project_name.lower()],
                ["workspace-governance"],
            )
        )
        for child in sorted(
            path
            for path in project.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )[:12]:
            records.append(
                _capability_record(
                    f"{project_name.lower()}.{child.name.replace('_', '-')}",
                    "capability",
                    "local",
                    str(child.relative_to(root)),
                    f"{project_name} component capability: {child.name}",
                    [project_name.lower(), "component", child.name.lower()],
                    ["research-pipeline", "workspace-governance"],
                )
            )

    scripts = [
        "omo",
        "omo_worker.py",
        "omo_governance.py",
        "omo_discovery.py",
        "omo_skill.py",
        "sync_omo_state.py",
        "check-system-consistency.sh",
        "daily-backup.sh",
        "restore-from-backup.sh",
        "cost_track_org.py",
    ]
    for script_name in scripts:
        script = root / "scripts" / script_name
        if script.exists():
            records.append(
                _capability_record(
                    f"cli.{script.stem.replace('_', '-')}",
                    "cli",
                    "cli",
                    str(script.relative_to(root)),
                    f"OMO CLI/script capability: {script_name}",
                    ["omo", "cli", script.stem],
                    ["workspace-governance"],
                )
            )
    return records


def _sharedwork_sample() -> list[dict[str, Any]]:
    candidates = [
        ("GitNexus", "repository intelligence and graph analysis"),
        ("Graphify", "graph extraction and visualization"),
        ("UltraRAG", "retrieval augmented generation"),
        ("Firecrawl", "web crawling and extraction"),
        ("MinerU", "document parsing and mining"),
        ("AgentLaboratory", "agent research workflow"),
        ("nuwa-skill", "skill authoring and packaging"),
        ("OpenManus", "agent task execution reference"),
        ("ContextHub", "context sharing reference"),
        ("TrustGraph", "context core and graph memory reference"),
    ]
    return [
        _capability_record(
            f"sharedwork.{name.lower().replace('-', '_')}",
            "connector",
            "doc",
            f"SharedWork/{name}",
            description,
            ["sharedwork", "deferred", name.lower()],
            ["phase14-candidate"],
            lifecycle="external",
            source=f"SharedWork/{name}",
        )
        for name, description in candidates
    ]


def _system_packages(root: Path) -> list[dict[str, Any]]:
    package_files = [
        root / "projects" / "kairon" / "pyproject.toml",
        root / "projects" / "agentmesh" / "package.json",
        root / "projects" / "gbrain" / "package.json",
        root / "projects" / "SharedBrain" / "pyproject.toml",
    ]
    records: list[dict[str, Any]] = []
    for package_file in package_files:
        if not package_file.exists():
            continue
        records.append(
            {
                "id": package_file.parent.name,
                "manager": "python" if package_file.name == "pyproject.toml" else "bun",
                "manifest": str(package_file.relative_to(root)),
                "version": "declared-in-manifest",
                "status": "declared",
            }
        )
    return records


def _agent_clis(root: Path) -> list[dict[str, str]]:
    candidates = [
        root / "scripts" / "omo",
        root / "scripts" / "sync-omo-state.sh",
        root / "kos-infra" / "kos",
        root / "projects" / "kairon" / "packages" / "kos" / "kos-cli.py",
        root / "projects" / "kairon" / "packages" / "kos" / "kairon-cli.py",
    ]
    clis: list[dict[str, str]] = []
    for cli in candidates:
        if cli.exists():
            clis.append(
                {
                    "name": cli.stem,
                    "entrypoint": str(cli.relative_to(root)),
                    "description": f"Workspace CLI entrypoint for {cli.stem}",
                }
            )
    return clis


def _write_registry_index(root: Path) -> None:
    index = """# Capability registry

> Status: active
> Owner: Phase 12 capability ecosystem foundation

## Files

| File | Purpose |
|------|---------|
| `projects-capabilities.yaml` | Core workspace capability records |
| `sharedwork-sample.yaml` | External/SharedWork sample records for Phase 14 triage |
| `system-packages.yaml` | Package baseline records |
| `agent-clis.yaml` | Agent CLI baseline |
| `pilot-contract.yaml` | Selected Phase 12 pilot interface contract |
| `article-samples.yaml` | Article ingestion policy samples |
| `package-baseline.yaml` | Package dry-run baseline |

## Rule

Registry records are evidence for discovery and binding. They do not authorize live mutation or external installation.
"""
    write_text_atomic(_omo(root) / "registry" / "INDEX.md", index)


def scan_command(args: argparse.Namespace) -> int:
    root = _root()
    omo = _omo(root)
    records = _project_capabilities(root)
    sharedwork = _sharedwork_sample()
    packages = _system_packages(root)
    clis = _agent_clis(root)

    if args.write:
        (omo / "registry").mkdir(parents=True, exist_ok=True)
        _write_registry_index(root)
        write_yaml_atomic(
            omo / "registry" / "projects-capabilities.yaml", {"capabilities": records}
        )
        write_yaml_atomic(
            omo / "registry" / "sharedwork-sample.yaml", {"capabilities": sharedwork}
        )
        write_yaml_atomic(
            omo / "registry" / "system-packages.yaml", {"packages": packages}
        )
        write_yaml_atomic(omo / "registry" / "agent-clis.yaml", {"clis": clis})

    print(
        json.dumps(
            {
                "capabilities": len(records),
                "sharedwork_samples": len(sharedwork),
                "packages": len(packages),
                "clis": len(clis),
                "written": bool(args.write),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _load_all_capabilities(root: Path) -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    for rel in ("projects-capabilities.yaml", "sharedwork-sample.yaml"):
        payload = _load_yaml(_omo(root) / "registry" / rel) or {}
        capabilities.extend(payload.get("capabilities", []))
    return capabilities


def register_command(args: argparse.Namespace) -> int:
    root = _root()
    payload = _load_yaml(Path(args.file))
    records = payload.get(
        "capabilities", payload if isinstance(payload, list) else [payload]
    )
    errors: dict[str, list[str]] = {}
    for record in records:
        record_errors = _validate_capability(record)
        if record_errors:
            errors[record.get("id", "<missing-id>")] = record_errors
    if errors:
        raise SystemExit(
            json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False)
        )

    target = _omo(root) / "registry" / "manual-capabilities.yaml"
    existing = _load_yaml(target) or {"capabilities": []}
    by_id = {record["id"]: record for record in existing.get("capabilities", [])}
    for record in records:
        by_id[record["id"]] = record
    write_yaml_atomic(
        target, {"capabilities": sorted(by_id.values(), key=lambda item: item["id"])}
    )
    print(
        json.dumps({"status": "registered", "count": len(records)}, ensure_ascii=False)
    )
    return 0


def discover_command(args: argparse.Namespace) -> int:
    root = _root()
    records = _load_all_capabilities(root)
    if args.type:
        records = [record for record in records if record.get("type") == args.type]
    if args.tag:
        records = [
            record
            for record in records
            if args.tag in record.get("metadata", {}).get("tags", [])
            or args.tag in record.get("metadata", {}).get("scenario_tags", [])
        ]
    if args.lifecycle:
        records = [
            record for record in records if record.get("lifecycle") == args.lifecycle
        ]
    print(
        json.dumps(
            {"count": len(records), "capabilities": records},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _scenario_bindings(root: Path, scenario_path: Path) -> dict[str, Any]:
    scenario = _load_yaml(scenario_path)
    capabilities = {record["id"]: record for record in _load_all_capabilities(root)}
    missing = [
        capability_id
        for capability_id in scenario.get("capabilities", [])
        if capability_id not in capabilities
    ]
    return {
        "scenario_id": scenario["id"],
        "status": "blocked" if missing else "ready",
        "missing_capabilities": missing,
        "bindings": [
            {
                "capability_id": capability_id,
                "entrypoint": capabilities[capability_id]["entrypoint"],
                "protocol": capabilities[capability_id]["protocol"],
            }
            for capability_id in scenario.get("capabilities", [])
            if capability_id in capabilities
        ],
    }


def bind_command(args: argparse.Namespace) -> int:
    root = _root()
    result = _scenario_bindings(root, Path(args.scenario))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 2


def trace_command(args: argparse.Namespace) -> int:
    root = _root()
    scenario_path = Path(args.scenario)
    result = _scenario_bindings(root, scenario_path)
    trace = {
        "trace_id": f"{result['scenario_id']}-trace",
        "created_at": _utc_now(),
        "mode": "dry-run",
        "scenario": str(
            scenario_path.relative_to(root)
            if scenario_path.is_absolute()
            else scenario_path
        ),
        **result,
        "steps": [
            {
                "step": index + 1,
                "capability_id": binding["capability_id"],
                "status": "simulated",
                "entrypoint": binding["entrypoint"],
            }
            for index, binding in enumerate(result["bindings"])
        ],
    }
    output = Path(args.output)
    write_yaml_atomic(output, trace)
    print(
        json.dumps(
            {"status": trace["status"], "output": str(output)}, ensure_ascii=False
        )
    )
    return 0 if trace["status"] == "ready" else 2


def pkg_sync_command(args: argparse.Namespace) -> int:
    if not args.dry_run:
        raise SystemExit("Phase 12 only supports pkg sync --dry-run")
    root = _root()
    baseline = _load_yaml(_omo(root) / "registry" / "system-packages.yaml") or {
        "packages": []
    }
    report = {
        "mode": "dry-run",
        "created_at": _utc_now(),
        "mutations_applied": 0,
        "packages_checked": len(baseline.get("packages", [])),
        "diffs": [
            {
                "id": package["id"],
                "manifest": package["manifest"],
                "status": "declared-no-mutation",
            }
            for package in baseline.get("packages", [])
        ],
    }
    output = Path(args.output)
    write_yaml_atomic(output, report)
    print(json.dumps({"status": "dry-run", "output": str(output)}, ensure_ascii=False))
    return 0


def registry_browse_command(args: argparse.Namespace) -> int:
    root = _root()
    records = _load_all_capabilities(root)
    counts: dict[str, int] = {}
    for record in records:
        counts[record["type"]] = counts.get(record["type"], 0) + 1
    print(
        json.dumps(
            {"total": len(records), "by_type": counts}, ensure_ascii=False, indent=2
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omo-capability")
    subparsers = parser.add_subparsers(dest="area", required=True)

    capability = subparsers.add_parser("capability")
    capability_sub = capability.add_subparsers(dest="command", required=True)
    scan = capability_sub.add_parser("scan")
    scan.add_argument("--write", action="store_true")
    scan.set_defaults(func=scan_command)
    register = capability_sub.add_parser("register")
    register.add_argument("file")
    register.set_defaults(func=register_command)
    discover = capability_sub.add_parser("discover")
    discover.add_argument("--type", choices=sorted(CAPABILITY_TYPES))
    discover.add_argument("--tag")
    discover.add_argument("--lifecycle", choices=sorted(LIFECYCLES))
    discover.set_defaults(func=discover_command)
    bind = capability_sub.add_parser("bind")
    bind.add_argument("--scenario", required=True)
    bind.set_defaults(func=bind_command)

    registry = subparsers.add_parser("registry")
    registry_sub = registry.add_subparsers(dest="command", required=True)
    browse = registry_sub.add_parser("browse")
    browse.set_defaults(func=registry_browse_command)

    scenario = subparsers.add_parser("scenario")
    scenario_sub = scenario.add_subparsers(dest="command", required=True)
    trace = scenario_sub.add_parser("trace")
    trace.add_argument("--scenario", required=True)
    trace.add_argument("--output", required=True)
    trace.set_defaults(func=trace_command)

    pkg = subparsers.add_parser("pkg")
    pkg_sub = pkg.add_subparsers(dest="command", required=True)
    sync = pkg_sub.add_parser("sync")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--output", default=".omo/evidence/phase12/package-dry-run.yaml")
    sync.set_defaults(func=pkg_sync_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
