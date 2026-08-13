"""Contract tests for the thin Workspace/L4/OMO governance adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
import yaml


def test_governance_context_adapter_module_exists() -> None:
    assert importlib.util.find_spec("cockpit.adapters.governance_context") is not None


def _write_domain_registry(root: Path, *, domain_id: str = "vault") -> Path:
    domain_root = root / "domains" / domain_id
    domain_root.mkdir(parents=True)
    manifest = {
        "apiVersion": "l4/v1",
        "kind": "DomainManifest",
        "id": domain_id,
        "display_name": "@学习进化",
        "archetype": "private-core",
        "space_ref": "personal-space",
        "root": ".",
        "owners": ["personal-space-owner"],
        "principal_ref": "personal-space-owner",
        "default_sensitivity": "private",
        "default_visibility": "private",
        "sharing_policy": "explicit_publish",
        "retention": "permanent",
        "authority_policy": "canonical_write",
        "harness_profile_ref": "harness://private-core/v1",
        "lifecycle": "active",
        "policy_refs": [],
    }
    manifest_path = domain_root / "DOMAIN.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    registry = {
        "apiVersion": "l4/v1",
        "kind": "DomainRegistry",
        "id": "documents-test-registry",
        "space_ref": "personal-space",
        "path_base": "registry_file_parent",
        "manifests": [{"id": domain_id, "path": str(manifest_path.relative_to(root))}],
    }
    registry_path = root / "L4-DOMAIN-REGISTRY.yaml"
    registry_path.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")
    return registry_path


def _write_workspace_state(root: Path) -> None:
    system_path = root / ".omo" / "state" / "system.yaml"
    system_path.parent.mkdir(parents=True)
    system_path.write_text(
        yaml.safe_dump(
            {
                "current_phase": 49,
                "phase_status": "active",
                "next_milestone": "Documents 内容主权收敛",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    goals_path = root / ".omo" / "_truth" / "goals" / "current.yaml"
    goals_path.parent.mkdir(parents=True)
    goals_path.write_text(
        "status: active\nlifecycle: ssot\n---\ntheme: Goals 权威主题\ncurrent_wave: W5\ngoals:\n  - id: G-1\n    desc: Domain SSOT\n    status: active\n",
        encoding="utf-8",
    )


def test_resolve_workspace_root_ignores_compatibility_omo_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    _write_workspace_state(tmp_path)
    project_root = tmp_path / "projects"
    project_root.mkdir()
    (project_root / ".omo").symlink_to("../.omo", target_is_directory=True)
    source = project_root / "cockpit" / "src" / "cockpit" / "adapters" / "governance_context.py"
    monkeypatch.delenv("WORKSPACE_ROOT", raising=False)
    monkeypatch.setattr(gc, "__file__", str(source))

    assert gc.resolve_workspace_root() == tmp_path


def _write_binding_registry(root: Path, clients: dict[str, object]) -> None:
    skills_path = root / ".agents" / "skills" / "example"
    skills_path.mkdir(parents=True, exist_ok=True)
    (skills_path / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    binding_path = root / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    (binding_path.parent / "agent-workflows.yaml").write_text(
        "apiVersion: workspace.omostation/v1\nkind: AgentWorkflowRegistry\n",
        encoding="utf-8",
    )
    binding_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "workspace.omostation/v1",
                "kind": "DocumentsDomainProjects",
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
                "clients": clients,
                "profiles": {"content-domain": {"execution_policy": "workspace_only"}},
                "runtime_state": {
                    "owner": "runtime",
                    "environment_override": "OMOSTATION_RUNTIME_STATE_ROOT",
                    "default_home_relative": ".local/state/omostation/runtime",
                },
                "runtime_jobs": [
                    {
                        "id": "documents-weijian-facts-audit",
                        "domain_id": "vault",
                        "owner": "runtime-facts",
                        "action": "audit_structured_facts",
                        "evidence_relative_path": (
                            "control/evidence/documents-weijian-facts-audit/documents-weijian-facts-audit.json"
                        ),
                        "evidence_schema": "runtime.documents-facts-audit.evidence.v1",
                    },
                    {
                        "id": "documents-weijian-model-freshness",
                        "domain_id": "vault",
                        "owner": "runtime-control",
                        "action": "audit_model_freshness",
                        "evidence_relative_path": (
                            "control/evidence/documents-weijian-model-freshness/documents-weijian-model-freshness.json"
                        ),
                        "evidence_schema": "runtime.documents-model-freshness.evidence.v1",
                    },
                ],
                "domains": [{"id": "vault", "profile": "content-domain"}],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def _write_runtime_facts_receipt(
    root: Path,
    *,
    owner_status: str = "ok",
    job_status: str = "succeeded",
    exit_code: int = 0,
) -> Path:
    state_root = root / "runtime-state"
    receipt = (
        state_root / "control" / "evidence" / "documents-weijian-facts-audit" / "documents-weijian-facts-audit.json"
    )
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        json.dumps(
            {
                "job_id": "documents-weijian-facts-audit",
                "owner": "runtime-facts",
                "status": job_status,
                "exit_code": exit_code,
                "timed_out": False,
                "evidence_error": None,
                "owner_evidence": {
                    "schema": "runtime.documents-facts-audit.evidence.v1",
                    "status": owner_status,
                    "facts_total": 3,
                    "by_type": {"info": 2, "rule": 1},
                    "error_count": 0 if owner_status == "ok" else 1,
                    "warning_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    return state_root


def _write_runtime_controller_shadow_receipt(root: Path) -> Path:
    state_root = root / "runtime-state"
    receipt = (
        state_root
        / "control"
        / "evidence"
        / "documents-weijian-controller-shadow"
        / "documents-weijian-controller-shadow.json"
    )
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        json.dumps(
            {
                "job_id": "documents-weijian-controller-shadow",
                "owner": "runtime-control",
                "status": "failed",
                "exit_code": 1,
                "timed_out": False,
                "evidence_error": None,
                "owner_evidence": {
                    "schema": "runtime.documents-controller-shadow.evidence.v2",
                    "status": "shadow_observed",
                    "legacy_controller_replaced": False,
                    "cutover_ready": False,
                    "legacy_rule_ids": [
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
                    ],
                    "legacy_rule_count": 11,
                    "observed_rule_ids": ["CR01", "CR02", "CR03", "CR05"],
                    "observed_rule_count": 4,
                    "unobserved_rule_ids": [
                        "CR08",
                        "CR23",
                        "CR24",
                        "CR25",
                        "CR26",
                        "CR29",
                        "CR30",
                    ],
                    "unobserved_rule_count": 7,
                },
            }
        ),
        encoding="utf-8",
    )
    return state_root


def _write_runtime_model_freshness_receipt(
    root: Path,
    *,
    owner_status: str = "attention",
    job_status: str = "failed",
    exit_code: int = 1,
    owner_overrides: dict[str, object] | None = None,
    receipt_overrides: dict[str, object] | None = None,
) -> Path:
    state_root = root / "runtime-state"
    receipt = (
        state_root
        / "control"
        / "evidence"
        / "documents-weijian-model-freshness"
        / "documents-weijian-model-freshness.json"
    )
    receipt.parent.mkdir(parents=True)
    owner_evidence: dict[str, object] = {
        "schema": "runtime.documents-model-freshness.evidence.v1",
        "status": owner_status,
        "checked_on": "2026-08-14",
        "facts_last_reviewed": "2026-08-13",
        "model_markdown_count": 2,
        "fresh_model_count": 1 if owner_status != "unavailable" else 0,
        "stale_model_count": 1 if owner_status == "attention" else 0,
        "invalid_reviewed_count": 0,
        "unreadable_regular_file_count": 0,
        "error": None,
    }
    if owner_status == "ok":
        owner_evidence["fresh_model_count"] = 2
    elif owner_status == "unavailable":
        owner_evidence.update(
            {
                "facts_last_reviewed": None,
                "model_markdown_count": 0,
                "error": "facts_file_missing",
            }
        )
    owner_evidence.update(owner_overrides or {})
    payload: dict[str, object] = {
        "job_id": "documents-weijian-model-freshness",
        "owner": "runtime-control",
        "status": job_status,
        "exit_code": exit_code,
        "timed_out": False,
        "evidence_error": None,
        "owner_evidence": owner_evidence,
    }
    payload.update(receipt_overrides or {})
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    return state_root


def _adapter():
    from cockpit.adapters import governance_context

    return governance_context


def test_context_reads_workspace_and_validated_l4_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    _write_workspace_state(tmp_path)
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    monkeypatch.setattr(
        gc,
        "cards_status",
        lambda **_kwargs: {
            "schema": "cockpit.cards.v1",
            "status": "ok",
            "available": True,
            "items": [
                {
                    "id": "TASK-1",
                    "priority": "P0",
                    "status": "active",
                    "domain": "meta",
                    "title": "收敛入口",
                }
            ],
            "total": 1,
        },
    )

    result = gc.workspace_context(workspace_root=tmp_path)

    assert result["schema"] == "cockpit.governance-context.v1"
    assert result["status"] == "ok"
    assert result["phase"] == 49
    assert result["phase_status"] == "active"
    assert result["theme"] == "Goals 权威主题"
    assert result["current_wave"] == "W5"
    assert result["cards_summary"]["p0_open"] == 1
    assert result["domains"][0] == {
        "id": "vault",
        "name": "@学习进化",
        "type": "document",
        "path": str((tmp_path / "domains" / "vault").resolve()),
        "bos_uri": "bos://vault/**",
        "capabilities": ["knowledge.read", "knowledge.validate"],
        "exists": True,
    }


def test_missing_workspace_l4_and_omo_are_not_reported_healthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(tmp_path / "missing-registry.yaml"))

    def _missing_owner(*_args, **_kwargs):
        raise FileNotFoundError("omo missing")

    monkeypatch.setattr(gc, "_run_omo", _missing_owner)

    result = gc.workspace_context(workspace_root=tmp_path)

    assert result["status"] == "degraded"
    assert result["sources"]["workspace"]["status"] == "unavailable"
    assert result["sources"]["domains"]["status"] == "unavailable"
    assert result["sources"]["cards"]["status"] == "unavailable"
    assert result["phase"] is None
    assert result["domains"] == []


def test_cards_check_delegates_to_omo_and_preserves_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    seen: list[list[str]] = []

    def _run(arguments: list[str], **_kwargs):
        seen.append(arguments)
        return subprocess.CompletedProcess(arguments, 3, "⚠️ policy violation\n", "")

    monkeypatch.setattr(gc, "_run_omo", _run)

    result = gc.cards_check(workspace_root=tmp_path, card_id="TASK-1")

    assert seen == [["check"]]
    assert result["owner"] == "omo"
    assert result["available"] is True
    assert result["status"] == "violations"
    assert result["compliant"] is False
    assert result["returncode"] == 3
    assert result["requested_card_id"] == "TASK-1"
    assert result["scope"] == "all"
    assert result["violations"] == ["⚠️ policy violation"]


def test_cards_status_normalizes_owner_cli_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    output = "[P1] TASK-7  active        meta          Keep Workspace as SSOT\n1 cards\n"
    monkeypatch.setattr(
        gc,
        "_run_omo",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, output, ""),
    )

    result = gc.cards_status(workspace_root=tmp_path)

    assert result["status"] == "ok"
    assert result["total"] == 1
    assert result["items"] == [
        {
            "id": "TASK-7",
            "priority": "P1",
            "status": "active",
            "domain": "meta",
            "title": "Keep Workspace as SSOT",
        }
    ]


def test_domain_context_returns_identity_and_selected_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    binding_path = tmp_path / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    binding_path.parent.mkdir(parents=True)
    skills_path = tmp_path / ".agents" / "skills" / "example"
    skills_path.mkdir(parents=True)
    (skills_path / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    (binding_path.parent / "agent-workflows.yaml").write_text(
        "apiVersion: workspace.omostation/v1\nkind: AgentWorkflowRegistry\n",
        encoding="utf-8",
    )
    binding_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "workspace.omostation/v1",
                "kind": "DocumentsDomainProjects",
                "workspace_mcp": {"entrypoint": "cockpit-mcp", "transport": "stdio"},
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
                "clients": {"claude": {"instruction_file": "CLAUDE.md"}},
                "profiles": {
                    "content-domain": {
                        "allowed_workspace_tools": ["domain_context"],
                        "execution_policy": "workspace_only",
                    }
                },
                "domains": [{"id": "vault", "profile": "content-domain"}],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = gc.domain_context("vault", workspace_root=tmp_path)

    assert result["status"] == "ok"
    assert result["domain"]["id"] == "vault"
    assert result["domain"]["authority_policy"] == "canonical_write"
    assert result["binding"]["profile_id"] == "content-domain"
    assert result["binding"]["profile"]["execution_policy"] == "workspace_only"
    assert result["binding"]["workspace_mcp"]["entrypoint"] == "cockpit-mcp"
    assert result["binding"]["capability_routes"]["skills"] == {
        "owner": "workspace-skills",
        "registry_ref": ".agents/skills",
        "resolved_path": str(tmp_path / ".agents" / "skills"),
        "status": "ok",
    }
    assert "domains" not in result["binding"]


@pytest.mark.parametrize(
    "registry_ref",
    ["bos://shared/_control/SKILL-INDEX.md", ".agents/missing"],
)
def test_domain_context_degrades_for_invalid_capability_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registry_ref: str
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "CLAUDE.md"}})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    binding_path = tmp_path / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    raw = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    raw["capability_routes"]["skills"]["registry_ref"] = registry_ref
    binding_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = gc.domain_context("vault", workspace_root=tmp_path)

    assert result["status"] == "degraded"
    assert result["binding"]["status"] == "unavailable"
    assert "capability_routes.skills.registry_ref" in result["binding"]["error"]


def test_domain_context_keeps_valid_identity_when_binding_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_context("vault", workspace_root=tmp_path)

    assert result["status"] == "degraded"
    assert result["available"] is True
    assert result["domain"]["id"] == "vault"
    assert result["binding"]["status"] == "unavailable"


def test_domain_context_fails_closed_for_unknown_domain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_context("unknown", workspace_root=tmp_path)

    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["domain"] is None
    assert "unknown domain" in result["error"]


def test_domain_project_status_is_ok_when_identity_binding_and_gateways_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    domain_root = tmp_path / "domains" / "vault"
    (domain_root / "CLAUDE.md").write_text("# Vault", encoding="utf-8")
    (domain_root / "AGENTS.md").write_text("# Vault", encoding="utf-8")
    _write_binding_registry(
        tmp_path,
        {
            "claude": {"instruction_file": "CLAUDE.md"},
            "codex": {"instruction_file": "AGENTS.md"},
            "chatgpt_web": {"instruction_file": None},
        },
    )
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert result["schema"] == "cockpit.domain-project-status.v1"
    assert result["status"] == "ok"
    assert result["summary"] == {"ok": 1, "degraded": 0, "unavailable": 0}
    assert [gateway["status"] for gateway in result["domains"][0]["gateways"]] == ["present", "present"]


def test_domain_project_status_does_not_degrade_when_facts_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    domain_root = tmp_path / "domains" / "vault"
    (domain_root / "CLAUDE.md").write_text("# Vault", encoding="utf-8")
    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "CLAUDE.md"}})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert result["status"] == "ok"
    assert result["domains"][0]["facts"]["status"] == "missing"


def test_domain_project_status_degrades_when_binding_or_gateway_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    without_binding = gc.domain_project_status("vault", workspace_root=tmp_path)

    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "CLAUDE.md"}})
    without_gateway = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert without_binding["status"] == "degraded"
    assert without_binding["domains"][0]["binding"]["status"] == "unavailable"
    assert without_gateway["status"] == "degraded"
    assert without_gateway["domains"][0]["gateways"][0]["status"] == "missing"


def test_domain_project_status_degrades_when_binding_clients_are_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, ["not-a-client-mapping"])
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert result["status"] == "degraded"
    assert result["domains"][0]["binding"]["status"] == "unavailable"


def test_domain_project_status_does_not_follow_symlink_or_fifo_gateways(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    domain_root = tmp_path / "domains" / "vault"
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (domain_root / "CLAUDE.md").symlink_to(outside)
    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "CLAUDE.md"}})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    symlink_result = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert symlink_result["status"] == "degraded"
    assert symlink_result["domains"][0]["gateways"][0]["status"] == "invalid"

    if hasattr(os, "mkfifo"):
        (domain_root / "CLAUDE.md").unlink()
        os.mkfifo(domain_root / "CLAUDE.md")
        fifo_result = gc.domain_project_status("vault", workspace_root=tmp_path)
        assert fifo_result["status"] == "degraded"
        assert fifo_result["domains"][0]["gateways"][0]["status"] == "invalid"


def test_domain_project_status_rejects_directory_and_parent_escape_gateways(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    domain_root = tmp_path / "domains" / "vault"
    (domain_root / "guidance").mkdir()
    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "guidance"}})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    directory_result = gc.domain_project_status("vault", workspace_root=tmp_path)

    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "../outside.md"}})
    escaped_result = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert directory_result["status"] == "degraded"
    assert directory_result["domains"][0]["gateways"][0]["status"] == "invalid"
    assert escaped_result["status"] == "degraded"
    assert escaped_result["domains"][0]["gateways"][0]["status"] == "invalid"


def test_domain_project_status_is_unavailable_for_unknown_domain_or_bad_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    unknown = gc.domain_project_status("unknown", workspace_root=tmp_path)
    registry_path.write_text("manifests: [", encoding="utf-8")
    malformed = gc.domain_project_status("vault", workspace_root=tmp_path)

    assert unknown["status"] == "unavailable"
    assert unknown["domains"] == []
    assert malformed["status"] == "unavailable"


def test_domain_facts_audit_reports_present_file_and_local_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_path = _write_domain_registry(tmp_path)
    facts = tmp_path / "domains" / "vault" / "_entities" / "facts.md"
    facts.parent.mkdir()
    facts.write_text("# facts\n", encoding="utf-8")
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = _adapter().domain_facts_audit("vault")

    assert result["status"] == "ok"
    assert result["summary"] == {"present": 1, "missing": 0, "unreadable": 0, "invalid": 0}
    assert (
        result["domains"][0]["facts"]["modified_on"] == datetime.fromtimestamp(facts.stat().st_mtime).date().isoformat()
    )


def test_domain_facts_audit_is_unavailable_when_registry_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    source = tmp_path / "L4-DOMAIN-REGISTRY.yaml"
    monkeypatch.setattr(gc, "_load_domains", lambda *_args, **_kwargs: (source, object(), []))

    result = gc.domain_facts_audit()

    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["total"] == 0
    assert result["domains"] == []
    assert result["error"] == "no registered domain projects"


def test_domain_facts_audit_does_not_read_facts_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    facts = tmp_path / "domains" / "vault" / "_entities" / "facts.md"
    facts.parent.mkdir()
    facts.write_text("# facts\n", encoding="utf-8")
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    def fail_if_content_is_read(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("facts audit must not read artifact content")

    monkeypatch.setattr(gc.os, "read", fail_if_content_is_read)

    result = gc.domain_facts_audit("vault")

    assert result["status"] == "ok"
    assert result["domains"][0]["facts"]["status"] == "present"


def test_domain_facts_audit_reports_missing_and_static_artifacts_as_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    assert _adapter().domain_facts_audit("vault")["status"] == "violations"

    facts = tmp_path / "domains" / "vault" / "_entities" / "facts.md"
    facts.parent.mkdir()
    facts.symlink_to(tmp_path / "outside.md")
    result = _adapter().domain_facts_audit("vault")

    assert result["status"] == "violations"
    assert result["domains"][0]["facts"]["status"] == "invalid"

    if hasattr(os, "mkfifo"):
        facts.unlink()
        os.mkfifo(facts)
        fifo_result = _adapter().domain_facts_audit("vault")
        assert fifo_result["status"] == "violations"
        assert fifo_result["domains"][0]["facts"]["status"] == "invalid"


def test_domain_facts_audit_is_unavailable_without_authority_or_for_unknown_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    assert _adapter().domain_facts_audit("unknown")["status"] == "unavailable"
    registry_path.write_text("manifests: [", encoding="utf-8")
    assert _adapter().domain_facts_audit()["status"] == "unavailable"


def test_domain_facts_validation_uses_only_the_runtime_bounded_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_facts_receipt(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_facts_validation_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["schema"] == "cockpit.domain-facts-validation.v1"
    assert result["status"] == "ok"
    assert result["available"] is True
    assert result["validation"] == {
        "facts_total": 3,
        "by_type": {"info": 2, "rule": 1},
        "error_count": 0,
        "warning_count": 0,
    }
    assert result["job"] == {
        "id": "documents-weijian-facts-audit",
        "owner": "runtime-facts",
        "action": "audit_structured_facts",
    }


def test_domain_facts_validation_reports_runtime_semantic_failure_as_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_facts_receipt(tmp_path, owner_status="invalid", job_status="failed", exit_code=1)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_facts_validation_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["status"] == "violations"
    assert result["available"] is True
    assert result["validation"]["error_count"] == 1


def test_domain_facts_validation_fails_closed_for_missing_or_symlinked_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    state_root = tmp_path / "runtime-state"

    missing = gc.domain_facts_validation_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert missing["status"] == "unavailable"
    assert missing["available"] is False

    state_root = _write_runtime_facts_receipt(tmp_path)
    receipt = (
        state_root / "control" / "evidence" / "documents-weijian-facts-audit" / "documents-weijian-facts-audit.json"
    )
    target = tmp_path / "caller-owned-receipt.json"
    target.write_text(receipt.read_text(encoding="utf-8"), encoding="utf-8")
    receipt.unlink()
    receipt.symlink_to(target)

    symlinked = gc.domain_facts_validation_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert symlinked["status"] == "unavailable"
    assert symlinked["available"] is False


def test_domain_model_freshness_projects_only_the_bounded_runtime_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_model_freshness_receipt(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["schema"] == "cockpit.domain-model-freshness.v1"
    assert result["status"] == "attention"
    assert result["available"] is True
    assert result["freshness"] == {
        "checked_on": "2026-08-14",
        "facts_last_reviewed": "2026-08-13",
        "model_markdown_count": 2,
        "fresh_model_count": 1,
        "stale_model_count": 1,
        "invalid_reviewed_count": 0,
        "unreadable_regular_file_count": 0,
        "error": None,
    }
    assert result["job"] == {
        "id": "documents-weijian-model-freshness",
        "owner": "runtime-control",
        "action": "audit_model_freshness",
    }
    assert set(result["sources"]) == {
        "domain_registry",
        "binding_registry",
        "runtime_evidence",
    }
    assert "fixture-private-model.md" not in json.dumps(result)
    assert "fixture private model body" not in json.dumps(result)


@pytest.mark.parametrize("registry_state", ["missing", "malformed"])
def test_domain_model_freshness_redacts_documents_registry_failures(
    tmp_path: Path,
    registry_state: str,
) -> None:
    gc = _adapter()
    workspace_root = tmp_path / "workspace"
    documents_root = tmp_path / "Documents-private"
    registry_path = documents_root / "private-domain-registry.yaml"
    documents_root.mkdir()
    _write_binding_registry(workspace_root, {})
    if registry_state == "malformed":
        registry_path.write_text("not: [valid", encoding="utf-8")

    result = gc.domain_model_freshness_status(
        "vault",
        workspace_root=workspace_root,
        registry_path=registry_path,
        documents_root=documents_root,
    )

    encoded = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["error"] == "domain_registry_unavailable"
    assert result["sources"]["domain_registry"] == "l4-domain-registry"
    assert str(documents_root) not in encoded
    assert registry_path.name not in encoded
    assert str(registry_path) not in encoded


@pytest.mark.parametrize(
    ("owner_status", "job_status", "exit_code", "available"),
    [
        ("ok", "succeeded", 0, True),
        ("attention", "failed", 1, True),
        ("unavailable", "failed", 2, False),
    ],
)
def test_domain_model_freshness_accepts_only_contract_status_relationships(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_status: str,
    job_status: str,
    exit_code: int,
    available: bool,
) -> None:
    gc = _adapter()
    workspace_root = tmp_path / "workspace"
    documents_root = tmp_path / "Documents"
    registry_path = _write_domain_registry(documents_root)
    _write_binding_registry(workspace_root, {})
    state_root = _write_runtime_model_freshness_receipt(
        workspace_root,
        owner_status=owner_status,
        job_status=job_status,
        exit_code=exit_code,
    )

    result = gc.domain_model_freshness_status(
        "vault",
        workspace_root=workspace_root,
        registry_path=registry_path,
        documents_root=documents_root,
        runtime_state_root=state_root,
    )

    assert result["status"] == owner_status
    assert result["available"] is available
    assert result["schema"] == "cockpit.domain-model-freshness.v1"
    assert result["sources"]["domain_registry"] == "l4-domain-registry"
    assert str(documents_root) not in json.dumps(result)
    if owner_status == "unavailable":
        assert result["freshness"]["error"] == "facts_file_missing"


@pytest.mark.parametrize("scenario", ["ok", "valid_unavailable", "adapter_unavailable"])
def test_domain_model_freshness_sources_never_expose_physical_paths(
    tmp_path: Path,
    scenario: str,
) -> None:
    gc = _adapter()
    documents_root = tmp_path / "Documents-private"
    workspace_root = documents_root / "workspace"
    registry_path = _write_domain_registry(documents_root)
    _write_binding_registry(workspace_root, {})
    runtime_root = tmp_path / "runtime-state"
    if scenario != "adapter_unavailable":
        runtime_root = _write_runtime_model_freshness_receipt(
            tmp_path,
            owner_status="ok" if scenario == "ok" else "unavailable",
            job_status="succeeded" if scenario == "ok" else "failed",
            exit_code=0 if scenario == "ok" else 2,
        )

    result = gc.domain_model_freshness_status(
        "vault",
        workspace_root=workspace_root,
        registry_path=registry_path,
        documents_root=documents_root,
        runtime_state_root=runtime_root,
    )

    expected_status = {
        "ok": "ok",
        "valid_unavailable": "unavailable",
        "adapter_unavailable": "unavailable",
    }[scenario]
    assert result["status"] == expected_status
    if scenario == "valid_unavailable":
        assert result["freshness"]["error"] == "facts_file_missing"
    if scenario == "adapter_unavailable":
        assert result["error"] == "runtime_receipt_unavailable"
    encoded = json.dumps(result, ensure_ascii=False)
    assert result["sources"]["binding_registry"] == "workspace-documents-domain-projects"
    assert all(not Path(source).is_absolute() for source in result["sources"].values())
    assert str(documents_root) not in encoded
    assert str(workspace_root) not in encoded


@pytest.mark.parametrize(
    "owner_overrides",
    [
        {"model_markdown_count": True},
        {"model_markdown_count": -1},
        {"fresh_model_count": 2},
        {"checked_on": "2026-02-30"},
        {"facts_last_reviewed": "2026-8-13"},
        {"error": "private/model.md"},
        {"private_model_name": "fixture-private-model.md"},
    ],
)
def test_domain_model_freshness_rejects_malformed_owner_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_overrides: dict[str, object],
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_model_freshness_receipt(
        tmp_path,
        owner_overrides=owner_overrides,
    )
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["schema"] == "cockpit.domain-model-freshness.v1"
    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["freshness"] is None
    assert result["error"] == "runtime_receipt_unavailable"


@pytest.mark.parametrize(
    "receipt_overrides",
    [
        {"job_id": "wrong-job"},
        {"owner": "wrong-owner"},
        {"status": "succeeded", "exit_code": 1},
        {"status": "failed", "exit_code": 0},
        {"status": "failed", "exit_code": 2},
        {"timed_out": True},
        {"evidence_error": "private failure"},
    ],
)
def test_domain_model_freshness_rejects_malformed_runtime_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt_overrides: dict[str, object],
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_model_freshness_receipt(
        tmp_path,
        receipt_overrides=receipt_overrides,
    )
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["schema"] == "cockpit.domain-model-freshness.v1"
    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["error"] == "runtime_receipt_unavailable"


def test_domain_model_freshness_fails_closed_for_missing_symlinked_and_oversized_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    state_root = tmp_path / "runtime-state"

    missing = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert missing["status"] == "unavailable"
    assert missing["available"] is False
    assert missing["error"] == "runtime_receipt_unavailable"

    state_root = _write_runtime_model_freshness_receipt(tmp_path)
    receipt = (
        state_root
        / "control"
        / "evidence"
        / "documents-weijian-model-freshness"
        / "documents-weijian-model-freshness.json"
    )
    valid_receipt = receipt.read_bytes()
    receipt.write_text("{", encoding="utf-8")
    malformed = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert malformed["status"] == "unavailable"
    assert malformed["available"] is False
    assert malformed["error"] == "runtime_receipt_unavailable"

    receipt.write_bytes(valid_receipt)
    target = tmp_path / "caller-owned-model-freshness.json"
    target.write_text(receipt.read_text(encoding="utf-8"), encoding="utf-8")
    receipt.unlink()
    receipt.symlink_to(target)
    symlinked = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert symlinked["status"] == "unavailable"
    assert symlinked["available"] is False
    assert symlinked["error"] == "runtime_receipt_unavailable"

    receipt.unlink()
    receipt.write_bytes(b"{" + b" " * (32 * 1024))
    oversized = gc.domain_model_freshness_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)
    assert oversized["status"] == "unavailable"
    assert oversized["available"] is False
    assert oversized["error"] == "runtime_receipt_unavailable"


@pytest.mark.parametrize(
    ("mutation", "domain_id", "expected_error"),
    [
        ("duplicate", "vault", "runtime_job_unavailable"),
        ("wrong_action", "vault", "runtime_job_unavailable"),
        ("wrong_owner", "vault", "runtime_job_unavailable"),
        ("wrong_schema", "vault", "runtime_job_unavailable"),
        ("traversal", "vault", "runtime_job_unavailable"),
        ("wrong_safe_path", "vault", "runtime_job_unavailable"),
        ("unchanged", "unknown", "domain_not_registered"),
    ],
)
def test_domain_model_freshness_rejects_invalid_binding_or_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    domain_id: str,
    expected_error: str,
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    binding_path = tmp_path / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    binding = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    job = next(item for item in binding["runtime_jobs"] if item["action"] == "audit_model_freshness")
    if mutation == "duplicate":
        binding["runtime_jobs"].append(dict(job))
    elif mutation == "wrong_action":
        job["action"] = "audit_model_freshness_wrong"
    elif mutation == "wrong_owner":
        job["owner"] = "runtime-facts"
    elif mutation == "wrong_schema":
        job["evidence_schema"] = "runtime.documents-model-freshness.evidence.v0"
    elif mutation == "traversal":
        job["evidence_relative_path"] = "../private-model.json"
    elif mutation == "wrong_safe_path":
        job["evidence_relative_path"] = "control/evidence/sibling/sibling.json"
    binding_path.write_text(yaml.safe_dump(binding, sort_keys=False), encoding="utf-8")
    state_root = _write_runtime_model_freshness_receipt(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_model_freshness_status(domain_id, workspace_root=tmp_path, runtime_state_root=state_root)

    assert result["schema"] == "cockpit.domain-model-freshness.v1"
    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["error"] == expected_error


def test_domain_model_freshness_maps_binding_and_runtime_state_failures_to_stable_categories(tmp_path: Path) -> None:
    gc = _adapter()
    workspace_root = tmp_path / "workspace"
    documents_root = tmp_path / "Documents-private"
    registry_path = _write_domain_registry(documents_root)
    workspace_root.mkdir()

    missing_binding = gc.domain_model_freshness_status(
        "vault",
        workspace_root=workspace_root,
        registry_path=registry_path,
        documents_root=documents_root,
    )
    assert missing_binding["error"] == "domain_binding_unavailable"

    _write_binding_registry(workspace_root, {})
    overlapping_state = gc.domain_model_freshness_status(
        "vault",
        workspace_root=workspace_root,
        registry_path=registry_path,
        documents_root=documents_root,
        runtime_state_root=documents_root / "runtime-state",
    )
    assert overlapping_state["error"] == "runtime_state_unavailable"

    for result in (missing_binding, overlapping_state):
        encoded = json.dumps(result, ensure_ascii=False)
        assert result["status"] == "unavailable"
        assert str(documents_root) not in encoded
        assert registry_path.name not in encoded


def test_domain_model_freshness_never_reads_documents_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    state_root = _write_runtime_model_freshness_receipt(tmp_path)
    documents_root = tmp_path / "documents-content"
    domain_root = documents_root / "vault"
    models_root = domain_root / "_entities" / "models"
    models_root.mkdir(parents=True)
    models_root.joinpath("fixture-private-model.md").write_text(
        "last-reviewed: 2026-08-01\nfixture private model body\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    monkeypatch.setattr(
        gc,
        "_load_domains",
        lambda *_args, **_kwargs: (
            registry_path,
            object(),
            [{"id": "vault", "path": str(domain_root)}],
        ),
    )
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if documents_root in path.parents or path == documents_root:
            raise AssertionError("model freshness projection must not read Documents content")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    result = gc.domain_model_freshness_status(
        "vault",
        workspace_root=tmp_path,
        documents_root=documents_root,
        runtime_state_root=state_root,
    )

    assert result["status"] == "attention"
    assert result["freshness"]["stale_model_count"] == 1


def test_domain_controller_shadow_reads_only_the_registered_incomplete_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gc = _adapter()
    registry_path = _write_domain_registry(tmp_path)
    _write_binding_registry(tmp_path, {})
    binding_path = tmp_path / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    binding = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    binding["runtime_jobs"].append(
        {
            "id": "documents-weijian-controller-shadow",
            "domain_id": "vault",
            "owner": "runtime-control",
            "action": "shadow_legacy_controller",
            "evidence_relative_path": (
                "control/evidence/documents-weijian-controller-shadow/documents-weijian-controller-shadow.json"
            ),
            "evidence_schema": "runtime.documents-controller-shadow.evidence.v2",
        }
    )
    binding_path.write_text(yaml.safe_dump(binding, sort_keys=False), encoding="utf-8")
    state_root = _write_runtime_controller_shadow_receipt(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = gc.domain_controller_shadow_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert result == {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "shadow_observed",
        "available": True,
        "domain_id": "vault",
        "job": {
            "id": "documents-weijian-controller-shadow",
            "owner": "runtime-control",
            "action": "shadow_legacy_controller",
        },
        "shadow": {
            "cutover_ready": False,
            "legacy_controller_replaced": False,
            "legacy_rule_ids": [
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
            ],
            "observed_rule_ids": ["CR01", "CR02", "CR03", "CR05"],
            "unobserved_rule_ids": [
                "CR08",
                "CR23",
                "CR24",
                "CR25",
                "CR26",
                "CR29",
                "CR30",
            ],
        },
        "sources": {
            "domain_registry": str(registry_path),
            "binding_registry": str(binding_path),
            "runtime_evidence": str(
                state_root
                / "control"
                / "evidence"
                / "documents-weijian-controller-shadow"
                / "documents-weijian-controller-shadow.json"
            ),
        },
    }

    evidence_path = (
        state_root
        / "control"
        / "evidence"
        / "documents-weijian-controller-shadow"
        / "documents-weijian-controller-shadow.json"
    )
    receipt = json.loads(evidence_path.read_text(encoding="utf-8"))
    receipt["exit_code"] = "1"
    evidence_path.write_text(json.dumps(receipt), encoding="utf-8")

    malformed = gc.domain_controller_shadow_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert malformed["status"] == "unavailable"
    assert malformed["available"] is False
    assert malformed["schema"] == "cockpit.domain-controller-shadow.v2"
    assert "observed shadow status" in malformed["error"]

    receipt["exit_code"] = 1
    receipt["owner_evidence"]["schema"] = "runtime.documents-controller-shadow.evidence.v1"
    evidence_path.write_text(json.dumps(receipt), encoding="utf-8")

    legacy_schema = gc.domain_controller_shadow_status("vault", workspace_root=tmp_path, runtime_state_root=state_root)

    assert legacy_schema["status"] == "unavailable"
    assert legacy_schema["available"] is False
    assert legacy_schema["schema"] == "cockpit.domain-controller-shadow.v2"
    assert "invalid controller shadow schema" in legacy_schema["error"]


def test_kems_status_leaves_full_content_scan_to_explicit_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))

    result = _adapter().kems_status(documents_root=tmp_path)

    assert result["status"] == "degraded"
    assert result["content_audit"] == {
        "owner": "l4-kernel",
        "status": "not_run",
        "available": False,
        "root": str(tmp_path.resolve()),
        "reason": "full Documents content audit is on-demand; run cockpit kems scan",
    }


def test_dashboard_governance_routes_use_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from cockpit.dashboard import routes

    monkeypatch.setattr(
        routes.governance_context,
        "workspace_context",
        lambda: {"schema": "context.v1", "status": "degraded", "available": False},
    )
    context_response = asyncio.run(routes.api_context())
    assert context_response.status_code == 503

    monkeypatch.setattr(
        routes.governance_context,
        "cards_status",
        lambda: {"schema": "cards.v1", "status": "ok", "available": True, "items": []},
    )
    cards_response = asyncio.run(routes.api_cards())
    assert cards_response.status_code == 200
    assert json.loads(cards_response.body)["schema"] == "cards.v1"

    monkeypatch.setattr(
        routes.governance_context,
        "cards_check",
        lambda: {"schema": "check.v1", "status": "violations", "available": True, "returncode": 1},
    )
    check_response = asyncio.run(routes.api_cards_check())
    assert check_response.status_code == 200
    assert json.loads(check_response.body)["returncode"] == 1


def test_no_production_reference_to_removed_cockpit_mcp_module() -> None:
    package_root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in package_root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        if "cockpit.scripts.cockpit_mcp" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(package_root)))
    assert offenders == []
