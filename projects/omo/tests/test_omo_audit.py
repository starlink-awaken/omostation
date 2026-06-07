from __future__ import annotations

import asyncio

from omo.omo_audit import governance_check_agora_health


def test_governance_check_agora_health_with_active_event_loop(monkeypatch):
    async def _fake_check_all_health(endpoints):
        class _Result:
            def __init__(self, service: str, is_healthy: bool):
                self.service = service
                self.is_healthy = is_healthy

        return [_Result("agora", True), _Result("forge", False)]

    monkeypatch.setattr("omo.omo_health.load_agora_routes", lambda: {"routes": {}})
    monkeypatch.setattr("omo.omo_health.derive_endpoints", lambda routes: {"agora": "http://localhost:7422/health"})
    monkeypatch.setattr("omo.omo_health.check_all_health", _fake_check_all_health)

    async def _invoke():
        return governance_check_agora_health()

    result = asyncio.run(_invoke())
    assert result.category == "agora"
    assert result.message == "1/2 services healthy"
    assert result.severity == "warn"
