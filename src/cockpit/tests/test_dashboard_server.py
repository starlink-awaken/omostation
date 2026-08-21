"""Dashboard server 测试 — 端点路由/认证/CORS + loader 函数单元测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard.helpers import load_compute as _load_compute
from cockpit.dashboard.helpers import load_debt as _load_debt
from cockpit.dashboard.helpers import omo_report as _omo_report
from cockpit.dashboard.helpers import run_e2e as _run_e2e
from cockpit.dashboard_server import app


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

    def test_version_catalog_reflects_mounted_api_routes(self, test_client):
        info = test_client.get("/api/version")
        history = test_client.get("/api/version/history")

        assert info.status_code == 200
        assert history.status_code == 200
        payload = info.json()
        entries = history.json()
        assert payload["current_version"] == "v1"
        assert payload["endpoints"] > 10
        assert "v1" in payload["supported_versions"]
        assert any(item["version"] == "v1" and item["endpoints"] > 10 for item in entries)
        endpoint_paths = {endpoint.get("path") for item in entries for endpoint in item.get("endpoint_list", [])}
        assert "/api/tasks" in endpoint_paths
        assert "/api/cockpit/system-map" in endpoint_paths
        task_operations = {
            (endpoint.get("method"), endpoint.get("path"))
            for item in entries
            for endpoint in item.get("endpoint_list", [])
        }
        assert {("GET", "/api/tasks"), ("POST", "/api/tasks")} <= task_operations

    def test_api_response_exposes_current_version(self, test_client):
        resp = test_client.get("/api/status")
        assert resp.headers["X-API-Version"] == "v1"

    def test_router_health_exposes_graceful_degradation_report(self, test_client):
        resp = test_client.get("/api/cockpit/router-health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary"]["total"] >= 10
        assert payload["summary"]["loaded"] >= 1
        assert payload["summary"]["loaded"] + payload["summary"]["unavailable"] == payload["summary"]["total"]
        assert any(
            item["module"] == "cockpit.web.api_tasks" and item["status"] == "loaded" for item in payload["items"]
        )
        agora = next(item for item in payload["items"] if item["module"] == "cockpit.web.api_agora")
        assert agora["status"] == "loaded"
        assert agora["route_count"] > 0

    def test_openapi_operation_ids_are_unique(self, test_client):
        paths = test_client.get("/openapi.json").json().get("paths", {})
        operation_ids = [
            operation["operationId"]
            for operations in paths.values()
            for operation in operations.values()
            if isinstance(operation, dict) and operation.get("operationId")
        ]

        assert len(operation_ids) == len(set(operation_ids))

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

        import cockpit.dashboard.constants as c

        importlib.reload(c)
        assert c.DASHBOARD_TOKEN == "test-secret"  # noqa: S105 (测试用假 token)
        assert c.DASHBOARD_TOKEN != ""


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
                    '{"model":"gpt-4o","provider":"openai","input_tokens":1000,"output_tokens":500,"timestamp":"2026-06-15T08:00:00Z","node_id":"cloud-cc-switch","node_label":"Cloud (cc-switch)","route_type":"cloud","latency_ms":1800.5,"tokens_per_second":833.1}',
                    '{"model":"ollama/qwen3","provider":"ollama","input_tokens":100,"output_tokens":50,"timestamp":"2026-06-14T08:00:00Z","node_id":"macmini-ollama","node_label":"MacMini (Ollama)","route_type":"local","latency_ms":250.0,"tokens_per_second":600.0}',
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
      remaining: 25
      balance: 8.5
      used_percent: 20.0
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.setattr("cockpit.dashboard.constants.LLM_QUOTA_SUMMARY_PATH", quota_path)
        monkeypatch.setattr("cockpit.dashboard.constants.LLM_COST_LOG_PATH", cost_path)
        monkeypatch.setattr("cockpit.dashboard.constants.PROVIDER_PLANE_PATH", provider_plane_path)

        result = _load_compute()

        assert result["summary"]["total_calls"] == 2
        assert result["summary"]["remaining_ratio"] == 0.42
        assert result["summary"]["avg_latency_ms"] == 1025.25
        assert result["summary"]["avg_tokens_per_second"] == 716.55
        assert result["cost_board"]["selected_cloud_model"] == "gpt-4o"
        assert result["cost_board"]["intercepted_calls"] == 1
        assert result["cost_board"]["interception_rate"] == 0.5
        assert result["cost_board"]["actual_cloud_cost_usd"] == 0.025
        assert result["cost_board"]["saved_vs_cloud_usd"] == 0.0025
        assert result["cost_board"]["codex_remaining_credits"] == 25
        assert result["cost_board"]["codex_secondary_used_percent"] == 20.0
        assert result["cost_board"]["codex_available"] is True
        assert result["provider"]["name"] == "DeepSeek"
        assert result["provider"]["quota_provider_count"] == 1
        assert result["observations"]["cross_day"] is True
        assert result["observations"]["cross_model"] is True
        assert result["observations"]["latency_available"] is True
        assert result["observations"]["throughput_mode"] == "trace"
        assert result["traffic_by_node"][0]["calls"] == 1
        assert result["traffic_by_node"][0]["latency_ms_avg"] in (1800.5, 250.0)
        assert len(result["recent_traffic"]) == 2
        assert result["recent_traffic"][0]["node_label"] == "Cloud (cc-switch)"
        assert any(item["label"] == "Cloud (cc-switch)" for item in result["topology"])

    def test_load_debt_no_omo_dir(self, monkeypatch):
        monkeypatch.setattr(
            "cockpit.dashboard.helpers.OMO_ROOT",
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

    def test_run_e2e_returns_parseable_status_and_diagnostics(self, monkeypatch):
        monkeypatch.setattr(
            "subprocess.run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout="Result: 9/9 checks passed\n",
                stderr="",
            ),
        )

        result = _run_e2e()

        assert result["status"] == "ok"
        assert result["result"] == "9/9 passed"
        assert result["exit_code"] == 0

    def test_omo_report_empty_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cockpit.dashboard.helpers.OMO_ROOT", tmp_path)
        (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True)
        result = _omo_report()
        assert result["total"] == 0
        assert result["open"] == 0


class TestDashboardCORS:
    def test_cors_origin_env_loaded(self, monkeypatch):
        """验证 CORS 环境变量正确加载。"""
        monkeypatch.setenv("COCKPIT_DASHBOARD_CORS_ORIGIN", "http://myapp.local")
        import importlib

        import cockpit.dashboard.constants as c

        importlib.reload(c)
        assert c.DASHBOARD_CORS_ORIGIN == "http://myapp.local"


class TestDashboardComputeApi:
    def test_api_compute_endpoint(self, test_client, monkeypatch):
        monkeypatch.setattr(
            "cockpit.dashboard.routes.load_compute",
            lambda: {
                "summary": {"total_calls": 3},
                "recent_traffic": [],
                "traffic_by_node": [],
                "cost_board": {"saved_vs_cloud_usd": 1.23},
            },
        )
        resp = test_client.get("/api/compute")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_calls"] == 3
        assert resp.json()["cost_board"]["saved_vs_cloud_usd"] == 1.23


class TestUnifiedAuth:
    """统一认证中间件测试 (OPT-UNIFIED-AUTH)."""

    def test_auth_disabled_allows_anonymous(self, test_client, monkeypatch):
        """AUTH_REQUIRED=false (默认) → 匿名访问 /api/* 返回 200."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", False)
        auth_mod.reload_api_keys()
        resp = test_client.get("/api/status")
        assert resp.status_code == 200

    def test_auth_enabled_rejects_no_key(self, test_client, monkeypatch):
        """AUTH_REQUIRED=true + 无 key → 401."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", True)
        auth_mod.reload_api_keys()
        resp = test_client.get("/api/status")
        assert resp.status_code == 401

    def test_auth_enabled_accepts_valid_key(self, test_client, monkeypatch):
        """AUTH_REQUIRED=true + 有效 X-Api-Key → 200."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", True)
        monkeypatch.setenv("COCKPIT_API_KEY", "test-master-key")
        auth_mod.reload_api_keys()
        resp = test_client.get("/api/status", headers={"X-Api-Key": "test-master-key"})
        assert resp.status_code == 200

    def test_auth_enabled_accepts_bearer_token(self, test_client, monkeypatch):
        """AUTH_REQUIRED=true + 有效 Authorization: Bearer → 200."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", True)
        monkeypatch.setenv("COCKPIT_API_KEY", "bearer-test-key")
        auth_mod.reload_api_keys()
        resp = test_client.get("/api/status", headers={"Authorization": "Bearer bearer-test-key"})
        assert resp.status_code == 200

    def test_auth_enabled_rejects_invalid_key(self, test_client, monkeypatch):
        """AUTH_REQUIRED=true + 无效 key → 401."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", True)
        monkeypatch.setenv("COCKPIT_API_KEY", "correct-key")
        auth_mod.reload_api_keys()
        resp = test_client.get("/api/status", headers={"X-Api-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_example_key_file_is_safe_and_matches_default_location(self, test_client, monkeypatch, tmp_path):
        import cockpit.web.auth as auth_mod

        project_root = Path(__file__).resolve().parents[3]
        example_file = project_root / "config" / "api_keys.yaml.example"
        assert auth_mod._DEFAULT_KEYS_FILE == project_root / "config" / "api_keys.yaml"
        assert auth_mod._resolve_keys_file(None) == auth_mod._DEFAULT_KEYS_FILE
        assert auth_mod._resolve_keys_file("  ") == auth_mod._DEFAULT_KEYS_FILE
        assert auth_mod._resolve_keys_file(str(example_file)) == example_file
        assert auth_mod._resolve_keys_file("~/cockpit-keys.yaml") == Path.home() / "cockpit-keys.yaml"

        with monkeypatch.context() as patch:
            patch.delenv("COCKPIT_API_KEY", raising=False)
            patch.chdir(tmp_path)
            patch.setenv("COCKPIT_KEYS_FILE", "config/api_keys.yaml.example")
            assert auth_mod._resolve_keys_file("config/api_keys.yaml.example") == example_file
            assert auth_mod.reload_api_keys() == {}
            response = test_client.post(
                "/api/workflow-mesh/engineering-delivery/review",
                headers={"X-Api-Key": "your-engineering-review-key-here"},
                json={},
            )
            assert response.status_code == 401
            assert response.json()["error"] == "engineering_delivery_auth_required"
        auth_mod.reload_api_keys()

    def test_effectful_auth_binds_opaque_principal_even_when_global_auth_is_optional(self, monkeypatch):
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", False)
        monkeypatch.setattr(
            auth_mod,
            "_cached_keys",
            lambda: {"review-secret": auth_mod.ApiKeyInfo(name="reviewer", scopes=["engineering-review"])},
        )

        principal = auth_mod.authenticate_api_principal(
            {"X-Api-Key": "review-secret"},
            any_scope=frozenset({"engineering-review"}),
        )

        assert principal.principal_ref.startswith("operator://cockpit-api/")
        assert "review-secret" not in principal.principal_ref
        assert principal.scopes == ("engineering-review",)

    def test_effectful_auth_rejects_anonymous_and_insufficient_scope(self, monkeypatch):
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_cached_keys",
            lambda: {"read-secret": auth_mod.ApiKeyInfo(name="reader", scopes=["read"])},
        )
        with pytest.raises(auth_mod.ApiAuthenticationError, match="missing_api_key"):
            auth_mod.authenticate_api_principal({}, any_scope=frozenset({"engineering-review"}))
        with pytest.raises(auth_mod.ApiAuthorizationError, match="insufficient_scope"):
            auth_mod.authenticate_api_principal(
                {"Authorization": "Bearer read-secret"},
                any_scope=frozenset({"engineering-review"}),
            )

    def test_human_review_auth_rejects_generic_admin_without_explicit_scope(self, monkeypatch):
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_cached_keys",
            lambda: {"admin-secret": auth_mod.ApiKeyInfo(name="admin", scopes=["admin"])},
        )

        with pytest.raises(auth_mod.ApiAuthorizationError, match="insufficient_scope"):
            auth_mod.authenticate_api_principal(
                {"X-Api-Key": "admin-secret"},
                any_scope=frozenset({"engineering-review"}),
                allow_admin=False,
            )
        with pytest.raises(auth_mod.ApiAuthorizationError, match="engineering_review_scope_required"):
            auth_mod.issue_engineering_review_assertion(
                auth_mod.AuthenticatedPrincipal(
                    principal_ref="operator://cockpit-api/admin",
                    name="admin",
                    scopes=("admin",),
                ),
                {"workflow_run_id": "run-1", "candidate_receipt_id": "delivery-1", "review": {}},
            )

    def test_engineering_review_assertion_is_signed_and_payload_bound(self, monkeypatch):
        import cockpit.web.auth as auth_mod

        monkeypatch.setenv(
            "COCKPIT_ENGINEERING_REVIEW_SIGNING_KEY",
            "test-engineering-review-signing-key-0001",
        )
        principal = auth_mod.AuthenticatedPrincipal(
            principal_ref="operator://cockpit-api/reviewer-1",
            name="reviewer",
            scopes=("engineering-review",),
        )
        first = auth_mod.issue_engineering_review_assertion(
            principal,
            {"delivery_id": "delivery-1", "decision": "adopted", "evidence_refs": ["evidence://review/1"]},
        )
        changed = auth_mod.issue_engineering_review_assertion(
            principal,
            {"delivery_id": "delivery-1", "decision": "rejected", "evidence_refs": ["evidence://review/1"]},
        )

        assert first["schema"] == "cockpit-human-principal-assertion/v2"
        assert first["source_class"] == "real_human"
        assert len(first["signature"]) == 64
        assert first["binding_digest"] != changed["binding_digest"]
        assert first["signature"] != changed["signature"]

    def test_healthz_always_public(self, test_client, monkeypatch):
        """AUTH_REQUIRED=true 时 /healthz 仍然 200 (白名单路由)."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_AUTH_REQUIRED", True)
        auth_mod.reload_api_keys()
        resp = test_client.get("/healthz")
        assert resp.status_code == 200

    def test_subservice_token_from_env(self, monkeypatch):
        """get_subservice_token() 优先返回 COCKPIT_JWT_TOKEN, 其次 COCKPIT_API_KEY."""
        import cockpit.web.auth as auth_mod

        monkeypatch.setenv("COCKPIT_JWT_TOKEN", "jwt-abc")
        monkeypatch.setenv("COCKPIT_API_KEY", "api-xyz")
        assert auth_mod.get_subservice_token() == "jwt-abc"

        monkeypatch.delenv("COCKPIT_JWT_TOKEN", raising=False)
        assert auth_mod.get_subservice_token() == "api-xyz"

        monkeypatch.delenv("COCKPIT_API_KEY", raising=False)
        assert auth_mod.get_subservice_token() == ""
