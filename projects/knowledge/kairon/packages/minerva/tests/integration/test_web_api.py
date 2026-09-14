"""Integration tests for Minerva Web API endpoints.

Tests core security properties without requiring the full research pipeline.
"""

import pytest


def _has_network():
    """Check if the internet is reachable."""
    import urllib.request

    try:
        urllib.request.urlopen("https://httpbin.org/ip", timeout=3)
        return True
    except Exception:
        return False


def _server_is_running():
    """Check if the local minerva server is responding."""
    import urllib.request

    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=2)
        return resp.status == 200
    except Exception:
        return False


from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Create test client with mocked executor and API key configured."""
    monkeypatch.setenv("MINERVA_API_KEY", "test-key")
    # Ensure fresh module state so middleware picks up the env var
    import importlib

    import minerva.web.app

    importlib.reload(minerva.web.app)
    from minerva.web.app import _executor_ref, app

    class MockExec:
        async def execute_now(self, task):
            class Ctx:
                stage_timings = {"search": 1.0, "output": 0.5}

            class R:
                summary = "Test research result"
                report_path = "~/knowledge/reports/test.md"
                cost = 0.0
                context = Ctx()

            return R

        async def get_status(self, tid):
            return {"status": "completed"}

    _executor_ref["executor"] = MockExec()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    _executor_ref.clear()


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_has_security_headers(self, client):
        resp = client.get("/health")
        assert "X-Content-Type-Options" in resp.headers
        assert "X-Frame-Options" in resp.headers


class TestPathTraversalBlocked:
    def test_report_rejects_traversal(self, client):
        resp = client.get("/api/report?path=../../etc/passwd")
        assert resp.status_code == 404

    def test_report_rejects_root_path(self, client):
        resp = client.get("/api/report?path=/etc/shadow")
        assert resp.status_code == 404

    def test_report_pdf_rejects_traversal(self, client):
        resp = client.get("/api/report/pdf?path=../../etc/shadow")
        assert resp.status_code == 404

    def test_error_no_path_leak(self, client):
        """Error must not leak filesystem paths."""
        resp = client.get("/api/report?path=../../etc/passwd")
        data = resp.json()
        assert "error" in data
        assert "../../etc" not in data.get("error", "")


class TestInputValidation:
    def test_paradigm_empty_query_rejected(self, client):
        resp = client.get("/api/paradigm?query=")
        assert resp.status_code == 400

    def test_oversized_query_rejected(self, client):
        resp = client.get(f"/api/paradigm?query={'x' * 3000}")
        assert resp.status_code == 414

    def test_normal_query_accepted(self, client):
        resp = client.get("/api/paradigm?query=short")
        assert resp.status_code != 414


class TestPublicEndpoints:
    def test_dashboard_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_progress_returns_data(self, client):
        resp = client.get("/api/progress")
        assert resp.status_code == 200
        assert "status" in resp.json()

    def test_404_nonexistent(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404


class TestResearchEndpoint:
    @pytest.mark.skipif(
        not _has_network() or not _server_is_running(),
        reason="requires network + running server",
    )
    def test_research_returns_structure(self, client):
        resp = client.post("/api/research", data={"query": "test", "level": "L0"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "task_id" in data
        assert "summary" in data
        assert "stages" in data
