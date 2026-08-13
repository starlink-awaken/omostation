"""Thin, read-only projections over Workspace, L4, and OMO governance owners."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

_CAPABILITY_ROUTE_CONTRACTS = {
    "skills": ("workspace-skills", "directory"),
    "workflows": ("workspace-workflow-mesh", "file"),
}
_FACTS_EVIDENCE_SCHEMA = "runtime.documents-facts-audit.evidence.v1"
_CONTROLLER_SHADOW_EVIDENCE_SCHEMA = "runtime.documents-controller-shadow.evidence.v2"
_MODEL_FRESHNESS_EVIDENCE_SCHEMA = "runtime.documents-model-freshness.evidence.v1"
_MODEL_FRESHNESS_ERRORS = frozenset(
    {
        "domain_root_missing",
        "domain_root_unreadable",
        "domain_root_not_direct",
        "domain_path_invalid",
        "entities_directory_missing",
        "entities_directory_unreadable",
        "entities_directory_not_direct",
        "facts_file_missing",
        "facts_file_not_regular",
        "facts_file_unreadable",
        "facts_last_reviewed_missing",
        "facts_last_reviewed_invalid",
        "models_directory_missing",
        "models_directory_unreadable",
        "models_directory_not_direct",
        "models_directory_empty",
        "model_file_not_regular",
        "model_file_unreadable",
        "model_last_reviewed_missing",
        "model_last_reviewed_invalid",
    }
)
_MODEL_FRESHNESS_PRE_FACTS_ERRORS = frozenset(
    {
        "domain_root_missing",
        "domain_root_unreadable",
        "domain_root_not_direct",
        "domain_path_invalid",
        "entities_directory_missing",
        "entities_directory_unreadable",
        "entities_directory_not_direct",
        "facts_file_missing",
        "facts_file_not_regular",
        "facts_file_unreadable",
        "facts_last_reviewed_missing",
        "facts_last_reviewed_invalid",
    }
)
_MODEL_FRESHNESS_DIRECTORY_ERRORS = frozenset(
    {
        "models_directory_missing",
        "models_directory_unreadable",
        "models_directory_not_direct",
        "models_directory_empty",
    }
)
_MODEL_FRESHNESS_REVIEWED_ERRORS = frozenset({"model_last_reviewed_missing", "model_last_reviewed_invalid"})
_CONTROLLER_SHADOW_LEGACY_RULE_IDS = (
    "CR01",
    "CR02",
    "CR03",
    "CR05",
    "CR08",
    "CR23",
    "CR24",
    "CR25",
    "CR26",
    "CR29",
    "CR30",
)
_CONTROLLER_SHADOW_OBSERVED_RULE_IDS = ("CR01", "CR02", "CR03", "CR05")
_CONTROLLER_SHADOW_UNOBSERVED_RULE_IDS = tuple(
    rule_id for rule_id in _CONTROLLER_SHADOW_LEGACY_RULE_IDS if rule_id not in _CONTROLLER_SHADOW_OBSERVED_RULE_IDS
)
_MAX_RUNTIME_RECEIPT_BYTES = 32 * 1024


def resolve_workspace_root(explicit: str | Path | None = None) -> Path:
    """Resolve Workspace without assuming one fixed checkout layout."""

    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    source = Path(__file__).resolve()
    for parent in source.parents:
        authority = parent / ".omo"
        if not authority.is_symlink() and (authority / "state" / "system.yaml").is_file():
            return parent
        if parent.name == ".subtrees":
            return parent.parent
    return source.parents[3]


def _documents_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("L4_DOCUMENTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Documents").resolve()


def _registry_path(
    explicit: str | Path | None = None,
    *,
    documents_root: str | Path | None = None,
) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("L4_DOMAIN_REGISTRY")
    if configured:
        return Path(configured).expanduser().resolve()
    return _documents_root(documents_root) / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"


def _load_domains(
    registry_path: str | Path | None = None,
    *,
    documents_root: str | Path | None = None,
):
    from l4_kernel.manifest_registry import ManifestRegistry  # type: ignore[import-not-found]

    path = _registry_path(registry_path, documents_root=documents_root)
    registry = ManifestRegistry.load(path)
    legacy = registry.as_legacy_registry()
    projected = []
    for domain in legacy.list_all():
        raw = domain.to_dict()
        projected.append(
            {
                "id": raw["id"],
                "name": raw["name"],
                "type": raw["type"],
                "path": raw["path"],
                "bos_uri": raw["bos_uri"],
                "capabilities": list(raw.get("capabilities") or []),
                "exists": bool(raw["exists"]),
            }
        )
    return path, registry, projected


def domains_list(
    registry_path: str | Path | None = None,
    *,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the validated Documents domain registry projection."""

    path = _registry_path(registry_path, documents_root=documents_root)
    try:
        path, registry, domains = _load_domains(registry_path, documents_root=documents_root)
    except Exception as exc:
        return {
            "schema": "cockpit.domains.v1",
            "status": "unavailable",
            "available": False,
            "owner": "l4-kernel",
            "source": str(path),
            "total": 0,
            "domains": [],
            "error": str(exc),
        }

    status = "ok" if all(domain["exists"] for domain in domains) else "degraded"
    return {
        "schema": "cockpit.domains.v1",
        "status": status,
        "available": True,
        "owner": "l4-kernel",
        "source": str(path),
        "registry_id": registry.id,
        "total": len(domains),
        "domains": domains,
    }


