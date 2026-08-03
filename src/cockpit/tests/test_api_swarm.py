"""Swarm Observatory API 测试.

验证 /api/swarm/status 和 /api/swarm/claims 路由可达 + 返回结构 + 降级处理.
数据源用 monkeypatch 隔离 (不依赖 cockpit venv 的 pyyaml / agent-workflow 真跑).
"""

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_swarm


def _fake_status_json() -> dict:
    return {
        "ok": True,
        "active_runs": ["run-fake-1"],
        "closed_runs": ["run-closed-1", "run-closed-2"],
        "run_count": 3,
        "lock_count": 2,
        "stale_locks": 0,
        "current_run_id": "run-fake-1",
        "compliance": {"ok": True, "decision": "continue", "slo": {"stale_locks": 0}},
        "claim_coverage": {"ok": True, "mode": "advisory"},
        "recommended_next": "claim missing files",
    }


def _fake_window_json() -> dict:
    return {
        "m1_conflict_zero_verdict": "window_open",
        "elapsed_hours": 1.5,
        "conflict_count": 0,
        "window_start": "2026-08-03T00:00:00Z",
    }


def test_swarm_status_returns_expected_shape(monkeypatch):
    """GET /api/swarm/status 返回 200 + workflow/window/claims/compliance 完整结构."""

    def fake_run_cli_json(script, args=None, timeout=30):
        if args and "status" in args:
            return _fake_status_json()
        return _fake_window_json()

    monkeypatch.setattr(api_swarm, "_run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(
        api_swarm,
        "_load_branch_claims",
        lambda: [{"session": "d2-swarm-dashboard", "branch": "work/d2-swarm-dashboard"}],
    )

    response = TestClient(app).get("/api/swarm/status")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow"]["active_count"] == 1
    assert body["workflow"]["run_count"] == 3
    assert body["workflow"]["lock_count"] == 2
    assert body["workflow"]["stale_locks"] == 0
    assert body["window"]["verdict"] == "window_open"
    assert body["window"]["conflict_count"] == 0
    assert body["claims"]["active_count"] == 1
    assert body["compliance"]["decision"] == "continue"
    assert body["compliance"]["ok"] is True
    assert body["claim_coverage"]["ok"] is True
    assert body["data_quality"] == "complete"
    assert body["degraded_reasons"] == []


def test_swarm_status_degrades_when_sources_unavailable(monkeypatch):
    """数据源全失败时, 降级标记 + data_quality=unavailable, 不崩 (显式降级哲学)."""
    monkeypatch.setattr(api_swarm, "_run_cli_json", lambda script, args=None, timeout=30: None)
    monkeypatch.setattr(api_swarm, "_load_branch_claims", lambda: [])

    response = TestClient(app).get("/api/swarm/status")

    assert response.status_code == 200
    body = response.json()
    assert body["data_quality"] == "unavailable"
    assert len(body["degraded_reasons"]) == 2
    assert body["workflow"]["active_count"] == 0
    assert body["window"]["verdict"] is None
    assert body["compliance"]["decision"] is None


def test_swarm_claims_returns_claim_details(monkeypatch):
    """GET /api/swarm/claims 返回活跃 claim 明细列表."""
    fake_claims = [
        {"session": "d2-swarm-dashboard", "branch": "work/d2-swarm-dashboard"},
        {"session": "p2-discover", "branch": "work/p2-discover"},
    ]
    monkeypatch.setattr(api_swarm, "_load_branch_claims", lambda: fake_claims)

    response = TestClient(app).get("/api/swarm/claims")

    assert response.status_code == 200
    body = response.json()
    assert body["active_count"] == 2
    assert len(body["claims"]) == 2
    assert body["claims"][0]["session"] == "d2-swarm-dashboard"
