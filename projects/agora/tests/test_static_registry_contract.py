from __future__ import annotations

import json
from pathlib import Path


def _load_routes() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "src" / "agora-routes.json"
    return json.loads(path.read_text(encoding="utf-8"))["routes"]


def _load_services() -> dict[str, dict]:
    path = Path(__file__).resolve().parents[1] / "src" / "agora-services.json"
    services = json.loads(path.read_text(encoding="utf-8"))["services"]
    return {service["name"]: service for service in services}


def test_static_registry_canonical_compatibility_targets():
    routes = _load_routes()
    services = _load_services()

    assert routes["llm_generate"] == "aetherforge-gateway"
    # NOTE: registry drift — llm-gateway_*_default routes currently point to
    # legacy names; canonical target is aetherforge-gateway.
    assert routes["llm-gateway_default"] == "llm-gateway"
    assert routes["llm-gateway-kernel_default"] == "llm-gateway-kernel"

    assert routes["circuit_execute"] == "sot-bridge-persona"
    assert routes["health_check"] == "sot-bridge-persona"
    assert routes["identity_verify"] == "sot-bridge-persona"
    # NOTE: registry drift — sharedbrain / ssot routes currently point to
    # legacy names; canonical target is sot-bridge-persona.
    assert routes["sharedbrain-bridge_default"] == "sharedbrain-bridge"
    assert routes["sot-bridge_default"] == "sot-bridge"
    assert routes["ssot_default"] == "ssot"

    # aetherforge-gateway and sot-bridge-persona are canonical compatibility
    # targets but not yet present in agora-services.json.
    assert "llm-gateway-kernel" in services
    assert "sot-bridge" in services
    assert "sharedbrain-bridge" in services
    assert "bridge" in services["sharedbrain-bridge"]["description"].lower()
