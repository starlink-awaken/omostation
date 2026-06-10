"""Dashboard server 测试 — 端点路由/认证/CORS + loader 函数单元测试。"""

from pathlib import Path
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import _load_debt, _omo_report, _run_e2e, app


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
        assert ds.DASHBOARD_TOKEN == "test-secret"
        assert ds.DASHBOARD_TOKEN != ""


class TestDashboardLoaders:
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
