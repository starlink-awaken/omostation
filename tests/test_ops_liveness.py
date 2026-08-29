"""Regression tests for bounded Service Gateway liveness aggregation."""

from __future__ import annotations

import time

import pytest

from bin.ops import cli


def test_collect_liveness_preserves_service_order_and_results(monkeypatch: pytest.MonkeyPatch) -> None:
    services = [{"id": f"svc-{index}"} for index in range(8)]

    def fake_check(service: dict, *, timeout: float | None = None) -> dict[str, str]:
        del timeout
        time.sleep(0.001 * (8 - int(service["id"].split("-")[-1])))
        return {"status": "healthy"}

    monkeypatch.setattr(cli, "check_liveness", fake_check)

    result = cli.collect_liveness(services, total_timeout=1.0, probe_timeout=0.1, max_workers=4)

    assert list(result) == [service["id"] for service in services]
    assert all(item["status"] == "healthy" for item in result.values())


def test_collect_liveness_marks_unfinished_probes_as_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    services = [{"id": f"svc-{index}"} for index in range(4)]

    def slow_check(service: dict, *, timeout: float | None = None) -> dict[str, str]:
        del service, timeout
        time.sleep(0.2)
        return {"status": "healthy"}

    monkeypatch.setattr(cli, "check_liveness", slow_check)

    result = cli.collect_liveness(services, total_timeout=0.005, probe_timeout=0.005, max_workers=2)

    assert list(result) == [service["id"] for service in services]
    assert all(item["status"] == "timeout" for item in result.values())
    assert all(item["error"] == "liveness_budget_exhausted" for item in result.values())
