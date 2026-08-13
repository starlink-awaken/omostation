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

_CAPABILITY_ROUTE_CONTRACTS = {
    "skills": ("workspace-skills", "directory"),
    "workflows": ("workspace-workflow-mesh", "file"),
}


def resolve_workspace_root(explicit: str | Path | None = None) -> Path:
    """Resolve Workspace without assuming one fixed checkout layout."""

    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / ".omo" / "state" / "system.yaml").is_file():
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
    try:
        from l4_kernel.content_plane import audit_content_plane  # type: ignore[import-not-found]

        report = audit_content_plane(documents_root)
    except Exception as exc:
        return {
            "owner": "l4-kernel",
            "status": "unavailable",
            "available": False,
            "root": str(documents_root),
            "error": str(exc),
        }
    return {
        "owner": "l4-kernel",
        "status": "ok" if report.ok else "degraded",
        "available": True,
        "root": str(report.root),
        "counts": report.counts,
        "violations": [item.to_dict() for item in report.violations],
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
