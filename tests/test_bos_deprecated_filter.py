"""BOS deprecated filter (ADR-0181 Phase 2 entry cap)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def registry_yaml(tmp_path: Path) -> Path:
    data = {
        "services": [
            {
                "uri": "bos://memory/active/svc",
                "domain": "memory",
                "action": "svc",
                "package": "x",
                "transport": "inline",
                "status": "active",
            },
            {
                "uri": "bos://memory/metaos/mcp-server",
                "domain": "memory",
                "action": "mcp-server",
                "package": "metaos-mcp",
                "transport": "stdio",
                "status": "deprecated",
            },
        ]
    }
    p = tmp_path / "bos.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


def test_deprecated_excluded_by_default(registry_yaml, monkeypatch):
    monkeypatch.delenv("AGORA_BOS_INCLUDE_DEPRECATED", raising=False)
    from agora.mcp.resolver.bos_registry import load_from_yaml

    services = load_from_yaml(registry_yaml)
    uris = {s.uri for s in services}
    assert "bos://memory/active/svc" in uris
    assert "bos://memory/metaos/mcp-server" not in uris


def test_deprecated_included_with_env(registry_yaml, monkeypatch):
    monkeypatch.setenv("AGORA_BOS_INCLUDE_DEPRECATED", "1")
    from agora.mcp.resolver.bos_registry import load_from_yaml

    services = load_from_yaml(registry_yaml)
    uris = {s.uri for s in services}
    assert "bos://memory/metaos/mcp-server" in uris


def test_unimplemented_never_included_even_with_env(monkeypatch, tmp_path):
    """unimplemented 服务即使 AGORA_BOS_INCLUDE_DEPRECATED=1 也始终排除 (P0-1 增强)。"""
    import yaml
    from pathlib import Path

    data = {
        "services": [
            {
                "uri": "bos://memory/unimpl/svc",
                "domain": "memory",
                "action": "svc",
                "package": "x",
                "transport": "inline",
                "status": "unimplemented",
            }
        ]
    }
    p = tmp_path / "unimpl.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    monkeypatch.setenv("AGORA_BOS_INCLUDE_DEPRECATED", "1")
    from agora.mcp.resolver.bos_registry import load_from_yaml

    services = load_from_yaml(p)
    assert services == []