def _validated_capability_routes(raw_routes: object, workspace_root: Path) -> dict[str, Any]:
    """Resolve the Workspace-owned skill and workflow sources fail closed."""

    if not isinstance(raw_routes, dict):
        raise ValueError("capability_routes must be a mapping")
    resolved_workspace = workspace_root.resolve(strict=True)
    routes = dict(raw_routes)
    for route_id, (expected_owner, expected_kind) in _CAPABILITY_ROUTE_CONTRACTS.items():
        route = raw_routes.get(route_id)
        if not isinstance(route, dict):
            raise ValueError(f"capability_routes.{route_id} must be a mapping")
        if route.get("owner") != expected_owner:
            raise ValueError(f"capability_routes.{route_id}.owner must be {expected_owner}")
        registry_ref = route.get("registry_ref")
        if not isinstance(registry_ref, str) or not registry_ref:
            raise ValueError(f"capability_routes.{route_id}.registry_ref must be a Workspace-relative path")
        candidate = Path(registry_ref)
        if candidate.is_absolute() or ".." in candidate.parts or "://" in registry_ref:
            raise ValueError(f"capability_routes.{route_id}.registry_ref must be a Workspace-relative path")
        try:
            resolved = (resolved_workspace / candidate).resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"capability_routes.{route_id}.registry_ref is unavailable: {registry_ref}") from exc
        if not resolved.is_relative_to(resolved_workspace):
            raise ValueError(f"capability_routes.{route_id}.registry_ref must be a Workspace-relative path")
        if expected_kind == "directory" and not resolved.is_dir():
            raise ValueError(f"capability_routes.{route_id}.registry_ref must be a directory")
        if expected_kind == "file" and not resolved.is_file():
            raise ValueError(f"capability_routes.{route_id}.registry_ref must be a file")
        routes[route_id] = {
            **route,
            "resolved_path": str(resolved),
            "status": "ok",
        }
    return routes


