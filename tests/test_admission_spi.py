"""AdmissionPort SPI tests (ADR-0181)."""

from __future__ import annotations

import os

import pytest

from agora.admission import (
    evaluate_admission,
    get_admission_provider,
    reset_admission_provider_cache,
)


@pytest.fixture(autouse=True)
def _reset_provider():
    reset_admission_provider_cache()
    old_mode = os.environ.pop("AGORA_ADMISSION_MODE", None)
    old_prov = os.environ.pop("AGORA_ADMISSION_PROVIDER", None)
    yield
    reset_admission_provider_cache()
    if old_mode is not None:
        os.environ["AGORA_ADMISSION_MODE"] = old_mode
    else:
        os.environ.pop("AGORA_ADMISSION_MODE", None)
    if old_prov is not None:
        os.environ["AGORA_ADMISSION_PROVIDER"] = old_prov
    else:
        os.environ.pop("AGORA_ADMISSION_PROVIDER", None)


def test_evaluate_degraded_when_provider_forced_missing(monkeypatch):
    """When provider cannot load, degraded mode admits with explicit flag."""
    monkeypatch.setenv("AGORA_ADMISSION_MODE", "degraded")
    monkeypatch.setenv("AGORA_ADMISSION_PROVIDER", "nonexistent.module:Nope")
    # Block soft providers by forcing env-only failure then empty soft path
    import agora.admission.port as port

    monkeypatch.setattr(port, "_SOFT_PROVIDERS", ())
    # Clear entry points by patching metadata
    monkeypatch.setattr(
        port.metadata,
        "entry_points",
        lambda: type("EP", (), {"select": lambda **k: [], "get": lambda *a, **k: []})(),
    )
    reset_admission_provider_cache()

    result = evaluate_admission({"domain": "test", "role": "generator"})
    assert result["status"] == "admitted"
    assert result.get("degraded") is True
    assert any("unavailable" in r.lower() or "SPI" in r for r in result["reasons"])


def test_evaluate_strict_rejects_when_provider_missing(monkeypatch):
    monkeypatch.setenv("AGORA_ADMISSION_MODE", "strict")
    monkeypatch.setenv("AGORA_ADMISSION_PROVIDER", "nonexistent.module:Nope")
    import agora.admission.port as port

    monkeypatch.setattr(port, "_SOFT_PROVIDERS", ())
    monkeypatch.setattr(
        port.metadata,
        "entry_points",
        lambda: type("EP", (), {"select": lambda **k: [], "get": lambda *a, **k: []})(),
    )
    reset_admission_provider_cache()

    result = evaluate_admission({"domain": "test"})
    assert result["status"] == "rejected"


def test_evaluate_default_mode_required_fail_closed(monkeypatch):
    """默认 AGORA_ADMISSION_MODE=required (fail-closed): provider 缺失即拒绝。"""
    monkeypatch.delenv("AGORA_ADMISSION_MODE", raising=False)
    monkeypatch.setenv("AGORA_ADMISSION_PROVIDER", "nonexistent.module:Nope")
    import agora.admission.port as port

    monkeypatch.setattr(port, "_SOFT_PROVIDERS", ())
    monkeypatch.setattr(
        port.metadata,
        "entry_points",
        lambda: type("EP", (), {"select": lambda **k: [], "get": lambda *a, **k: []})(),
    )
    reset_admission_provider_cache()

    result = evaluate_admission({"domain": "test"})
    assert result["status"] == "rejected"
    assert any("fail-closed" in r for r in result["reasons"])


def test_evaluate_with_stub_provider(monkeypatch):
    class Stub:
        def evaluate(self, request):
            return {"status": "admitted", "reasons": ["stub-ok"]}

    import agora.admission.port as port

    reset_admission_provider_cache()
    monkeypatch.setattr(port, "_provider_cache", Stub())

    result = evaluate_admission({"domain": "x"})
    assert result["status"] == "admitted"
    assert "stub-ok" in result["reasons"]
    assert result.get("provider") == "Stub"


def test_manager_does_not_import_metaos_gateway_directly():
    """Regression: ProxyManager must not hard-import AdmissionGateway."""
    import inspect

    from agora.mcp_proxy import manager as mgr

    src = inspect.getsource(mgr)
    assert "from metaos.layers.admission_gateway import AdmissionGateway" not in src
    assert "agora.admission" in src or "evaluate_admission" in src
