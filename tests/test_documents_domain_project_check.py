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
    skills_path = tmp_path / ".agents" / "skills" / "example"
    skills_path.mkdir(parents=True)
    (skills_path / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    registry_dir = tmp_path / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "agent-workflows.yaml").write_text(
        "apiVersion: workspace.omostation/v1\nkind: AgentWorkflowRegistry\n",
        encoding="utf-8",
    )
    profile_generator = tmp_path / "bin" / "gac" / "documents-codex-profile.py"
    profile_generator.parent.mkdir(parents=True)
    profile_generator.write_text("# profile generator\n", encoding="utf-8")
    path = registry_dir / "documents-domain-projects.yaml"
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
                        "registry_ref": ".agents/skills",
                    },
                    "workflows": {
                        "owner": "workspace-workflow-mesh",
                        "registry_ref": ".omo/_truth/registry/agent-workflows.yaml",
                    },
                },
                "clients": {
                    "claude": {
                        "instruction_file": "CLAUDE.md",
                        "mcp_scope": "user",
                    },
                    "codex": {
                        "instruction_file": "AGENTS.md",
                        "mcp_scope": "user_or_project",
                        "profile_contract": {
                            "name": "documents",
                            "owner": "workspace",
                            "generator_ref": "bin/gac/documents-codex-profile.py",
                            "exclusive_mcp_server": "cockpit",
                            "approval_mode": "approve",
                            "skill_policy": "disable_user_local",
                        },
                    },
                    "agents_compatible": {
                        "instruction_file": "AGENTS.md",
                        "mcp_scope": "client",
                    },
                    "chatgpt_web": {
                        "instruction_file": None,
                        "mcp_scope": "public_https_or_secure_tunnel",
                        "requires_developer_mode": True,
                        "setup_ref": "https://developers.openai.com/plugins/deploy/connect-chatgpt",
                        "tunnel_ref": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
                    },
                },
                "profiles": {
                    "content-domain": {
                        "allowed_workspace_tools": [
                            "workspace_context",
                            "domain_context",
                        ],
                        "skill_route": "skills",
                        "workflow_route": "workflows",
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
    gateway_domain_ids: tuple[str, ...] | None = None,
    *,
    prepare_default_gateways: bool = True,
) -> subprocess.CompletedProcess[str]:
    if gateway_domain_ids is None and prepare_default_gateways:
        raw = yaml.safe_load(domain_registry.read_text(encoding="utf-8"))
        for entry in raw["manifests"]:
            manifest_path = domain_registry.parent / entry["path"]
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            _write_gateways(manifest_path.parent, manifest["id"])
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
                for domain_id in gateway_domain_ids or ()
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
ChatGPT Web uses public HTTPS MCP or Secure MCP Tunnel.
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
    assert payload == {
        "ok": True,
        "domain_count": 2,
        "gateway_count": 2,
        "errors": [],
    }


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "owner",
            "documents",
            "clients.codex.profile_contract.owner must be workspace",
        ),
        (
            "exclusive_mcp_server",
            "runtime",
            "clients.codex.profile_contract.exclusive_mcp_server must match workspace_mcp.server",
        ),
        (
            "approval_mode",
            "auto",
            "clients.codex.profile_contract.approval_mode must be approve",
        ),
        (
            "skill_policy",
            "all_user_skills",
            "clients.codex.profile_contract.skill_policy must be disable_user_local",
        ),
    ],
)
def test_codex_profile_contract_fails_closed(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["clients"]["codex"]["profile_contract"][field] = value
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [expected]


def test_codex_profile_generator_must_be_workspace_relative(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["clients"]["codex"]["profile_contract"]["generator_ref"] = (
        "../Documents/profile.py"
    )
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "clients.codex.profile_contract.generator_ref must be a Workspace-relative file"
    ]


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("clients",), None, "clients must be a mapping"),
        (
            ("clients", "chatgpt_web"),
            None,
            "clients.chatgpt_web must be a mapping",
        ),
        (
            ("clients", "chatgpt_web", "instruction_file"),
            "AGENTS.md",
            "clients.chatgpt_web.instruction_file must be null",
        ),
        (
            ("clients", "chatgpt_web", "instruction_file"),
            None,
            "clients.chatgpt_web.instruction_file must be null",
        ),
        (
            ("clients", "chatgpt_web", "mcp_scope"),
            "user_or_project",
            "clients.chatgpt_web.mcp_scope must be public_https_or_secure_tunnel",
        ),
        (
            ("clients", "chatgpt_web", "requires_developer_mode"),
            False,
            "clients.chatgpt_web.requires_developer_mode must be true",
        ),
        (
            ("clients", "chatgpt_web", "requires_developer_mode"),
            1,
            "clients.chatgpt_web.requires_developer_mode must be true",
        ),
        (
            ("clients", "chatgpt_web", "setup_ref"),
            "https://example.test/connect-chatgpt",
            "clients.chatgpt_web.setup_ref must be https://developers.openai.com/plugins/deploy/connect-chatgpt",
        ),
        (
            ("clients", "chatgpt_web", "tunnel_ref"),
            "https://example.test/secure-mcp-tunnels",
            "clients.chatgpt_web.tunnel_ref must be https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
        ),
    ],
)
def test_chatgpt_web_contract_fails_closed(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
    expected: str,
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    target = raw
    for key in path[:-1]:
        target = target[key]
    if value is None:
        target.pop(path[-1])
    else:
        target[path[-1]] = value
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [expected]


@pytest.mark.parametrize(
    "instruction_file",
    [
        "../../escape/AGENTS.md",
        "/private/tmp/escape/AGENTS.md",
        "nested/AGENTS.md",
    ],
)
def test_client_instruction_file_must_be_a_safe_filename(
    tmp_path: Path, instruction_file: str
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["clients"]["agents_compatible"]["instruction_file"] = instruction_file
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        f"clients instruction_file must be a safe filename: {instruction_file}"
    ]


def test_gateway_file_must_not_be_a_symlink(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    domain_root = tmp_path / "documents" / "vault"
    _write_gateways(domain_root, "vault")
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    _write_gateways(outside_root, "vault")
    agent_gateway = domain_root / "AGENTS.md"
    agent_gateway.unlink()
    agent_gateway.symlink_to(outside_root / "AGENTS.md")

    result = _run(
        domain_registry,
        project_registry,
        ("vault",),
        prepare_default_gateways=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "vault/AGENTS.md must not be a symlink"
    ]


def test_default_gateway_check_fails_if_registered_projection_is_missing(
    tmp_path: Path,
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault", "shared"])
    project_registry = _project_registry(tmp_path, ["vault", "shared"])
    _write_gateways(tmp_path / "documents" / "vault", "vault")

    result = _run(
        domain_registry,
        project_registry,
        prepare_default_gateways=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["gateway_count"] == 2
    assert len(payload["errors"]) == 2
    assert payload["errors"][0].startswith("shared/AGENTS.md unavailable:")
    assert payload["errors"][1].startswith("shared/CLAUDE.md unavailable:")


def test_explicit_gateway_selector_only_checks_requested_domain(
    tmp_path: Path,
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault", "shared"])
    project_registry = _project_registry(tmp_path, ["vault", "shared"])
    _write_gateways(tmp_path / "documents" / "vault", "vault")

    result = _run(domain_registry, project_registry, ("vault",))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ok": True,
        "domain_count": 2,
        "gateway_count": 1,
        "errors": [],
    }


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


@pytest.mark.parametrize(
    "invalid_ref",
    [
        "bos://shared/_control/SKILL-INDEX.md",
        "/Users/example/Documents/@公共/_control/SKILL-INDEX.md",
        "../Documents/@公共/_control/SKILL-INDEX.md",
    ],
)
def test_capability_routes_must_use_workspace_relative_paths(
    tmp_path: Path, invalid_ref: str
) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["capability_routes"]["skills"]["registry_ref"] = invalid_ref
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "capability_routes.skills.registry_ref must be a Workspace-relative path"
    ]


def test_capability_route_source_must_exist(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["capability_routes"]["skills"]["registry_ref"] = ".agents/missing"
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "capability_routes.skills.registry_ref is unavailable: .agents/missing"
    ]


def test_capability_route_owner_must_match_workspace_authority(tmp_path: Path) -> None:
    domain_registry = _domain_registry(tmp_path, ["vault"])
    project_registry = _project_registry(tmp_path, ["vault"])
    raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    raw["capability_routes"]["skills"]["owner"] = "documents"
    project_registry.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(domain_registry, project_registry)

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"] == [
        "capability_routes.skills.owner must be workspace-skills"
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
