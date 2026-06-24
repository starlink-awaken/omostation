from __future__ import annotations

import asyncio
from pathlib import Path

from omo.omo_audit import _load_yaml_safely, governance_check_agora_health


def test_governance_check_agora_health_with_active_event_loop(monkeypatch):
    async def _fake_check_all_health(endpoints):
        class _Result:
            def __init__(self, service: str, is_healthy: bool):
                self.service = service
                self.is_healthy = is_healthy

        return [_Result("agora", True), _Result("forge", False)]

    monkeypatch.setattr("omo.omo_health.load_agora_routes", lambda: {"routes": {}})
    monkeypatch.setattr(
        "omo.omo_health.derive_endpoints",
        lambda routes: {"agora": "http://localhost:7422/health"},
    )
    monkeypatch.setattr("omo.omo_health.check_all_health", _fake_check_all_health)

    async def _invoke():
        return governance_check_agora_health()

    result = asyncio.run(_invoke())
    assert result.category == "agora"
    assert result.message == "1/2 services healthy"
    assert result.severity == "warn"


def test_load_yaml_safely_accepts_multi_document_yaml(tmp_path: Path) -> None:
    payload = tmp_path / "audit.yaml"
    payload.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "current_phase: 42\n"
        "health_score: 100\n",
        encoding="utf-8",
    )

    data = _load_yaml_safely(payload)

    assert data == {
        "status": "active",
        "owner": "governance",
        "current_phase": 42,
        "health_score": 100,
    }
