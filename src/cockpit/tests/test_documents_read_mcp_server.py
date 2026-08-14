from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import os
import tomllib
from pathlib import Path

import pytest

EXPECTED_TOOLS = {
    "workspace_context",
    "domain_context",
    "cards_status",
    "cards_check",
    "domain_facts_validation_status",
    "domain_controller_shadow_status",
    "domain_model_freshness_status",
    "domain_sanyi_status_consistency_status",
}


def _server():
    assert importlib.util.find_spec("cockpit.documents_read_mcp_server") is not None
    return importlib.import_module("cockpit.documents_read_mcp_server")


def test_documents_read_server_exposes_only_profile_tools() -> None:
    server = _server()

    tools = asyncio.run(server.mcp.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_documents_read_server_has_dedicated_entrypoint() -> None:
    project = tomllib.loads((Path(__file__).resolve().parents[3] / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["scripts"]["cockpit-documents-mcp"] == ("cockpit.documents_read_mcp_server:main")


def test_documents_read_server_discovers_workspace_without_overriding_explicit_root(
    tmp_path: Path, monkeypatch
) -> None:
    server = _server()
    workspace = tmp_path / "workspace"
    registry = workspace / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text("clients: {}\n", encoding="utf-8")
    projects = workspace / "projects"
    projects.mkdir()
    (projects / ".omo").symlink_to("../.omo", target_is_directory=True)
    source = workspace / "projects" / "cockpit" / "src" / "cockpit" / "server.py"

    monkeypatch.delenv("WORKSPACE_ROOT", raising=False)
    server._configure_workspace_root(source)
    assert os.environ["WORKSPACE_ROOT"] == str(workspace)

    explicit = tmp_path / "explicit"
    monkeypatch.setenv("WORKSPACE_ROOT", str(explicit))
    server._configure_workspace_root(source)
    assert os.environ["WORKSPACE_ROOT"] == str(explicit)


def test_domain_context_delegates_to_cockpit_authority(monkeypatch) -> None:
    server = _server()
    seen: list[str] = []
    payload = {
        "schema": "cockpit.domain-context.v1",
        "status": "ok",
        "available": True,
    }
    monkeypatch.setattr(
        server.governance_context,
        "domain_context",
        lambda domain_id: seen.append(domain_id) or payload,
    )

    assert json.loads(server.domain_context("work-weijian")) == payload
    assert seen == ["work-weijian"]


def test_domain_context_redacts_documents_root_from_mcp_envelope(tmp_path: Path, monkeypatch) -> None:
    server = _server()
    documents_root = tmp_path / "Documents"
    payload = {
        "schema": "cockpit.domain-context.v1",
        "status": "ok",
        "available": True,
        "domain_id": "work-weijian",
        "domain": {
            "id": "work-weijian",
            "path": str(documents_root / "@工作文档" / "卫健委"),
        },
        "binding": {
            "status": "ok",
            "profile_id": "content-domain",
            "capability_routes": {"skills": {"status": "ok"}},
        },
        "sources": {"domain_registry": str(documents_root / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml")},
    }
    monkeypatch.setenv("L4_DOCUMENTS_ROOT", str(documents_root))
    monkeypatch.setattr(server.governance_context, "domain_context", lambda _domain_id: payload)

    serialized = server.domain_context("work-weijian")
    result = json.loads(serialized)

    assert str(documents_root) not in serialized
    assert result["domain_id"] == "work-weijian"
    assert result["binding"]["profile_id"] == "content-domain"
    assert result["binding"]["capability_routes"]["skills"]["status"] == "ok"


def test_facts_validation_delegates_to_cockpit_authority(monkeypatch) -> None:
    server = _server()
    seen: list[str] = []
    payload = {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": "ok",
        "available": True,
    }
    monkeypatch.setattr(
        server.governance_context,
        "domain_facts_validation_status",
        lambda domain_id: seen.append(domain_id) or payload,
    )

    assert json.loads(server.domain_facts_validation_status("work-weijian")) == payload
    assert seen == ["work-weijian"]


def test_controller_shadow_delegates_to_cockpit_authority(monkeypatch) -> None:
    server = _server()
    seen: list[str] = []
    payload = {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "shadow_observed",
        "available": True,
    }
    monkeypatch.setattr(
        server.governance_context,
        "domain_controller_shadow_status",
        lambda domain_id: seen.append(domain_id) or payload,
    )

    assert json.loads(server.domain_controller_shadow_status("work-weijian")) == payload
    assert seen == ["work-weijian"]


@pytest.mark.parametrize(
    "tool_name",
    ["domain_model_freshness_status", "domain_sanyi_status_consistency_status"],
)
def test_receipt_projections_delegate_to_cockpit_authority(monkeypatch, tool_name: str) -> None:
    server = _server()
    seen: list[str] = []
    payload = {"schema": f"cockpit.{tool_name}.v1", "status": "attention", "available": True}
    monkeypatch.setattr(
        server.governance_context,
        tool_name,
        lambda domain_id: seen.append(domain_id) or payload,
        raising=False,
    )

    assert json.loads(getattr(server, tool_name)("work-weijian")) == payload
    assert seen == ["work-weijian"]


def test_cards_check_delegates_without_adding_write_behavior(monkeypatch) -> None:
    server = _server()
    seen: list[str] = []
    payload = {
        "schema": "cockpit.cards-check.v1",
        "status": "ok",
        "available": True,
        "compliant": True,
    }
    monkeypatch.setattr(
        server.governance_context,
        "cards_check",
        lambda card_id="": seen.append(card_id) or payload,
    )

    assert json.loads(server.cards_check("CARD-001")) == payload
    assert seen == ["CARD-001"]
