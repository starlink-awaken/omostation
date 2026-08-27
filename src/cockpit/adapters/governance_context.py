"""Thin, read-only projections over Workspace, L4, and OMO governance owners."""

from __future__ import annotations

import importlib.util
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from cockpit.adapters.governance import _utils
from cockpit.adapters.governance._utils import _documents_root, _registry_path

_CAPABILITY_ROUTE_CONTRACTS = {
    "skills": ("workspace-skills", "directory"),
    "workflows": ("workspace-workflow-mesh", "file"),
}
_DOMAIN_REGISTRY_AUTHORITY = "l4-domain-registry"
_DOMAIN_BINDING_AUTHORITY = "workspace-documents-domain-projects"


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


def mcp_safe_domain_context(
    payload: dict[str, Any],
    *,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    """Project domain context without exposing Documents absolute paths."""

    root = str(_documents_root(documents_root))
    root_prefix = f"{root}{os.sep}"

    def project(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: project(item) for key, item in value.items()}
        if isinstance(value, list):
            return [project(item) for item in value]
        if isinstance(value, tuple):
            return tuple(project(item) for item in value)
        if isinstance(value, Path):
            value = str(value)
        if isinstance(value, str):
            if value == root:
                return "documents://"
            return value.replace(root_prefix, "documents://")
        return value

    return project(payload)


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


from cockpit.adapters.governance import domain_project, runtime_receipts, workspace_cards
from cockpit.adapters.governance.domain_project import domain_project_status
from cockpit.adapters.governance.runtime_receipts import (
    _controller_shadow_unavailable,
    _facts_validation_unavailable,
    domain_controller_shadow_status,
    domain_facts_validation_status,
    domain_model_freshness_status,
    domain_sanyi_status_consistency_status,
    model_freshness_unavailable_envelope,
    sanyi_status_consistency_unavailable_envelope,
)
from cockpit.adapters.governance.workspace_cards import (
    _run_omo,
    cards_check,
    cards_status,
    kems_status,
    workspace_context,
)

__all__ = [
    "resolve_workspace_root",
    "_documents_root",
    "_registry_path",
    "_load_domains",
    "domains_list",
    "_validated_capability_routes",
    "_binding_context",
    "domain_context",
    "mcp_safe_domain_context",
    "_artifact_status",
    "_domain_facts_audit_unavailable",
    "domain_facts_audit",
    "domain_facts_validation_status",
    "domain_model_freshness_status",
    "domain_sanyi_status_consistency_status",
    "domain_controller_shadow_status",
    "domain_project_status",
    "_run_omo",
    "cards_status",
    "cards_check",
    "workspace_context",
    "kems_status",
]
