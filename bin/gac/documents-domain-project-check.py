"""Validate the Workspace binding for standalone Documents domain projects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
L4_SRC = ROOT / "projects" / "l4-kernel" / "src"
if str(L4_SRC) not in sys.path:
    sys.path.insert(0, str(L4_SRC))

from l4_kernel.manifest_registry import ManifestRegistry

_LOGICAL_BINDING_REGISTRY = "Workspace binding registry `documents-domain-projects`"
_PHYSICAL_BINDING_REGISTRY = re.compile(
    r"(?:/Users/[^/]+/(?:ws-[^/]+|Workspace)|~/Workspace)/\.omo/_truth/registry/"
    r"documents-domain-projects\.yaml"
)
_LOCAL_EXECUTION = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?`?(?:python(?:3)?|bash|sh|zsh|node|bun|uv\s+run)\b"
    r"[^\n]*(?:_runtime|_control|\.kems/_scripts)"
)


def _check_gateway_file(path: Path, domain_id: str) -> list[str]:
    """Validate one client projection without interpreting domain content."""

    label = f"{domain_id}/{path.name}"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{label} unavailable: {exc}"]

    errors: list[str] = []
    if len(text.splitlines()) >= 80:
        errors.append(f"{label} must remain under 80 lines")
    if "DOMAIN.yaml" not in text or "SSOT" not in text:
        errors.append(f"{label} must point to DOMAIN.yaml as identity SSOT")
    if f'domain_context(domain_id="{domain_id}")' not in text:
        errors.append(f"{label} must call domain_context for {domain_id}")
    if _LOGICAL_BINDING_REGISTRY not in text or _PHYSICAL_BINDING_REGISTRY.search(text):
        errors.append(f"{label} must reference the logical Workspace binding registry")
    if "degraded" not in text or "默认只读" not in text:
        errors.append(f"{label} must define degraded and default-read-only behavior")
    if "ChatGPT Web" not in text:
        errors.append(f"{label} must state the ChatGPT Web remote-plugin boundary")
    if _LOCAL_EXECUTION.search(text):
        errors.append(f"{label} instructs Documents-local execution")
    return errors


def check_domain_projects(
    domain_registry_path: Path,
    project_registry_path: Path,
    gateway_domain_ids: Sequence[str] = (),
) -> dict[str, object]:
    """Return a stable, read-only consistency report for both registries."""

    errors: list[str] = []
    try:
        registry = ManifestRegistry.load(domain_registry_path)
        manifests = registry
        manifest_ids = [manifest.id for manifest in manifests.list_all()]
    except (
        OSError,
        UnicodeError,
        TypeError,
        ValueError,
    ) as exc:  # l4-kernel owns detailed errors
        return {
            "ok": False,
            "domain_count": 0,
            "errors": [f"domain registry invalid: {exc}"],
        }

    try:
        raw = yaml.safe_load(project_registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return {
            "ok": False,
            "domain_count": len(manifest_ids),
            "errors": [f"project registry invalid: {exc}"],
        }
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "domain_count": len(manifest_ids),
            "errors": ["project registry must be a mapping"],
        }

    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
        errors.append("profiles must be a mapping")
    workspace_mcp = raw.get("workspace_mcp")
    if not isinstance(workspace_mcp, dict):
        workspace_mcp = {}
        errors.append("workspace_mcp must be a mapping")
    read_tools = workspace_mcp.get("read_tools")
    if not isinstance(read_tools, list) or not all(
        isinstance(item, str) and item for item in read_tools
    ):
        read_tool_set: set[str] = set()
        errors.append("workspace_mcp.read_tools must be a string list")
    else:
        read_tool_set = set(read_tools)
    routes = raw.get("capability_routes")
    if not isinstance(routes, dict):
        routes = {}
        errors.append("capability_routes must be a mapping")
    clients = raw.get("clients")
    gateway_files: list[str] = []
    if not isinstance(clients, dict):
        errors.append("clients must be a mapping")
    else:
        gateway_files = sorted(
            {
                instruction_file
                for client in clients.values()
                if isinstance(client, dict)
                and isinstance(instruction_file := client.get("instruction_file"), str)
                and instruction_file
            }
        )

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"profiles.{profile_id} must be a mapping")
            continue
        tools = profile.get("allowed_workspace_tools")
        if not isinstance(tools, list) or not all(
            isinstance(item, str) and item for item in tools
        ):
            errors.append(
                f"profiles.{profile_id}.allowed_workspace_tools must be a string list"
            )
            continue
        unknown_tools = sorted(set(tools) - read_tool_set)
        if unknown_tools:
            errors.append(
                f"profiles.{profile_id} references unknown tools: {', '.join(unknown_tools)}"
            )
        for field in ("skill_route", "workflow_route"):
            route = profile.get(field)
            if route is not None and route not in routes:
                errors.append(
                    f"profiles.{profile_id}.{field} references unknown route: {route}"
                )
        if profile.get("execution_policy") != "workspace_only":
            errors.append(
                f"profiles.{profile_id}.execution_policy must be workspace_only"
            )

    domains = raw.get("domains")
    project_ids: list[str] = []
    if not isinstance(domains, list):
        errors.append("domains must be a list")
    else:
        for index, domain in enumerate(domains):
            if not isinstance(domain, dict):
                errors.append(f"domains[{index}] requires only id and profile")
                continue
            domain_id = domain.get("id")
            profile_id = domain.get("profile")
            if not isinstance(domain_id, str) or not domain_id:
                errors.append(f"domains[{index}].id must be non-empty")
                continue
            project_ids.append(domain_id)
            if profile_id not in profiles:
                errors.append(
                    f"domain {domain_id} references unknown profile: {profile_id}"
                )

    if len(set(project_ids)) != len(project_ids):
        errors.append("domains contains duplicate ids")
    missing = sorted(set(manifest_ids) - set(project_ids))
    unknown = sorted(set(project_ids) - set(manifest_ids))
    if missing:
        errors.append(f"domains missing manifest ids: {', '.join(missing)}")
    if unknown:
        errors.append(f"domains contains unknown manifest ids: {', '.join(unknown)}")

    selected_ids = list(gateway_domain_ids)
    if len(set(selected_ids)) != len(selected_ids):
        errors.append("gateway domains contains duplicate ids")
    if selected_ids and not gateway_files:
        errors.append("clients must expose at least one instruction file")
    for domain_id in sorted(set(selected_ids)):
        if domain_id not in manifest_ids or domain_id not in project_ids:
            errors.append(f"gateway domain is not registered: {domain_id}")
            continue
        domain_root = registry.resolve_path(domain_id)
        if domain_root is None:
            errors.append(f"gateway domain root is unavailable: {domain_id}")
            continue
        for filename in gateway_files:
            errors.extend(_check_gateway_file(domain_root / filename, domain_id))

    report: dict[str, object] = {
        "ok": not errors,
        "domain_count": len(manifest_ids),
    }
    if selected_ids:
        report["gateway_count"] = len(set(selected_ids))
    report["errors"] = errors
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-registry", type=Path, required=True)
    parser.add_argument("--project-registry", type=Path, required=True)
    parser.add_argument("--gateway-domain", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_domain_projects(
        args.domain_registry,
        args.project_registry,
        args.gateway_domain,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "documents domain projects: ok"
            if report["ok"]
            else "documents domain projects: failed"
        )
        for error in report["errors"]:
            print(f"- {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
