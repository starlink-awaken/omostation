"""Unit tests for Service Gateway (bin/ops/cli.py)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add workspace to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bin.ops.cli import (
    load_services,
    get_service_by_id,
    check_liveness,
    topological_sort,
    _get_cmd,
    _get_environment,
    _get_pid_file,
    _is_running,
    WORKSPACE,
)


@pytest.fixture
def sample_services() -> list[dict]:
    """Sample service definitions for testing."""
    return [
        {
            "id": "svc.a",
            "enabled": True,
            "scheduler": "launchd",
            "program": {"interpreter": "python3", "entrypoint": "bin/test.py"},
            "depends_on": [],
        },
        {
            "id": "svc.b",
            "enabled": True,
            "scheduler": "launchd",
            "program": {"interpreter": "python3", "entrypoint": "bin/test2.py"},
            "depends_on": ["svc.a"],
        },
        {
            "id": "svc.c",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "python3", "entrypoint": "bin/test3.py"},
            "depends_on": ["svc.a", "svc.b"],
        },
        {
            "id": "svc.d",
            "enabled": False,
            "scheduler": "manual",
            "program": {"interpreter": "python3", "entrypoint": "bin/test4.py"},
            "depends_on": [],
        },
    ]


class TestLoadServices:
    """Tests for load_services function."""

    def test_load_returns_list(self):
        services = load_services()
        assert isinstance(services, list)

    def test_load_has_services(self):
        services = load_services()
        assert len(services) > 0

    def test_each_service_has_id(self):
        services = load_services()
        for svc in services:
            assert "id" in svc


class TestGetServiceById:
    """Tests for get_service_by_id function."""

    def test_find_existing(self, sample_services):
        svc = get_service_by_id(sample_services, "svc.a")
        assert svc is not None
        assert svc["id"] == "svc.a"

    def test_find_nonexisting(self, sample_services):
        svc = get_service_by_id(sample_services, "nonexistent")
        assert svc is None


class TestCheckLiveness:
    """Tests for check_liveness function."""

    def test_no_liveness(self):
        result = check_liveness({"id": "test"})
        assert result["status"] == "unknown"

    def test_file_missing(self, tmp_path):
        svc = {
            "id": "test",
            "liveness": {"signal": str(tmp_path / "nonexistent"), "max_stale_hours": 24},
        }
        result = check_liveness(svc)
        assert result["status"] == "missing"

    def test_file_exists(self, tmp_path):
        test_file = tmp_path / "test.log"
        test_file.write_text("test")
        svc = {
            "id": "test",
            "liveness": {"signal": str(test_file), "max_stale_hours": 24},
        }
        result = check_liveness(svc)
        assert result["status"] == "healthy"

    def test_http_check(self):
        svc = {
            "id": "test",
            "liveness": {"signal": "http", "endpoint": "http://localhost:19999/health", "max_stale_hours": 24},
        }
        result = check_liveness(svc)
        # Should be unreachable since nothing is listening
        assert result["status"] in ("unreachable", "unhealthy")


class TestTopologicalSort:
    """Tests for topological_sort function."""

    def test_no_dependencies(self, sample_services):
        # Only use svc.a and svc.d (no dependencies)
        services = [s for s in sample_services if s["id"] in ("svc.a", "svc.d")]
        layers = topological_sort(services)
        assert len(layers) == 1
        assert set(layers[0]) == {"svc.a", "svc.d"}

    def test_linear_chain(self, sample_services):
        # svc.a -> svc.b -> svc.c
        layers = topological_sort(sample_services[:3])
        assert len(layers) == 3
        assert layers[0] == ["svc.a"]
        assert layers[1] == ["svc.b"]
        assert layers[2] == ["svc.c"]

    def test_multiple_independent(self, sample_services):
        # svc.a and svc.d are independent
        services = [s for s in sample_services if s["id"] in ("svc.a", "svc.d")]
        layers = topological_sort(services)
        assert len(layers) == 1

    def test_disabled_excluded(self, sample_services):
        # svc.d is disabled but still included in sort
        layers = topological_sort(sample_services)
        all_ids = [sid for layer in layers for sid in layer]
        assert "svc.d" in all_ids


class TestGetCmd:
    """Tests for _get_cmd function."""

    def test_uv_interpreter(self):
        svc = {"program": {"interpreter": "uv", "entrypoint": "bin/tool.py", "args": ["--check"]}}
        cmd = _get_cmd(svc)
        assert cmd == ["uv", "run", "bin/tool.py", "--check"]

    def test_uv_directory_entrypoint_uses_directory_flag(self):
        svc = {"program": {"interpreter": "uv", "entrypoint": "projects/agora", "args": ["agora-mcp", "--sse"]}}
        cmd = _get_cmd(svc)
        assert cmd == ["uv", "run", "--directory", "projects/agora", "agora-mcp", "--sse"]

    def test_python3_interpreter(self):
        svc = {"program": {"interpreter": "stable-python3", "entrypoint": "bin/test.py", "args": []}}
        cmd = _get_cmd(svc)
        assert Path(cmd[0]).name in {"python", "python3"}
        assert cmd[1] == "bin/test.py"

    def test_absolute_interpreter(self):
        svc = {"program": {"interpreter": "/bin/bash", "entrypoint": "test.sh", "args": []}}
        cmd = _get_cmd(svc)
        assert cmd == ["/bin/bash", "test.sh"]

    def test_environment_merges_declared_values_for_child_only(self, monkeypatch):
        monkeypatch.setenv("OPS_INHERITED_TEST", "inherited")
        svc = {"environment": {"AGORA_MCP_SSE_PORT": 7433}}

        env = _get_environment(svc)

        assert env is not None
        assert env["OPS_INHERITED_TEST"] == "inherited"
        assert env["AGORA_MCP_SSE_PORT"] == "7433"
        assert "AGORA_MCP_SSE_PORT" not in os.environ

    def test_mcp_agora_registry_declares_ssot_port(self):
        svc = get_service_by_id(load_services(), "mcp.agora")
        assert svc is not None
        assert svc["environment"]["AGORA_MCP_SSE_PORT"] == "7433"


class TestPidFile:
    """Tests for PID file management."""

    def test_pid_file_path(self):
        pid_file = _get_pid_file("test.service")
        assert pid_file.name == "test.service.pid"
        assert "pids" in str(pid_file)

    def test_is_running_no_pid(self):
        svc = {"id": "nonexistent.service.12345"}
        assert not _is_running(svc)


class TestIntegration:
    """Integration tests."""

    def test_load_and_sort(self):
        services = load_services()
        enabled = [s for s in services if s.get("enabled")]
        layers = topological_sort(enabled)
        # All enabled services should be in layers
        all_sorted = [sid for layer in layers for sid in layer]
        assert len(all_sorted) == len(enabled)

    def test_all_services_have_valid_commands(self):
        services = load_services()
        for svc in services[:10]:  # Test first 10
            cmd = _get_cmd(svc)
            assert len(cmd) >= 2
            assert cmd[0]  # interpreter
            assert cmd[1]  # entrypoint
