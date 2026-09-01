"""Web reflection endpoints — 6 个只读反射端点冒烟测试.

覆盖:
  · GET /api/commands    — 命令目录
  · GET /api/chains      — chain 列表
  · GET /api/chains/{id} — chain 详情
  · GET /api/command-audit/summary — 评分卡汇总
  · GET /api/resident    — 常驻 Agent（可能不可达）
  · GET /api/bcos        — BCOS（可能不可达）
  · GET /api/p74         — P74（可能不可达）
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestCommandsEndpoint:
    def test_commands_returns_200(self, client: TestClient):
        resp = client.get("/api/commands")
        assert resp.status_code == 200

    def test_commands_has_list(self, client: TestClient):
        data = client.get("/api/commands").json()
        assert data["available"] is True
        assert isinstance(data["commands"], list)
        assert data["total"] > 0

    def test_commands_have_required_fields(self, client: TestClient):
        data = client.get("/api/commands").json()
        for cmd in data["commands"]:
            assert "name" in cmd
            assert "summary" in cmd
            assert "category" in cmd


class TestChainsEndpoint:
    def test_chains_returns_200(self, client: TestClient):
        resp = client.get("/api/chains")
        assert resp.status_code == 200

    def test_chains_has_list(self, client: TestClient):
        data = client.get("/api/chains").json()
        assert data["available"] is True
        assert isinstance(data["chains"], list)

    def test_chain_detail_404(self, client: TestClient):
        resp = client.get("/api/chains/nonexistent-chain-xyz")
        # Returns 200 with available=False (chain spec not found)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("available") is False


class TestCommandAuditEndpoint:
    def test_audit_summary_returns_200(self, client: TestClient):
        resp = client.get("/api/command-audit/summary")
        assert resp.status_code == 200

    def test_audit_summary_has_dimensions(self, client: TestClient):
        data = client.get("/api/command-audit/summary").json()
        assert data["available"] is True
        assert "dimension_averages" in data
        assert "total_cards" in data


class TestReflectionEndpoints:
    """resident / bcos / p74 — 可能不可达, 但端点应返回 200 + available 标志."""

    def test_resident_returns_200(self, client: TestClient):
        resp = client.get("/api/resident")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data

    def test_bcos_returns_200(self, client: TestClient):
        resp = client.get("/api/bcos")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data

    def test_p74_returns_200(self, client: TestClient):
        resp = client.get("/api/p74")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
