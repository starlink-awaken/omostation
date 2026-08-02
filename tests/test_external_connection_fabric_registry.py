from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".omo/_truth/registry/external-connection-fabric.yaml"
STANDARD = ROOT / ".omo/standards/external-connection-fabric.md"


def _body() -> dict:
    documents = list(yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")))
    assert len(documents) == 2
    assert documents[0]["status"] == "active"
    return documents[1]


def test_registry_covers_the_external_resource_surface() -> None:
    assert set(_body()["resource_kinds"]) == {
        "knowledge_source",
        "data_source",
        "resource_provider",
        "method_pack",
        "tool_capability",
        "channel",
        "model_provider",
    }


def test_descriptor_has_secret_boundary() -> None:
    descriptor = _body()["descriptor"]
    assert descriptor["schema_version"] == "external-resource/v1"
    assert descriptor["secret_policy"] == "credential_ref_only"
    assert "permission_ref" in descriptor["required_fields"]
    assert {"access_token", "password", "private_key"} <= set(descriptor["forbidden_fields"])


def test_lifecycle_transitions_are_closed() -> None:
    lifecycle = _body()["lifecycle"]
    states = set(lifecycle["states"])
    assert all(set(targets) <= states for targets in lifecycle["transitions"].values())
    assert lifecycle["transitions"]["retired"] == []


def test_architecture_pointers_are_present() -> None:
    body = _body()
    assert body["validation"]["contract_test"] == "tests/test_external_connection_fabric_registry.py"
    assert body["validation"]["runtime_test"] == "tests/test_external_connection_runtime.py"
    assert body["dynamic_discovery"]["entry_point_group"] == "external.resources"
    assert body["bindings"]["capability_router"].endswith("agora/external_connections.py")
    assert STANDARD.exists()
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    strategy = (ROOT / "docs/STRATEGY-3YEAR-PANORAMA.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/WORKFLOW-MESH-IMPLEMENTATION.md").read_text(encoding="utf-8")
    assert "external-connection-fabric.yaml" in architecture
    assert "External Connection Fabric" in strategy
    assert "P2.5" in workflow
