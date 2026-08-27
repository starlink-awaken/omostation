from __future__ import annotations

from pathlib import Path
from typing import Any

from cockpit.adapters.governance import _utils
from cockpit.adapters.governance_context import _binding_context, _load_domains, resolve_workspace_root


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
        from cockpit.adapters.governance_context import _artifact_status

        artifact = _artifact_status(root, Path(instruction_file))
        gateways.append({"client": client, "instruction_file": instruction_file, **artifact})

    from cockpit.adapters.governance_context import _artifact_status

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
    requested = domain_id.strip()
    source = _utils._registry_path(registry_path, documents_root=documents_root)
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
