"""Dashboard server 测试 — 端点路由/认证/CORS + loader 函数单元测试。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import _load_compute, _load_debt, _omo_report, _run_e2e, app


@pytest.fixture
def test_client():
    """FastAPI TestClient — 替换旧的 http.server 测试方式。"""
    return TestClient(app)


class TestDashboardEndpoints:
    def test_root_endpoint_reachable(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code in (200, 404)

    def test_api_status_endpoint(self, test_client):
        resp = test_client.get("/api/status")
        assert resp.status_code == 200

    def test_favicon_returns_404(self, test_client):
        resp = test_client.get("/favicon.ico")
        assert resp.status_code == 404

    def test_unknown_path_returns_404(self, test_client):
        resp = test_client.get("/nonexistent")
        assert resp.status_code == 404


class TestDashboardAuth:
    def test_auth_bypassed_when_token_empty(self, test_client):
        resp = test_client.get("/api/status")
        assert resp.status_code == 200

    def test_auth_token_loads_correctly(self, monkeypatch):
        """验证 token 环境变量正确加载到模块变量。"""
        monkeypatch.setenv("COCKPIT_DASHBOARD_TOKEN", "test-secret")
        import importlib

        import cockpit.dashboard_server as ds

        importlib.reload(ds)
        assert ds.DASHBOARD_TOKEN == "test-secret"  # noqa: S105
        assert ds.DASHBOARD_TOKEN != ""


class TestDashboardLoaders:
    def test_load_compute_aggregates_runtime_and_provider_plane(self, monkeypatch, tmp_path):
        runtime_home = tmp_path / "runtime"
        quota_path = runtime_home / "data" / "llm_quota_summary.json"
        cost_path = runtime_home / "data" / "llm_cost.jsonl"
        provider_plane_path = tmp_path / ".omo" / "state" / "provider-plane.yaml"
        quota_path.parent.mkdir(parents=True)
        provider_plane_path.parent.mkdir(parents=True)

        quota_path.write_text(
            """{
  "generated_at": "2026-06-15T09:00:00Z",
  "entry_count": 2,
  "total_estimated_cost_usd": 0.12,
  "remaining_ratio": 0.42,
  "quota_low": false
}""",
            encoding="utf-8",
        )
        cost_path.write_text(
            "\n".join(
                [
                    '{"model":"gpt-4o","input_tokens":1000,"output_tokens":500,"timestamp":"2026-06-15T08:00:00Z"}',
                    '{"model":"ollama/qwen3","input_tokens":100,"output_tokens":50,"timestamp":"2026-06-14T08:00:00Z"}',
                ]
            ),
            encoding="utf-8",
        )
        provider_plane_path.write_text(
            """
selected_provider:
  name: DeepSeek
  model: gpt-4o
  base_url: https://example.test
  source: cc-switch
  is_healthy: true
quota_summary:
  provider_count: 1
  providers:
    codex:
      available: true
      summary: balance=$8.50
      balance: 8.5
      used_percent: 20.0
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.setattr("cockpit.dashboard_server.LLM_QUOTA_SUMMARY_PATH", quota_path)
        monkeypatch.setattr("cockpit.dashboard_server.LLM_COST_LOG_PATH", cost_path)
        monkeypatch.setattr("cockpit.dashboard_server.PROVIDER_PLANE_PATH", provider_plane_path)

        result = _load_compute()

        assert result["summary"]["total_calls"] == 2
        assert result["summary"]["remaining_ratio"] == 0.42
        assert result["provider"]["name"] == "DeepSeek"
        assert result["provider"]["quota_provider_count"] == 1
        assert result["observations"]["cross_day"] is True
        assert result["observations"]["cross_model"] is True
        assert result["traffic_by_node"][0]["calls"] == 1
        assert len(result["recent_traffic"]) == 2
        assert any(item["label"] == "Cloud (cc-switch)" for item in result["topology"])

    def test_load_debt_no_omo_dir(self, monkeypatch):
        monkeypatch.setattr(
            "cockpit.dashboard_server.OMO_ROOT",
            Path("/nonexistent/path"),
        )
        result = _load_debt()
        assert "error" in result

    def test_run_e2e_timeout(self, monkeypatch):
        import subprocess

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="mock", timeout=1)

        monkeypatch.setattr("subprocess.run", mock_run)
        result = _run_e2e()
        assert result["result"] == "timeout"

    def test_run_e2e_error(self, monkeypatch):
        def mock_run(*args, **kwargs):
            raise RuntimeError("test error")

        monkeypatch.setattr("subprocess.run", mock_run)
        result = _run_e2e()
        assert result["result"] == "error"

    def test_omo_report_empty_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cockpit.dashboard_server.OMO_ROOT", tmp_path)
        (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True)
        result = _omo_report()
        assert result["total"] == 0
        assert result["open"] == 0


class TestDashboardCORS:
    def test_cors_origin_env_loaded(self, monkeypatch):
        """验证 CORS 环境变量正确加载。"""
        monkeypatch.setenv("COCKPIT_DASHBOARD_CORS_ORIGIN", "http://myapp.local")
        import importlib

        import cockpit.dashboard_server as ds

        importlib.reload(ds)
        assert ds.DASHBOARD_CORS_ORIGIN == "http://myapp.local"


class TestDashboardComputeApi:
    def test_api_compute_endpoint(self, test_client, monkeypatch):
        monkeypatch.setattr(
            "cockpit.dashboard_server._load_compute",
            lambda: {"summary": {"total_calls": 3}, "recent_traffic": [], "traffic_by_node": []},
        )
        resp = test_client.get("/api/compute")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_calls"] == 3
