"""Tests for registering Eidos as an Agora service."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agora.core.registry import KNOWN_PROTOCOLS, Service, ServiceRegistry


def _new_registry() -> ServiceRegistry:
    return ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))


def test_eidos_protocol_registration() -> None:
    """Verify Eidos protocol definition is valid."""
    protocol = {
        "name": "eidos",
        "type": "service",
        "version": "0.1.0",
        "description": "Eidos schema definition and validation service",
        "capabilities": ["validate", "list_schemas"],
        "transport": "stdio",
    }

    assert protocol["name"] == "eidos"
    assert protocol["type"] == "service"
    assert protocol["transport"] in KNOWN_PROTOCOLS
    assert "validate" in protocol["capabilities"]
    assert "list_schemas" in protocol["capabilities"]


def test_eidos_service_can_be_registered() -> None:
    """Eidos can be stored in the Agora service registry as an MCP endpoint."""
    registry = _new_registry()
    service = Service(
        name="eidos",
        description="Eidos schema definition and validation service",
        protocol="mcp",
        mcp_endpoint="http://192.0.2.1:8765/mcp",
        protocol_config={
            "capabilities": ["validate", "list_schemas"],
            "transport": "stdio",
        },
    )

    registry.register(service)

    registered = registry.get("eidos")
    assert registered is not None
    assert registered.name == "eidos"
    assert registered.protocol == "mcp"
    assert registered.mcp_endpoint == "http://192.0.2.1:8765/mcp"
    assert "validate" in registered.protocol_config["capabilities"]
    assert "list_schemas" in registered.protocol_config["capabilities"]


def test_eidos_service_list_output_matches_registry_format() -> None:
    """Eidos appears in the registry output with Agora service fields."""
    registry = _new_registry()
    registry.register(
        Service(
            name="eidos",
            description="Eidos schema definition and validation service",
            protocol="mcp",
            mcp_endpoint="http://192.0.2.1:8765/mcp",
        )
    )

    output = registry.to_dict()
    assert len(output) == 1
    assert output[0]["name"] == "eidos"
    assert output[0]["protocol"] == "mcp"
    assert output[0]["healthy"] is True
    assert output[0]["endpoint"] == "http://192.0.2.1:8765/mcp"