def _binding_context(domain_id: str, workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("binding registry must be a mapping")
        entries = raw.get("domains")
        if not isinstance(entries, list):
            raise ValueError("binding registry domains must be a list")
        entry = next((item for item in entries if isinstance(item, dict) and item.get("id") == domain_id), None)
        if entry is None:
            raise ValueError(f"binding not found for domain: {domain_id}")
        profile_id = entry.get("profile")
        profiles = raw.get("profiles")
        if not isinstance(profile_id, str) or not isinstance(profiles, dict):
            raise ValueError(f"invalid profile binding for domain: {domain_id}")
        profile = profiles.get(profile_id)
        if not isinstance(profile, dict):
            raise ValueError(f"profile not found: {profile_id}")
        clients = raw.get("clients")
        if not isinstance(clients, dict):
            raise ValueError("binding registry clients must be a mapping")
        capability_routes = _validated_capability_routes(raw.get("capability_routes"), workspace_root)
        return {
            "status": "ok",
            "available": True,
            "source": str(path),
            "profile_id": profile_id,
            "profile": profile,
            "workspace_mcp": raw.get("workspace_mcp") if isinstance(raw.get("workspace_mcp"), dict) else {},
            "capability_routes": capability_routes,
            "clients": clients,
            "runtime_state": raw.get("runtime_state") if isinstance(raw.get("runtime_state"), dict) else {},
            "runtime_jobs": raw.get("runtime_jobs") if isinstance(raw.get("runtime_jobs"), list) else [],
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "available": False,
            "source": str(path),
            "error": str(exc),
        }


def domain_context(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve one domain identity plus its optional Workspace binding."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    try:
        source, registry, domains = _load_domains(registry_path, documents_root=documents_root)
    except Exception as exc:
        return {
            "schema": "cockpit.domain-context.v1",
            "status": "unavailable",
            "available": False,
            "domain_id": requested,
            "domain": None,
            "error": str(exc),
            "sources": {"domain_registry": str(source)},
        }

    domain = next((item for item in domains if item["id"] == requested), None)
    manifest = registry.get(requested)
    if domain is None or manifest is None:
        return {
            "schema": "cockpit.domain-context.v1",
            "status": "unavailable",
            "available": False,
            "domain_id": requested,
            "domain": None,
            "error": f"unknown domain: {requested}",
            "sources": {"domain_registry": str(source)},
        }

    identity = {
        **domain,
        "archetype": manifest.archetype,
        "authority_policy": manifest.authority_policy,
        "lifecycle": manifest.lifecycle,
        "owners": list(manifest.owners),
        "principal_ref": manifest.principal_ref,
    }
    binding = _binding_context(requested, resolve_workspace_root(workspace_root))
    return {
        "schema": "cockpit.domain-context.v1",
        "status": "ok" if binding["status"] == "ok" else "degraded",
        "available": True,
        "domain_id": requested,
        "domain": identity,
        "binding": binding,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding["source"],
        },
    }


def _artifact_status(root: Path, relative: Path) -> dict[str, str]:
    """Inspect one declared domain artifact without following static links."""

    path = root / relative
    if relative.is_absolute() or ".." in relative.parts:
        return {"status": "invalid", "path": str(path)}

    try:
        for index in range(len(relative.parts)):
            parent = root.joinpath(*relative.parts[:index])
            if not stat.S_ISDIR(os.lstat(parent).st_mode):
                return {"status": "invalid", "path": str(path)}
        file_stat = os.lstat(path)
    except FileNotFoundError:
        return {"status": "missing", "path": str(path)}
    except OSError:
        return {"status": "unreadable", "path": str(path)}

    if not stat.S_ISREG(file_stat.st_mode):
        return {"status": "invalid", "path": str(path)}

    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return {"status": "unreadable", "path": str(path)}
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return {
        "status": "present",
        "path": str(path),
        "modified_on": datetime.fromtimestamp(file_stat.st_mtime).date().isoformat(),
    }


def _domain_facts_audit_unavailable(requested: str, source: Path, error: str) -> dict[str, Any]:
    return {
        "schema": "cockpit.domain-facts-audit.v1",
        "status": "unavailable",
        "available": False,
        "requested_domain_id": requested,
        "total": 0,
        "summary": {"present": 0, "missing": 0, "unreadable": 0, "invalid": 0},
        "domains": [],
        "sources": {"domain_registry": str(source)},
        "error": error,
    }


def domain_facts_audit(
    domain_id: str = "",
    *,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Audit declared per-domain facts artifacts through the L4 registry authority."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
    except Exception as exc:
        return _domain_facts_audit_unavailable(requested, source, str(exc))
    if not domains:
        return _domain_facts_audit_unavailable(requested, source, "no registered domain projects")

    selected = domains
    if requested:
        selected = [domain for domain in domains if domain["id"] == requested]
        if not selected:
            return _domain_facts_audit_unavailable(requested, source, f"unknown domain: {requested}")

    summary = {"present": 0, "missing": 0, "unreadable": 0, "invalid": 0}
    items: list[dict[str, Any]] = []
    for domain in selected:
        facts = _artifact_status(Path(domain["path"]), Path("_entities/facts.md"))
        summary[facts["status"]] += 1
        items.append({"id": domain["id"], "name": domain["name"], "facts": facts})

    return {
        "schema": "cockpit.domain-facts-audit.v1",
        "status": "ok" if summary["present"] == len(items) else "violations",
        "available": True,
        "requested_domain_id": requested,
        "total": len(items),
        "summary": summary,
        "domains": items,
        "sources": {"domain_registry": str(source)},
    }


def _facts_validation_unavailable(
    requested: str,
    source: Path,
    binding_source: str,
    error: str,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    sources = {"domain_registry": str(source), "binding_registry": binding_source}
    if runtime_evidence is not None:
        sources["runtime_evidence"] = str(runtime_evidence)
    return {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": "unavailable",
        "available": False,
        "domain_id": requested,
        "job": None,
        "validation": None,
        "sources": sources,
        "error": error,
    }


def _controller_shadow_unavailable(
    requested: str,
    source: Path,
    binding_source: str,
    error: str,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    sources = {"domain_registry": str(source), "binding_registry": binding_source}
    if runtime_evidence is not None:
        sources["runtime_evidence"] = str(runtime_evidence)
    return {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "unavailable",
        "available": False,
        "domain_id": requested,
        "job": None,
        "shadow": None,
        "sources": sources,
        "error": error,
    }


def _model_freshness_unavailable(
    requested: str,
    source: Path,
    binding_source: str,
    error: str,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    sources = {"domain_registry": str(source), "binding_registry": binding_source}
    if runtime_evidence is not None:
        sources["runtime_evidence"] = str(runtime_evidence)
    return {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": "unavailable",
        "available": False,
        "domain_id": requested,
        "job": None,
        "freshness": None,
        "sources": sources,
        "error": error,
    }


def _relative_path(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError(f"{label} must be a non-traversing relative path")
    return path


def _runtime_facts_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "audit_structured_facts"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique runtime facts validation job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("runtime facts validation job id must be non-empty")
    if owner != "runtime-facts":
        raise ValueError("runtime facts validation job owner must be runtime-facts")
    if evidence_schema != _FACTS_EVIDENCE_SCHEMA:
        raise ValueError("runtime facts validation job has an unsupported evidence schema")
    evidence_path = _relative_path(item.get("evidence_relative_path"), label="runtime evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "audit_structured_facts",
        "evidence_relative_path": str(evidence_path),
    }


def _runtime_controller_shadow_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "shadow_legacy_controller"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique Runtime controller shadow job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Runtime controller shadow job id must be non-empty")
    if owner != "runtime-control":
        raise ValueError("Runtime controller shadow job owner must be runtime-control")
    if evidence_schema != _CONTROLLER_SHADOW_EVIDENCE_SCHEMA:
        raise ValueError("Runtime controller shadow job has an unsupported evidence schema")
    evidence_path = _relative_path(item.get("evidence_relative_path"), label="Runtime evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "shadow_legacy_controller",
        "evidence_relative_path": str(evidence_path),
    }


def _runtime_model_freshness_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    """Return the unique configured Runtime model-freshness job."""

    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "audit_model_freshness"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique Runtime model freshness job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Runtime model freshness job id must be non-empty")
    if owner != "runtime-control":
        raise ValueError("Runtime model freshness job owner must be runtime-control")
    if evidence_schema != _MODEL_FRESHNESS_EVIDENCE_SCHEMA:
        raise ValueError("Runtime model freshness job has an unsupported evidence schema")
    evidence_path = _relative_path(item.get("evidence_relative_path"), label="Runtime evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "audit_model_freshness",
        "evidence_relative_path": str(evidence_path),
    }


def _path_identity_parts(path: Path) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path.resolve(strict=False).parts)


def _paths_overlap(first: Path, second: Path) -> bool:
    first_parts = _path_identity_parts(first)
    second_parts = _path_identity_parts(second)
    return first_parts[: len(second_parts)] == second_parts or second_parts[: len(first_parts)] == first_parts


def _runtime_state_root(
    binding: dict[str, Any],
    *,
    runtime_state_root: str | Path | None,
    documents_root: str | Path | None,
) -> Path:
    state = binding.get("runtime_state")
    if not isinstance(state, dict) or state.get("owner") != "runtime":
        raise ValueError("runtime_state must be declared by runtime")
    if runtime_state_root is not None:
        candidate = Path(runtime_state_root).expanduser()
    else:
        environment_override = state.get("environment_override")
        default_home_relative = state.get("default_home_relative")
        if not isinstance(environment_override, str) or not environment_override:
            raise ValueError("runtime_state environment_override must be non-empty")
        default_relative = _relative_path(default_home_relative, label="runtime_state default_home_relative")
        candidate = Path(os.environ.get(environment_override, str(Path.home() / default_relative))).expanduser()
    resolved = candidate.resolve(strict=False)
    if _paths_overlap(resolved, _documents_root(documents_root)):
        raise ValueError("Runtime state root must not overlap Documents")
    return resolved


def _read_bounded_runtime_receipt(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            raise ValueError("runtime state root is not a directory")
        parent = root
        for part in relative.parts[:-1]:
            parent = parent / part
            if not stat.S_ISDIR(os.lstat(parent).st_mode):
                raise ValueError("runtime evidence parent is not a directory")
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("runtime evidence is not a regular file")
        if before.st_size > _MAX_RUNTIME_RECEIPT_BYTES:
            raise ValueError("runtime evidence exceeds the bounded receipt size")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as exc:
        raise ValueError("runtime evidence is unavailable") from exc
    except OSError as exc:
        raise ValueError("runtime evidence is unavailable") from exc

    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("runtime evidence is not a regular file")
        encoded = os.read(descriptor, _MAX_RUNTIME_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise ValueError("runtime evidence is unreadable") from exc
    finally:
        os.close(descriptor)
    if len(encoded) > _MAX_RUNTIME_RECEIPT_BYTES:
        raise ValueError("runtime evidence exceeds the bounded receipt size")
    try:
        raw = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("runtime evidence is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("runtime evidence must be a JSON object")
    return raw


def _non_negative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"runtime evidence {label} must be a non-negative integer")
    return value


def _iso_date(value: object, *, label: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"runtime evidence {label} must be an ISO date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"runtime evidence {label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"runtime evidence {label} must be an ISO date")
    return value


def _unavailable_model_freshness_is_consistent(freshness: dict[str, Any]) -> bool:
    error = freshness["error"]
    facts_reviewed = freshness["facts_last_reviewed"]
    model_count = freshness["model_markdown_count"]
    fresh_count = freshness["fresh_model_count"]
    stale_count = freshness["stale_model_count"]
    invalid_count = freshness["invalid_reviewed_count"]
    unreadable_count = freshness["unreadable_regular_file_count"]
    no_model_observation = (
        model_count == 0 and fresh_count == 0 and stale_count == 0 and invalid_count == 0 and unreadable_count == 0
    )
    if error in _MODEL_FRESHNESS_PRE_FACTS_ERRORS:
        return facts_reviewed is None and no_model_observation
    if error in _MODEL_FRESHNESS_DIRECTORY_ERRORS:
        return facts_reviewed is not None and no_model_observation
    if error == "model_file_not_regular":
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 0
            and unreadable_count == 0
        )
    if error == "model_file_unreadable":
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 0
            and unreadable_count == 1
        )
    if error in _MODEL_FRESHNESS_REVIEWED_ERRORS:
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 1
            and unreadable_count == 0
        )
    return False


def _validated_facts_receipt(receipt: dict[str, Any], job: dict[str, str]) -> tuple[str, dict[str, Any]]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("runtime evidence did not complete a valid audit")
    owner_evidence = receipt.get("owner_evidence")
    if not isinstance(owner_evidence, dict) or owner_evidence.get("schema") != _FACTS_EVIDENCE_SCHEMA:
        raise ValueError("runtime evidence has an invalid facts audit schema")
    owner_status = owner_evidence.get("status")
    if owner_status not in {"ok", "invalid"}:
        raise ValueError("runtime evidence has an invalid facts audit status")
    facts_total = _non_negative_int(owner_evidence.get("facts_total"), label="facts_total")
    by_type = owner_evidence.get("by_type")
    if not isinstance(by_type, dict) or any(
        not isinstance(name, str) or not name or isinstance(count, bool) or not isinstance(count, int) or count < 0
        for name, count in by_type.items()
    ):
        raise ValueError("runtime evidence has an invalid facts type summary")
    if sum(by_type.values()) != facts_total:
        raise ValueError("runtime evidence facts_total does not match by_type")
    validation = {
        "facts_total": facts_total,
        "by_type": dict(sorted(by_type.items())),
        "error_count": _non_negative_int(owner_evidence.get("error_count"), label="error_count"),
        "warning_count": _non_negative_int(owner_evidence.get("warning_count"), label="warning_count"),
    }
    receipt_status = receipt.get("status")
    exit_code = receipt.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("runtime evidence exit_code must be an integer")
    if owner_status == "ok" and receipt_status == "succeeded" and exit_code == 0:
        return "ok", validation
    if owner_status == "invalid" and receipt_status == "failed" and exit_code != 0:
        return "violations", validation
    raise ValueError("runtime receipt and facts validation status disagree")


def _validated_model_freshness_receipt(receipt: dict[str, Any], job: dict[str, str]) -> tuple[str, dict[str, Any]]:
    """Validate status, aggregates and exit-code relationship in one receipt."""

    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("Runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("Runtime evidence did not complete a valid model freshness audit")
    owner_evidence = receipt.get("owner_evidence")
    fields = {
        "schema",
        "status",
        "checked_on",
        "facts_last_reviewed",
        "model_markdown_count",
        "fresh_model_count",
        "stale_model_count",
        "invalid_reviewed_count",
        "unreadable_regular_file_count",
        "error",
    }
    if (
        not isinstance(owner_evidence, dict)
        or set(owner_evidence) != fields
        or owner_evidence.get("schema") != _MODEL_FRESHNESS_EVIDENCE_SCHEMA
    ):
        raise ValueError("Runtime evidence has an invalid model freshness schema")
    status = owner_evidence.get("status")
    if status not in {"ok", "attention", "unavailable"}:
        raise ValueError("Runtime evidence has an invalid model freshness status")
    freshness = {
        "checked_on": _iso_date(owner_evidence.get("checked_on"), label="checked_on"),
        "facts_last_reviewed": _iso_date(
            owner_evidence.get("facts_last_reviewed"),
            label="facts_last_reviewed",
            optional=True,
        ),
        "model_markdown_count": _non_negative_int(
            owner_evidence.get("model_markdown_count"), label="model_markdown_count"
        ),
        "fresh_model_count": _non_negative_int(owner_evidence.get("fresh_model_count"), label="fresh_model_count"),
        "stale_model_count": _non_negative_int(owner_evidence.get("stale_model_count"), label="stale_model_count"),
        "invalid_reviewed_count": _non_negative_int(
            owner_evidence.get("invalid_reviewed_count"), label="invalid_reviewed_count"
        ),
        "unreadable_regular_file_count": _non_negative_int(
            owner_evidence.get("unreadable_regular_file_count"),
            label="unreadable_regular_file_count",
        ),
        "error": owner_evidence.get("error"),
    }
    model_count = freshness["model_markdown_count"]
    fresh_count = freshness["fresh_model_count"]
    stale_count = freshness["stale_model_count"]
    invalid_count = freshness["invalid_reviewed_count"]
    unreadable_count = freshness["unreadable_regular_file_count"]
    error = freshness["error"]
    if (
        fresh_count + stale_count > model_count
        or (status == "unavailable") != (error in _MODEL_FRESHNESS_ERRORS)
        or (status != "unavailable" and error is not None)
        or (status == "unavailable" and not _unavailable_model_freshness_is_consistent(freshness))
        or (
            status == "ok"
            and (
                model_count == 0
                or fresh_count != model_count
                or stale_count != 0
                or invalid_count != 0
                or unreadable_count != 0
                or freshness["facts_last_reviewed"] is None
            )
        )
        or (
            status == "attention"
            and (
                model_count == 0
                or fresh_count + stale_count != model_count
                or stale_count == 0
                or invalid_count != 0
                or unreadable_count != 0
                or freshness["facts_last_reviewed"] is None
            )
        )
    ):
        raise ValueError("Runtime evidence has invalid model freshness aggregates")
    exit_code = receipt.get("exit_code")
    expected = {
        "ok": ("succeeded", 0),
        "attention": ("failed", 1),
        "unavailable": ("failed", 2),
    }[status]
    if isinstance(exit_code, bool) or (receipt.get("status"), exit_code) != expected:
        raise ValueError("Runtime receipt and model freshness status disagree")
    return status, freshness


def _validated_controller_shadow_receipt(receipt: dict[str, Any], job: dict[str, str]) -> dict[str, Any]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("Runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("Runtime evidence did not complete a valid controller shadow")
    exit_code = receipt.get("exit_code")
    if (
        receipt.get("status") != "failed"
        or isinstance(exit_code, bool)
        or not isinstance(exit_code, int)
        or exit_code == 0
    ):
        raise ValueError("Runtime receipt does not preserve the observed shadow status")
    owner_evidence = receipt.get("owner_evidence")
    if (
        not isinstance(owner_evidence, dict)
        or owner_evidence.get("schema") != _CONTROLLER_SHADOW_EVIDENCE_SCHEMA
        or owner_evidence.get("status") != "shadow_observed"
        or owner_evidence.get("legacy_controller_replaced") is not False
        or owner_evidence.get("cutover_ready") is not False
    ):
        raise ValueError("Runtime evidence has an invalid controller shadow schema")
    legacy_rule_ids = owner_evidence.get("legacy_rule_ids")
    if legacy_rule_ids != list(_CONTROLLER_SHADOW_LEGACY_RULE_IDS):
        raise ValueError("Runtime evidence has invalid controller shadow legacy rules")
    if owner_evidence.get("legacy_rule_count") != len(legacy_rule_ids):
        raise ValueError("Runtime evidence has an invalid controller shadow legacy rule count")
    observed_rule_ids = owner_evidence.get("observed_rule_ids")
    if observed_rule_ids != list(_CONTROLLER_SHADOW_OBSERVED_RULE_IDS):
        raise ValueError("Runtime evidence has invalid observed controller rules")
    if owner_evidence.get("observed_rule_count") != len(observed_rule_ids):
        raise ValueError("Runtime evidence has an invalid observed controller rule count")
    unobserved_rule_ids = owner_evidence.get("unobserved_rule_ids")
    if unobserved_rule_ids != list(_CONTROLLER_SHADOW_UNOBSERVED_RULE_IDS):
        raise ValueError("Runtime evidence has invalid unobserved controller rules")
    if owner_evidence.get("unobserved_rule_count") != len(unobserved_rule_ids):
        raise ValueError("Runtime evidence has an invalid unobserved controller rule count")
    return {
        "cutover_ready": False,
        "legacy_controller_replaced": False,
        "legacy_rule_ids": legacy_rule_ids,
        "observed_rule_ids": observed_rule_ids,
        "unobserved_rule_ids": unobserved_rule_ids,
    }


def domain_facts_validation_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Read a bounded Runtime facts-audit receipt for one registered domain."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    binding_source = str(binding["source"])
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        if not requested or not any(domain["id"] == requested for domain in domains):
            raise ValueError(f"unknown domain: {requested}")
        if binding["status"] != "ok":
            raise ValueError(binding.get("error", "domain binding is unavailable"))
        job = _runtime_facts_job(binding, requested)
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
        evidence_path = state_root / job["evidence_relative_path"]
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        status, validation = _validated_facts_receipt(receipt, job)
    except (OSError, ValueError) as exc:
        evidence = locals().get("evidence_path")
        return _facts_validation_unavailable(
            requested,
            source,
            binding_source,
            str(exc),
            runtime_evidence=evidence if isinstance(evidence, Path) else None,
        )

    return {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": status,
        "available": True,
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "validation": validation,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding_source,
            "runtime_evidence": str(evidence_path),
        },
    }


def domain_model_freshness_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Project only a validated Runtime model-freshness receipt."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    binding_source = str(binding["source"])
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        if not requested or not any(domain["id"] == requested for domain in domains):
            raise ValueError(f"unknown domain: {requested}")
        if binding["status"] != "ok":
            raise ValueError(binding.get("error", "domain binding is unavailable"))
        job = _runtime_model_freshness_job(binding, requested)
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
        evidence_path = state_root / job["evidence_relative_path"]
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        status, freshness = _validated_model_freshness_receipt(receipt, job)
    except (OSError, ValueError) as exc:
        evidence = locals().get("evidence_path")
        return _model_freshness_unavailable(
            requested,
            source,
            binding_source,
            str(exc),
            runtime_evidence=evidence if isinstance(evidence, Path) else None,
        )

    return {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": status,
        "available": status != "unavailable",
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "freshness": freshness,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding_source,
            "runtime_evidence": str(evidence_path),
        },
    }


def domain_controller_shadow_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Read the bounded Runtime receipt for an incomplete legacy controller shadow."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    binding_source = str(binding["source"])
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        if not requested or not any(domain["id"] == requested for domain in domains):
            raise ValueError(f"unknown domain: {requested}")
        if binding["status"] != "ok":
            raise ValueError(binding.get("error", "domain binding is unavailable"))
        job = _runtime_controller_shadow_job(binding, requested)
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
        evidence_path = state_root / job["evidence_relative_path"]
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        shadow = _validated_controller_shadow_receipt(receipt, job)
    except (OSError, ValueError) as exc:
        evidence = locals().get("evidence_path")
        return _controller_shadow_unavailable(
            requested,
            source,
            binding_source,
            str(exc),
            runtime_evidence=evidence if isinstance(evidence, Path) else None,
        )

    return {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "shadow_observed",
        "available": True,
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "shadow": shadow,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding_source,
            "runtime_evidence": str(evidence_path),
        },
    }


def _domain_project_unavailable(
    requested: str,
    source: Path,
    binding_path: Path,
    error: str,
) -> dict[str, Any]:
    return {
        "schema": "cockpit.domain-project-status.v1",
        "status": "unavailable",
        "available": False,
        "requested_domain_id": requested,
        "total": 0,
        "summary": {"ok": 0, "degraded": 0, "unavailable": 0},
        "domains": [],
        "sources": {"domain_registry": str(source), "binding_registry": str(binding_path)},
        "error": error,
    }


def _domain_project_item(
    domain: dict[str, Any],
    *,
    manifest: Any,
    binding: dict[str, Any],
) -> dict[str, Any]:
    root = Path(domain["path"])
    gateways: list[dict[str, str]] = []
    clients = binding.get("clients") if binding.get("status") == "ok" else {}
    if not isinstance(clients, dict):
        clients = {"invalid": {"instruction_file": ".."}}

    for client, definition in clients.items():
        if not isinstance(client, str) or not isinstance(definition, dict):
            gateways.append(
                {
                    "client": str(client),
                    "instruction_file": "",
                    "status": "invalid",
                    "path": str(root),
                }
            )
            continue
        instruction_file = definition.get("instruction_file")
        if instruction_file is None:
            continue
        if not isinstance(instruction_file, str) or not instruction_file.strip():
            gateways.append(
                {
                    "client": client,
                    "instruction_file": str(instruction_file),
                    "status": "invalid",
                    "path": str(root),
                }
            )
            continue
        artifact = _artifact_status(root, Path(instruction_file))
        gateways.append({"client": client, "instruction_file": instruction_file, **artifact})

    facts = _artifact_status(root, Path("_entities/facts.md"))
    identity = {
        "id": domain["id"],
        "name": domain["name"],
        "path": domain["path"],
        "exists": domain["exists"],
        "lifecycle": manifest.lifecycle,
        "authority_policy": manifest.authority_policy,
    }
    projected_binding = {key: binding[key] for key in ("status", "available", "source", "profile_id") if key in binding}
    status = "ok"
    if (
        not domain["exists"]
        or binding.get("status") != "ok"
        or any(gateway["status"] != "present" for gateway in gateways)
    ):
        status = "degraded"
    return {
        "id": domain["id"],
        "name": domain["name"],
        "status": status,
        "identity": identity,
        "binding": projected_binding,
        "gateways": gateways,
        "facts": facts,
    }


def domain_project_status(
    domain_id: str = "",
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the authoritative project-entry status for one or all Documents domains."""

    requested = domain_id.strip()
    source = _registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding_path = workspace / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    try:
        source, registry, domains = _load_domains(registry_path, documents_root=documents_root)
    except Exception as exc:
        return _domain_project_unavailable(requested, source, binding_path, str(exc))

    selected = domains
    if requested:
        selected = [domain for domain in domains if domain["id"] == requested]
        if not selected:
            return _domain_project_unavailable(requested, source, binding_path, f"unknown domain: {requested}")

    items: list[dict[str, Any]] = []
    for domain in selected:
        manifest = registry.get(domain["id"])
        if manifest is None:
            return _domain_project_unavailable(requested, source, binding_path, f"manifest unavailable: {domain['id']}")
        binding = _binding_context(domain["id"], workspace)
        items.append(_domain_project_item(domain, manifest=manifest, binding=binding))

    if not items:
        return _domain_project_unavailable(requested, source, binding_path, "no registered domains")

    counts = {status: sum(item["status"] == status for item in items) for status in ("ok", "degraded", "unavailable")}
    overall_status = "ok" if counts["ok"] == len(items) else "degraded"
    return {
        "schema": "cockpit.domain-project-status.v1",
        "status": overall_status,
        "available": True,
        "requested_domain_id": requested,
        "total": len(items),
        "summary": counts,
        "domains": items,
        "sources": {"domain_registry": str(source), "binding_registry": str(binding_path)},
    }


def _workspace_state(workspace_root: Path) -> dict[str, Any]:
    system_path = workspace_root / ".omo" / "state" / "system.yaml"
    goals_path = workspace_root / ".omo" / "_truth" / "goals" / "current.yaml"
    system: dict[str, Any] = {}
    goals: dict[str, Any] = {}
    errors: list[str] = []

    try:
        loaded = yaml.safe_load(system_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("system state must be a mapping")
        system = loaded
    except Exception as exc:
        errors.append(f"system: {exc}")

    try:
        documents = list(yaml.safe_load_all(goals_path.read_text(encoding="utf-8")))
        for document in documents:
            if isinstance(document, dict):
                goals.update(document)
        if not goals:
            raise ValueError("goals state must contain a mapping")
    except Exception as exc:
        errors.append(f"goals: {exc}")

    active_goals = []
    for goal in goals.get("goals") or []:
        if not isinstance(goal, dict) or goal.get("status") not in {"active", "in_progress"}:
            continue
        active_goals.append({key: goal[key] for key in ("id", "title", "desc", "status", "progress") if key in goal})
    theme = goals.get("theme") or system.get("next_milestone")
    if not theme and active_goals:
        theme = active_goals[0].get("title") or active_goals[0].get("desc")

    if system and goals:
        status = "ok"
    elif system or goals:
        status = "degraded"
    else:
        status = "unavailable"
    return {
        "status": status,
        "available": bool(system or goals),
        "phase": system.get("current_phase"),
        "phase_status": system.get("phase_status"),
        "theme": theme,
        "current_wave": goals.get("current_wave") or system.get("current_wave"),
        "active_goals": active_goals,
        "sources": {"system": str(system_path), "goals": str(goals_path)},
        "errors": errors,
    }


def _omo_workdir(workspace_root: Path) -> Path | None:
    candidates = [
        workspace_root / "projects" / "omo",
        Path(__file__).resolve().parents[3].parent / "omo",
    ]
    return next((path for path in candidates if path.is_dir()), None)


def _run_omo(
    arguments: list[str],
    *,
    workspace_root: str | Path | None = None,
    timeout: float = 20,
) -> subprocess.CompletedProcess[str]:
    root = resolve_workspace_root(workspace_root)
    cwd = _omo_workdir(root)
    return subprocess.run(
        [sys.executable, "-m", "omo.omo_cards", *arguments],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
        timeout=timeout,
    )


_CARD_LINE = re.compile(r"^\[(P[0-3])\]\s+(\S+)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(.*?)\s*$")


def _parse_cards(output: str) -> list[dict[str, str]]:
    items = []
    for line in output.splitlines():
        match = _CARD_LINE.match(line)
        if not match:
            continue
        priority, card_id, status, domain, title = match.groups()
        items.append(
            {
                "id": card_id,
                "priority": priority,
                "status": status,
                "domain": domain,
                "title": title,
            }
        )
    return items


def cards_status(
    *,
    workspace_root: str | Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List CARDS through OMO's public CLI authority."""

    try:
        result = _run_omo(["list", "--limit", str(limit)], workspace_root=workspace_root)
    except Exception as exc:
        return {
            "schema": "cockpit.cards.v1",
            "status": "unavailable",
            "available": False,
            "owner": "omo",
            "returncode": 127,
            "total": 0,
            "items": [],
            "error": str(exc),
        }

    items = _parse_cards(result.stdout)
    total_match = re.search(r"(?m)^(\d+) cards\s*$", result.stdout)
    total = int(total_match.group(1)) if total_match else len(items)
    owner_error = result.stderr.strip()
    if result.returncode != 0:
        status = "unavailable"
        available = False
    elif items or "(no cards)" in result.stdout or not result.stdout.strip():
        status = "ok"
        available = True
    else:
        status = "degraded"
        available = True
        owner_error = owner_error or "OMO output could not be normalized"
    envelope = {
        "schema": "cockpit.cards.v1",
        "status": status,
        "available": available,
        "owner": "omo",
        "returncode": result.returncode,
        "total": total,
        "items": items,
        "raw": result.stdout,
    }
    if owner_error:
        envelope["error"] = owner_error
    return envelope


def _violation_lines(output: str) -> list[str]:
    ignored_prefixes = ("📋 Constraint Check Results", "──")
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
        and not line.strip().startswith(ignored_prefixes)
        and not line.strip().endswith("violation(s) ──")
        and line.strip() != "✅ All checks passed."
    ]


def cards_check(
    card_id: str = "",
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run OMO's CARDS constraint authority and preserve its exit code."""

    try:
        result = _run_omo(["check"], workspace_root=workspace_root)
    except Exception as exc:
        return {
            "schema": "cockpit.cards-check.v1",
            "status": "unavailable",
            "available": False,
            "owner": "omo",
            "scope": "all",
            "requested_card_id": card_id,
            "compliant": False,
            "returncode": 127,
            "violations": [],
            "error": str(exc),
        }

    compliant = result.returncode == 0
    return {
        "schema": "cockpit.cards-check.v1",
        "status": "ok" if compliant else "violations",
        "available": True,
        "owner": "omo",
        "scope": "all",
        "requested_card_id": card_id,
        "compliant": compliant,
        "returncode": result.returncode,
        "violations": [] if compliant else _violation_lines(result.stdout),
        "raw": result.stdout,
        "stderr": result.stderr,
    }


def workspace_context(*, workspace_root: str | Path | None = None) -> dict[str, Any]:
    """Aggregate truthful read-only projections without taking over ownership."""

    root = resolve_workspace_root(workspace_root)
    workspace = _workspace_state(root)
    domain_result = domains_list()
    card_result = cards_status(workspace_root=root)
    cards = card_result.get("items") or []
    p0 = [card for card in cards if card.get("priority") == "P0"]
    statuses = (workspace["status"], domain_result["status"], card_result["status"])
    available = any((workspace["available"], domain_result["available"], card_result["available"]))
    return {
        "schema": "cockpit.governance-context.v1",
        "status": "ok" if all(status == "ok" for status in statuses) else "degraded",
        "available": available,
        "workspace_root": str(root),
        "phase": workspace["phase"],
        "phase_status": workspace["phase_status"],
        "theme": workspace["theme"],
        "current_wave": workspace["current_wave"],
        "active_goals": workspace["active_goals"],
        "domains": domain_result["domains"],
        "domain_summary": {
            "total": domain_result["total"],
            "existing": sum(1 for domain in domain_result["domains"] if domain["exists"]),
        },
        "cards_summary": {
            "status": card_result["status"],
            "active": len(cards),
            "total": card_result.get("total", len(cards)),
            "p0_open": len(p0),
            "p0_titles": [card.get("title", "") for card in p0],
        },
        "sources": {
            "workspace": workspace,
            "domains": {
                key: domain_result[key] for key in ("status", "available", "owner", "source") if key in domain_result
            },
            "cards": {
                key: card_result[key]
                for key in ("status", "available", "owner", "returncode", "error")
                if key in card_result
            },
        },
    }


def _module_status(module_name: str, owner: str) -> dict[str, Any]:
    try:
        available = importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        available = False
    return {"owner": owner, "status": "ok" if available else "unavailable", "available": available}


def _content_status(documents_root: Path) -> dict[str, Any]:
    return {
        "owner": "l4-kernel",
        "status": "not_run",
        "available": False,
        "root": str(documents_root),
        "reason": "full Documents content audit is on-demand; run cockpit kems scan",
    }


def kems_status(
    *,
    workspace_root: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Report content-plane audit and owner reachability without fake health."""

    root = _documents_root(documents_root)
    domains = domains_list(documents_root=root)
    content = _content_status(root)
    owners = {
        "omo": _module_status("omo", "omo"),
        "kairon": _module_status("kairon_observability", "kairon"),
    }
    statuses = [domains["status"], content["status"], *(item["status"] for item in owners.values())]
    return {
        "schema": "cockpit.kems-status.v1",
        "status": "ok" if all(status == "ok" for status in statuses) else "degraded",
        "available": bool(domains["available"] or content["available"]),
        "workspace_root": str(resolve_workspace_root(workspace_root)),
        "documents_root": str(root),
        "domains": {
            "status": domains["status"],
            "available": domains["available"],
            "total": domains["total"],
            "source": domains["source"],
        },
        "content_audit": content,
        "owners": owners,
    }
