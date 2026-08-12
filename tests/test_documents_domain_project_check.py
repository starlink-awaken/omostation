from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
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
                    "claude": {
                        "instruction_file": "CLAUDE.md",
                        "mcp_scope": "user",
                    },
                    "codex": {
                        "instruction_file": "AGENTS.md",
                        "mcp_scope": "user_or_project",
                    },
                    "agents_compatible": {
                        "instruction_file": "AGENTS.md",
                        "mcp_scope": "client",
                    },
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
                "runtime_jobs": [
                    {
                        "id": "creative-manifest-check",
                        "domain_id": domain_ids[0],
                        "owner": "l4-kernel",
                        "action": "validate_manifest",
                        "schedule": "manual",
                        "timeout_seconds": 10,
                        "reads": ["domain_registry", "registered_manifests"],
                        "writes": [],
                        "evidence_path": "manifest-validation.json",
                        "fail_closed": True,
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _run(
    domain_registry: Path,
    project_registry: Path,
    gateway_domain_ids: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--domain-registry",
            str(domain_registry),
            "--project-registry",
            str(project_registry),
            *[
                argument
                for domain_id in gateway_domain_ids
                for argument in ("--gateway-domain", domain_id)
            ],
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_gateways(domain_root: Path, domain_id: str) -> None:
    text = f"""# Thin client gateway

Read `DOMAIN.yaml`; its id is `{domain_id}` and it is the identity SSOT.
Use Cockpit Workspace MCP `domain_context(domain_id=\"{domain_id}\")`.
Capabilities are owned by Workspace binding registry `documents-domain-projects`.
When MCP is unavailable report **degraded**. Documents 内容默认只读。
Do not execute Documents `_runtime`, `_control`, `.kems/_scripts`, or app code.
ChatGPT Web requires a reviewed remote plugin.
"""
    for filename in ("CLAUDE.md", "AGENTS.md"):
        (domain_root / filename).write_text(text, encoding="utf-8")


def test_valid_domain_project_registry_passes(tmp_path: Path) -> None:
    result = _run(
        _domain_registry(tmp_path, ["vault", "shared"]),
        _project_registry(tmp_path, ["vault", "shared"]),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"ok": True, "domain_count": 2, "errors": []}


def test_runtime_jobs_must_be_a_non_empty_list(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["creative"])
    project_registry = _project_registry(tmp_path, ["creative"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["runtime_jobs"] = []
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "runtime_jobs must be a non-empty list"
    ]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "domain_id",
            "missing",
            "runtime job creative-manifest-check references unknown domain: missing",
        ),
        (
            "owner",
            "runtime",
            "runtime job creative-manifest-check owner must be l4-kernel",
        ),
        (
            "action",
            "run_script",
            "runtime job creative-manifest-check action must be validate_manifest",
        ),
        (
            "writes",
            ["output.txt"],
            "runtime job creative-manifest-check must not declare Documents writes",
        ),
        (
            "fail_closed",
            False,
            "runtime job creative-manifest-check must be fail_closed",
        ),
    ],
)
def test_runtime_job_contract_fails_closed(
    field: str, value: object, expected: str, tmp_path: Path
) -> None:
    domain_registry = _domain_registry(tmp_path, ["creative"])
    project_registry = _project_registry(tmp_path, ["creative"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["runtime_jobs"][0][field] = value
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [expected]


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


def test_selected_domain_gateways_are_thin_ssot_projections(tmp_path: Path) -> None:
    domain_ids = ["vault", "work-weijian", "creative"]
    domain_registry = _domain_registry(tmp_path, domain_ids)
    project_registry = _project_registry(tmp_path, domain_ids)
    for domain_id in domain_ids:
        _write_gateways(tmp_path / "documents" / domain_id, domain_id)

    result = _run(domain_registry, project_registry, tuple(domain_ids))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ok": True,
        "domain_count": 3,
        "gateway_count": 3,
        "errors": [],
    }


def test_gateway_domain_context_must_match_manifest_id(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "wrong-domain")

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "vault/AGENTS.md must call domain_context for vault",
        "vault/CLAUDE.md must call domain_context for vault",
    ]


def test_gateway_rejects_physical_worktree_as_workspace_ssot(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "vault")
    for filename in ("CLAUDE.md", "AGENTS.md"):
        path = domain_root / filename
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "Workspace binding registry `documents-domain-projects`",
                "/Users/example/ws-documents-session/.omo/_truth/registry/documents-domain-projects.yaml",
            ),
            encoding="utf-8",
        )

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "vault/AGENTS.md must reference the logical Workspace binding registry",
        "vault/CLAUDE.md must reference the logical Workspace binding registry",
    ]


def test_gateway_rejects_documents_local_execution_instructions(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "vault")
    claude = domain_root / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8") + "\npython3 _runtime/controller.py\n",
        encoding="utf-8",
    )

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "vault/CLAUDE.md instructs Documents-local execution"
    ]


@pytest.mark.parametrize(
    "instruction",
    [
        "```sh\nmake -C app run\n```",
        "```sh\ncd _runtime && ./controller.py\n```",
        "`./app/server`",
        "```sh\nenv python3 _control/x.py\n```",
        "```sh\ncommand python3 _control/x.py\n```",
        "```sh\nxargs python3 _control/x.py\n```",
    ],
)
def test_gateway_rejects_common_documents_local_execution_forms(
    tmp_path: Path, instruction: str
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "vault")
    claude = domain_root / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8") + f"\n{instruction}\n",
        encoding="utf-8",
    )

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "vault/CLAUDE.md instructs Documents-local execution"
    ]


def test_gateway_allows_non_executable_prohibition_statement(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "vault")
    claude = domain_root / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8")
        + "\n不要执行或引导执行 Documents 内 `_runtime`、`_control` 脚本。\n",
        encoding="utf-8",
    )

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 0, result.stderr
