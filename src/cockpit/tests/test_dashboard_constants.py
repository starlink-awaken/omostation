"""Tests for cockpit.dashboard.constants — paths, config, layer sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from cockpit.dashboard import constants


class TestConstants:
    """所有 paths/ports 应该是 Path/int 类型, 不应该是空字符串"""

    def test_project_root_is_path(self):
        assert isinstance(constants.PROJECT_ROOT, Path)
        assert constants.PROJECT_ROOT.is_absolute()

    def test_workspace_root_is_path(self):
        assert isinstance(constants.WORKSPACE_ROOT, Path)

    def test_omo_root_is_path(self):
        assert isinstance(constants.OMO_ROOT, Path)

    def test_runtime_home_is_path(self):
        assert isinstance(constants.RUNTIME_HOME, Path)

    def test_dashboard_html_path(self):
        """BOS_DASHBOARD_HTML is an inline HTML template, not a file path."""
        assert isinstance(constants.BOS_DASHBOARD_HTML, str)
        assert len(constants.BOS_DASHBOARD_HTML) > 100

    def test_cockpit_ui_dist_path(self):
        assert isinstance(constants.COCKPIT_UI_DIST, Path)
        assert constants.COCKPIT_UI_DIST.name == "dist"

    def test_provider_plane_path(self):
        assert isinstance(constants.PROVIDER_PLANE_PATH, Path)
        assert constants.PROVIDER_PLANE_PATH.name == "provider-plane.yaml"

    def test_bos_metrics_path(self):
        assert isinstance(constants.BOS_METRICS_PATH, Path)
        assert str(constants.BOS_METRICS_PATH).endswith("bos-metrics.jsonl")

    def test_llm_paths_under_runtime_home(self):
        assert constants.LLM_QUOTA_SUMMARY_PATH.parent.parent == constants.RUNTIME_HOME
        assert constants.LLM_COST_LOG_PATH.parent.parent == constants.RUNTIME_HOME


class TestPort:
    def test_default_port_is_8090(self):
        assert constants.PORT == 8090

    def test_port_from_env(self, monkeypatch):
        monkeypatch.setenv("COCKPIT_DASHBOARD_PORT", "9999")
        # 重新 import
        import importlib

        importlib.reload(constants)
        try:
            assert constants.PORT == 9999
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_PORT", raising=False)
            importlib.reload(constants)

    def test_port_invalid_raises(self, monkeypatch):
        """非数字 PORT env 应抛 ValueError"""
        monkeypatch.setenv("COCKPIT_DASHBOARD_PORT", "not_a_number")
        import importlib

        try:
            with pytest.raises(ValueError):
                importlib.reload(constants)
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_PORT", raising=False)
            importlib.reload(constants)


class TestLayerSources:
    """LAYER_SOURCES 描述 4 层架构 (I0/L2/L1/L0) 的健康端点"""

    def test_layer_sources_is_list(self):
        assert isinstance(constants.LAYER_SOURCES, list)

    def test_layer_sources_has_4_entries(self):
        assert len(constants.LAYER_SOURCES) == 4

    def test_layer_sources_required_keys(self):
        required = {"layer", "name", "url", "port"}
        for src in constants.LAYER_SOURCES:
            assert required.issubset(src.keys()), f"missing {required - src.keys()} in {src}"

    def test_layer_sources_unique_layers(self):
        layers = [s["layer"] for s in constants.LAYER_SOURCES]
        assert len(layers) == len(set(layers)), f"duplicate layers: {layers}"

    def test_layer_sources_known_layers(self):
        """P43 5+4+1+1 架构: 4 个 layer 必须对应 I0/L2/L1/L0"""
        valid_layers = {"I0", "L2", "L1", "L0", "X", "L3", "L4"}
        for src in constants.LAYER_SOURCES:
            assert src["layer"] in valid_layers, f"unknown layer: {src['layer']}"

    def test_agora_is_i0_layer(self):
        """agora 必须是 I0 织层"""
        agora = [s for s in constants.LAYER_SOURCES if s["name"] == "agora"]
        assert len(agora) == 1
        assert agora[0]["layer"] == "I0"

    def test_omo_is_l2_layer(self):
        omo = [s for s in constants.LAYER_SOURCES if s["name"] == "omo"]
        assert len(omo) == 1
        assert omo[0]["layer"] == "L2"

    def test_ecos_layer_uses_m0_snapshot(self):
        """ecos L0 层用 m0_snapshot 协议 (非 HTTP)"""
        ecos = [s for s in constants.LAYER_SOURCES if s["name"] == "ecos"]
        assert len(ecos) == 1
        # m0_snapshot 协议: port=None, source="m0_snapshot"
        assert ecos[0]["port"] is None
        assert ecos[0].get("source") == "m0_snapshot"


class TestDefaultComputeTopology:
    """DEFAULT_COMPUTE_TOPOLOGY 描述默认部署拓扑"""

    def test_is_list(self):
        assert isinstance(constants.DEFAULT_COMPUTE_TOPOLOGY, list)

    def test_non_empty(self):
        assert len(constants.DEFAULT_COMPUTE_TOPOLOGY) > 0

    def test_required_keys(self):
        required = {"id", "label", "kind", "role"}
        for node in constants.DEFAULT_COMPUTE_TOPOLOGY:
            assert required.issubset(node.keys()), f"missing {required - node.keys()} in {node}"

    def test_unique_ids(self):
        ids = [n["id"] for n in constants.DEFAULT_COMPUTE_TOPOLOGY]
        assert len(ids) == len(set(ids)), f"duplicate node ids: {ids}"

    def test_known_kinds(self):
        valid = {"local", "remote", "edge", "cloud"}
        for node in constants.DEFAULT_COMPUTE_TOPOLOGY:
            assert node["kind"] in valid, f"unknown kind: {node['kind']}"


class TestRateLimit:
    def test_default_rate_limit_is_60(self):
        assert constants.DASHBOARD_RATE_LIMIT == 60

    def test_rate_limit_from_env(self, monkeypatch):
        monkeypatch.setenv("COCKPIT_DASHBOARD_RATE_LIMIT", "120")
        import importlib

        importlib.reload(constants)
        try:
            assert constants.DASHBOARD_RATE_LIMIT == 120
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_RATE_LIMIT", raising=False)
            importlib.reload(constants)


class TestDashboardToken:
    def test_default_token_empty_string(self):
        assert constants.DASHBOARD_TOKEN == ""

    def test_token_from_env(self, monkeypatch):
        token_value = "secret123"  # noqa: S105 (test fixture, not real credential)
        monkeypatch.setenv("COCKPIT_DASHBOARD_TOKEN", token_value)
        import importlib

        importlib.reload(constants)
        try:
            assert constants.DASHBOARD_TOKEN == token_value
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_TOKEN", raising=False)
            importlib.reload(constants)

    def test_token_with_special_chars(self, monkeypatch):
        special = "tok=abc;xyz&"
        monkeypatch.setenv("COCKPIT_DASHBOARD_TOKEN", special)
        import importlib

        importlib.reload(constants)
        try:
            assert constants.DASHBOARD_TOKEN == special
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_TOKEN", raising=False)
            importlib.reload(constants)


class TestCORSOrigin:
    def test_default_cors(self):
        assert constants.DASHBOARD_CORS_ORIGIN == "http://localhost:8090"

    def test_cors_from_env(self, monkeypatch):
        monkeypatch.setenv("COCKPIT_DASHBOARD_CORS_ORIGIN", "https://myapp.com")
        import importlib

        importlib.reload(constants)
        try:
            assert constants.DASHBOARD_CORS_ORIGIN == "https://myapp.com"
        finally:
            monkeypatch.delenv("COCKPIT_DASHBOARD_CORS_ORIGIN", raising=False)
            importlib.reload(constants)


class TestHTMLTemplates:
    """HTML 模板是非空字符串"""

    def test_overview_html_non_empty(self):
        assert isinstance(constants.OVERVIEW_HTML, str)
        assert len(constants.OVERVIEW_HTML) > 100
        assert "<!DOCTYPE" in constants.OVERVIEW_HTML

    def test_bos_dashboard_html_non_empty(self):
        assert isinstance(constants.BOS_DASHBOARD_HTML, str)
        assert len(constants.BOS_DASHBOARD_HTML) > 100

    def test_live_data_js_non_empty(self):
        assert isinstance(constants.LIVE_DATA_JS, str)
        assert "<script>" in constants.LIVE_DATA_JS


class TestConstantsInvariants:
    """跨字段一致性"""

    def test_all_workspace_paths_under_workspace_root(self):
        """WORKSPACE_ROOT 派生的 paths 都应在它下面"""
        assert str(constants.OMO_ROOT).startswith(str(constants.WORKSPACE_ROOT))
        assert str(constants.COCKPIT_UI_DIST).startswith(str(constants.WORKSPACE_ROOT))
        assert str(constants.BOS_METRICS_PATH).startswith(str(constants.WORKSPACE_ROOT))

    def test_runtime_paths_under_runtime_home(self):
        assert str(constants.LLM_QUOTA_SUMMARY_PATH).startswith(str(constants.RUNTIME_HOME))
        assert str(constants.LLM_COST_LOG_PATH).startswith(str(constants.RUNTIME_HOME))
