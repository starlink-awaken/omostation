from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import tomllib
from pathlib import Path

EXPECTED_TOOLS = {
    "workspace_context",
    "domain_context",
    "cards_status",
    "cards_check",
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
