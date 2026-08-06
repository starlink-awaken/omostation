"""omo_agent_host 测试 — HealthMonitorAgent (α.3 续) + AgentHost 错误隔离.

test_plan:
  - HealthMonitorAgent 全 healthy → noop
  - 有 unhealthy → alert (返回 details, 不落盘, 持久化归上层 omo_daemon)
  - 边界: "healthy (probe)" 不报 (startswith)
  - 边界: scheduled 不报
  - 边界: 空 health_check (未探活) 跳过
  - 边界: 非 dict service 跳过
  - 快照缺失/损坏 → noop (守 F14)
  - AgentHost 错误隔离 (F14): 异常 Agent 不炸 host
"""

from __future__ import annotations

import json
from pathlib import Path

from omo.omo_agent_host import AgentHost, HealthMonitorAgent


def _write_health(tmp_path: Path, services: dict) -> Path:
    """写临时 system_health.yaml (JSON 是 YAML 子集), 返回路径."""
    health_yaml = tmp_path / "system_health.yaml"
    health_yaml.write_text(
        json.dumps({"services": services}, ensure_ascii=False), encoding="utf-8"
    )
    return health_yaml


def test_all_healthy_returns_noop(tmp_path: Path, monkeypatch) -> None:
    """全 healthy → action=noop (含 'healthy (probe)' 不报)."""
    monkeypatch.setattr(
        HealthMonitorAgent,
        "_HEALTH_YAML",
        _write_health(
            tmp_path,
            {
                "svc-a": {"health_check": "healthy", "runtime": {"status": "running"}},
                "svc-b": {
                    "health_check": "healthy (probe)",
                    "runtime": {"status": "running"},
                },
            },
        ),
    )
    r = HealthMonitorAgent().tick()
    assert r["action"] == "noop"
    assert r["details"]["healthy_count"] == 2


def test_unhealthy_returns_alert(tmp_path: Path, monkeypatch) -> None:
    """有 unhealthy → action=alert + details 含异常服务清单 (不落盘)."""
    monkeypatch.setattr(
        HealthMonitorAgent,
        "_HEALTH_YAML",
        _write_health(
            tmp_path,
            {
                "good": {"health_check": "healthy", "runtime": {"status": "running"}},
                "bad": {"health_check": "down", "runtime": {"status": "stopped"}},
            },
        ),
    )
    r = HealthMonitorAgent().tick()
    assert r["action"] == "alert"
    assert r["details"]["unhealthy_count"] == 1
    assert r["details"]["total"] == 2
    svc = r["details"]["services"][0]
    assert svc["name"] == "bad"
    assert svc["health_check"] == "down"
    assert svc["status"] == "stopped"


def test_scheduled_not_flagged(tmp_path: Path, monkeypatch) -> None:
    """scheduled (定时任务未到点) 不报."""
    monkeypatch.setattr(
        HealthMonitorAgent,
        "_HEALTH_YAML",
        _write_health(tmp_path, {"cron": {"health_check": "scheduled"}}),
    )
    assert HealthMonitorAgent().tick()["action"] == "noop"


def test_empty_health_check_skipped(tmp_path: Path, monkeypatch) -> None:
    """空 health_check (未探活, 如 unmanaged 服务) 不报."""
    monkeypatch.setattr(
        HealthMonitorAgent,
        "_HEALTH_YAML",
        _write_health(tmp_path, {"gbrain": {"runtime": {"status": "unmanaged"}}}),
    )
    assert HealthMonitorAgent().tick()["action"] == "noop"


def test_non_dict_service_skipped(tmp_path: Path, monkeypatch) -> None:
    """非 dict service 条目跳过 (容错, 守 F14)."""
    monkeypatch.setattr(
        HealthMonitorAgent,
        "_HEALTH_YAML",
        _write_health(
            tmp_path, {"weird": "not-a-dict", "good": {"health_check": "healthy"}}
        ),
    )
    assert HealthMonitorAgent().tick()["action"] == "noop"


def test_snapshot_missing_returns_noop(tmp_path: Path, monkeypatch) -> None:
    """快照缺失 → noop (note)."""
    monkeypatch.setattr(
        HealthMonitorAgent, "_HEALTH_YAML", tmp_path / "nonexistent.yaml"
    )
    r = HealthMonitorAgent().tick()
    assert r["action"] == "noop"
    assert "note" in r["details"]


def test_snapshot_corrupt_returns_noop(tmp_path: Path, monkeypatch) -> None:
    """快照损坏 (非法 YAML) → noop, 不抛 (守 F14)."""
    corrupt = tmp_path / "system_health.yaml"
    corrupt.write_text("{ not valid yaml @@@ }", encoding="utf-8")
    monkeypatch.setattr(HealthMonitorAgent, "_HEALTH_YAML", corrupt)
    assert HealthMonitorAgent().tick()["action"] == "noop"


def test_agent_host_error_isolation() -> None:
    """AgentHost 错误隔离 (F14): 异常 Agent 不炸 host, 其他 Agent 正常."""

    class _BoomAgent:
        agent_id = "boom"

        def tick(self) -> dict:
            raise RuntimeError("炸了")

    class _OkAgent:
        agent_id = "ok"

        def tick(self) -> dict:
            return {"action": "noop", "details": {}}

    host = AgentHost(agents=[_BoomAgent(), _OkAgent()])
    result = host.tick_all()
    assert result["ok_count"] == 1
    assert result["failed_count"] == 1
    # boom 失败但被隔离, ok 正常
    boom_result = next(r for r in result["results"] if r["agent_id"] == "boom")
    ok_result = next(r for r in result["results"] if r["agent_id"] == "ok")
    assert boom_result["ok"] is False
    assert "炸了" in boom_result["error"]
    assert ok_result["ok"] is True
