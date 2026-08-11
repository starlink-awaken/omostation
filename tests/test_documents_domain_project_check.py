from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-project-check.py"


def _manifest(domain_root: Path, domain_id: str) -> Path:
    domain_root.mkdir(parents=True)
    path = domain_root / "DOMAIN.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainManifest",
                "id": domain_id,
                "display_name": f"@{domain_id}",
                "archetype": "operational",
                "space_ref": "personal-space",
                "root": ".",
                "owners": ["personal-space-owner"],
                "principal_ref": "personal-space-owner",
                "default_sensitivity": "private",
                "default_visibility": "private",
                "sharing_policy": "explicit_publish",
                "retention": "permanent",
                "authority_policy": "canonical_write",
                "harness_profile_ref": "harness://operational/v1",
                "lifecycle": "active",
                "policy_refs": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _domain_registry(tmp_path: Path, domain_ids: list[str]) -> Path:
    registry_dir = tmp_path / "documents" / "@公共" / "_control"
    registry_dir.mkdir(parents=True)
    entries = []
    for domain_id in domain_ids:
        manifest = _manifest(tmp_path / "documents" / domain_id, domain_id)
        entries.append(
            {"id": domain_id, "path": os.path.relpath(manifest, registry_dir)}
        )
    path = registry_dir / "L4-DOMAIN-REGISTRY.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainRegistry",
                "id": "test-domains",
                "display_name": "Test domains",
                "space_ref": "personal-space",
                "status": "active",
                "path_base": "registry_file_parent",
                "manifests": entries,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _project_registry(tmp_path: Path, domain_ids: list[str]) -> Path:
    path = tmp_path / "documents-domain-projects.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "workspace.omostation/v1",
                "kind": "DocumentsDomainProjects",
                "id": "test-domain-projects",
                "status": "active",
                "owner": "cockpit",
                "domain_registry": {
                    "owner": "l4-kernel",
                    "documents_relative_ref": "registry.yaml",
                },
                "workspace_mcp": {
                    "owner": "cockpit",
                    "server": "cockpit",
                    "entrypoint": "cockpit-mcp",
                    "transport": "stdio",
                    "read_tools": ["workspace_context", "domain_context"],
                },
                "capability_routes": {
                    "skills": {
                        "owner": "workspace-skills",
                        "registry_ref": "bos://shared/skills",
                    }
                },
                "clients": {
                    "codex": {
                        "instruction_file": "AGENTS.md",
                        "mcp_scope": "user_or_project",
                    }
                },
                "profiles": {
                    "content-domain": {
                        "allowed_workspace_tools": [
                            "workspace_context",
                            "domain_context",
                        ],
                        "skill_route": "skills",
                        "execution_policy": "workspace_only",
                    }
                },
                "domains": [
                    {"id": domain_id, "profile": "content-domain"}
                    for domain_id in domain_ids
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _run(
    domain_registry: Path, project_registry: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--domain-registry",
            str(domain_registry),
            "--project-registry",
            str(project_registry),
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_domain_project_registry_passes(tmp_path: Path) -> None:
    result = _run(
        _domain_registry(tmp_path, ["vault", "shared"]),
        _project_registry(tmp_path, ["vault", "shared"]),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"ok": True, "domain_count": 2, "errors": []}


def test_project_registry_must_cover_each_manifest_exactly_once(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault", "shared"])
    project_registry = _project_registry(tmp_path, ["vault"])

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "domains missing manifest ids: shared"
    ]


def test_domain_profile_reference_must_exist(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["domains"][0]["profile"] = "missing-profile"
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "domain vault references unknown profile: missing-profile"
    ]


def test_profile_tools_must_be_exposed_by_workspace_mcp(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["profiles"]["content-domain"]["allowed_workspace_tools"].append("invented_tool")
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "profiles.content-domain references unknown tools: invented_tool"
    ]


def test_profile_capability_routes_must_exist(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["profiles"]["content-domain"]["workflow_route"] = "missing-workflows"
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "profiles.content-domain.workflow_route references unknown route: missing-workflows"
    ]


def test_domain_execution_must_remain_workspace_owned(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["profiles"]["content-domain"]["execution_policy"] = "domain_local"
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "profiles.content-domain.execution_policy must be workspace_only"
    ]
