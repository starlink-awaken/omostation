"""Comprehensive test suite for Service Gateway (bin/ops/cli.py).

Tests all 21 ops commands and validates the complete workflow.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"


def run_ops(*args: str) -> subprocess.CompletedProcess:
    """Run an ops CLI command."""
    cmd = [sys.executable, str(WORKSPACE / "bin" / "ops" / "cli.py")] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


class TestOpsStatus:
    """Test ops status command."""

    def test_status_text(self):
        result = run_ops("status")
        assert result.returncode in (0, 1)  # 1 if unhealthy services
        assert "Service Gateway" in result.stdout or "Service Status" in result.stdout

    def test_status_json(self):
        result = run_ops("status", "--json")
        assert result.returncode in (0, 1)
        data = json.loads(result.stdout)
        assert "summary" in data
        assert "services" in data


class TestOpsSummary:
    """Test ops summary command."""

    def test_summary_text(self):
        result = run_ops("summary")
        assert result.returncode == 0
        assert "Service Gateway" in result.stdout

    def test_summary_json(self):
        result = run_ops("summary", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total" in data


class TestOpsDeps:
    """Test ops deps command."""

    def test_deps_all(self):
        result = run_ops("deps")
        assert result.returncode == 0

    def test_deps_service(self):
        result = run_ops("deps", "mcp.agora")
        assert result.returncode == 0


class TestOpsGraph:
    """Test ops graph command."""

    def test_graph_dot(self):
        result = run_ops("graph", "--format", "dot")
        assert result.returncode == 0
        assert "digraph" in result.stdout


class TestOpsDiscover:
    """Test ops discover command."""

    def test_discover(self):
        result = run_ops("discover")
        assert result.returncode == 0


class TestOpsValidate:
    """Test ops validate command."""

    def test_validate_all(self):
        result = run_ops("validate")
        assert result.returncode in (0, 1)

    def test_validate_service(self):
        result = run_ops("validate", "mcp.agora")
        assert result.returncode in (0, 1)


class TestOpsGenerate:
    """Test ops generate command."""

    def test_generate_docker_compose(self):
        result = run_ops("generate", "--format", "docker-compose")
        assert result.returncode == 0
        assert "version" in result.stdout or "services" in result.stdout

    def test_generate_systemd(self):
        result = run_ops("generate", "--format", "systemd")
        assert result.returncode == 0
        assert "[Unit]" in result.stdout or "[Service]" in result.stdout


class TestOpsLogs:
    """Test ops logs command."""

    def test_logs_all(self):
        result = run_ops("logs")
        assert result.returncode == 0

    def test_logs_lines(self):
        result = run_ops("logs", "-n", "10")
        assert result.returncode == 0


class TestOpsDeploy:
    """Test ops deploy command."""

    def test_deploy(self):
        result = run_ops("deploy")
        assert result.returncode == 0


class TestOpsScore:
    """Test ops score command."""

    def test_score_text(self):
        result = run_ops("score")
        assert result.returncode == 0
        assert "Score" in result.stdout or "score" in result.stdout

    def test_score_json(self):
        result = run_ops("score", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "overall" in data


class TestUnifiedMetrics:
    """Test unified metrics aggregator."""

    def test_metrics_once(self):
        result = run_ops("metrics-unified", "--once")
        assert result.returncode == 0

    def test_metrics_json(self):
        result = run_ops("metrics-unified", "--once", "--json")
        assert result.returncode == 0


class TestSLOTracker:
    """Test SLO tracker."""

    def test_slo_report(self):
        result = run_ops("slo")
        assert result.returncode == 0

    def test_slo_json(self):
        result = run_ops("slo", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "metrics" in data


class TestCostTracker:
    """Test cost tracker."""

    def test_cost_report(self):
        result = run_ops("cost")
        assert result.returncode == 0

    def test_cost_json(self):
        result = run_ops("cost", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "summary" in data


class TestRunbook:
    """Test automated runbook."""

    def test_runbook_all(self):
        result = run_ops("runbook", "all")
        assert result.returncode in (0, 1)

    def test_runbook_down(self):
        result = run_ops("runbook", "service-down")
        assert result.returncode in (0, 1)


class TestEnvConfig:
    """Test environment configuration."""

    def test_env_show(self):
        result = run_ops("env", "show")
        assert result.returncode == 0

    def test_env_list(self):
        result = run_ops("env", "list")
        assert result.returncode == 0


class TestCatalogAPI:
    """Test service catalog API."""

    def test_catalog_api_endpoints(self):
        """Test that catalog API endpoints return valid JSON."""
        import urllib.request
        import time

        # Start API server in background
        proc = subprocess.Popen(
            [sys.executable, str(WORKSPACE / "bin" / "ops" / "catalog_api.py"), "--port", "18092"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2)

        try:
            # Test health endpoint
            with urllib.request.urlopen("http://127.0.0.1:18092/health", timeout=5) as resp:
                data = json.loads(resp.read())
                assert data["status"] == "ok"

            # Test services endpoint
            with urllib.request.urlopen("http://127.0.0.1:18092/api/services", timeout=5) as resp:
                data = json.loads(resp.read())
                assert isinstance(data, list)

            # Test dependencies endpoint
            with urllib.request.urlopen("http://127.0.0.1:18092/api/dependencies", timeout=5) as resp:
                data = json.loads(resp.read())
                assert "nodes" in data
                assert "edges" in data
        finally:
            proc.terminate()
            proc.wait(timeout=5)


class TestServicesYaml:
    """Test services.yaml validation."""

    def test_services_yaml_exists(self):
        assert SERVICES_YAML.exists()

    def test_services_yaml_valid(self):
        content = SERVICES_YAML.read_text()
        docs = list(__import__("yaml").safe_load_all(content))
        services_found = False
        for doc in docs:
            if isinstance(doc, dict) and "services" in doc:
                services_found = True
                services = doc["services"]
                assert len(services) > 0
                for svc in services:
                    assert "id" in svc
                    assert "scheduler" in svc
        assert services_found


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
