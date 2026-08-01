"""Adversarial and Fallback testing for Agora MCP cross-layer communication (Milestone M1)

This test suite executes stress, fallback, and proxy robustness checks on:
- ecos.workflow.agora_mcp_backend
- ecos.workflow.backends.swarm
- ecos.workflow.circuit_breaker
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure projects/ecos/src is in Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ecos.workflow import circuit_breaker as cb
from ecos.workflow.executor import execute_m1_workflow


@pytest.fixture(autouse=True)
def cleanup_circuit_breaker():
    cb.reset_all()
    yield
    cb.reset_all()


# ── 1. Agora MCP Unreachable Fallback Tests ──


def test_agora_unreachable_fallback_connection_error():
    """Test that when Agora MCP raises a Connection Error during health check,
    it trips the circuit breaker and falls back to the default local executor.
    """
    # Verify initially available
    assert cb.is_available("agora", "mcp-gateway") is True

    # Setup a workflow with one simple health check step
    wf_node = {
        "name": "test-fallback-wf",
        "steps": [{"name": "step1", "action": "health_check"}],
        "execution": {"backend": "agora", "mode": "sequential"},
    }

    # Mock load_workflow to return this workflow
    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")),
        patch("ecos.workflow.backend_registry._default_executor") as mock_default_exec,
    ):
        mock_default_exec.return_value = {
            "steps": [{"name": "step1", "status": "ok"}],
            "passed": 1,
            "failed": 0,
        }

        # Run execute_m1_workflow
        result = execute_m1_workflow("test-fallback-wf")

        # Explicit Agora backend unavailable must not invoke the default executor.
        mock_default_exec.assert_not_called()
        assert result["passed"] == 0
        assert result["failed"] >= 1
        assert result["run_metadata"]["state"] == "unavailable"
        assert result["error_code"] == "BACKEND_UNAVAILABLE"

        # Verify circuit breaker got TRIPPED
        assert cb.is_available("agora", "mcp-gateway") is False


def test_agora_unreachable_fallback_http_error():
    """Test that when Agora MCP returns a non-200 HTTP code during health check,
    it trips the circuit breaker and falls back to default.
    """
    # Verify initially available
    assert cb.is_available("agora", "mcp-gateway") is True

    wf_node = {
        "name": "test-fallback-wf-http",
        "steps": [{"name": "step1", "action": "health_check"}],
        "execution": {"backend": "agora", "mode": "sequential"},
    }

    # Mock response with 500 status code
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch("httpx.Client.get", return_value=mock_resp),
        patch("ecos.workflow.backend_registry._default_executor") as mock_default_exec,
    ):
        mock_default_exec.return_value = {
            "steps": [{"name": "step1", "status": "ok"}],
            "passed": 1,
            "failed": 0,
        }

        result = execute_m1_workflow("test-fallback-wf-http")

        mock_default_exec.assert_not_called()
        assert result["passed"] == 0
        assert result["error_code"] == "BACKEND_UNAVAILABLE"
        assert cb.is_available("agora", "mcp-gateway") is False


def test_agora_unreachable_fallback_timeout():
    """Test that when Agora MCP health check times out, it trips the circuit breaker
    and falls back to default.
    """
    wf_node = {
        "name": "test-fallback-wf-timeout",
        "steps": [{"name": "step1", "action": "health_check"}],
        "execution": {"backend": "agora", "mode": "sequential"},
    }

    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch(
            "httpx.Client.get", side_effect=httpx.TimeoutException("Request timed out")
        ),
        patch("ecos.workflow.backend_registry._default_executor") as mock_default_exec,
    ):
        mock_default_exec.return_value = {
            "steps": [{"name": "step1", "status": "ok"}],
            "passed": 1,
            "failed": 0,
        }

        result = execute_m1_workflow("test-fallback-wf-timeout")

        mock_default_exec.assert_not_called()
        assert result["passed"] == 0
        assert result["error_code"] == "BACKEND_UNAVAILABLE"
        assert cb.is_available("agora", "mcp-gateway") is False


# ── 2. Circuit Breaker OPEN skip health check test ──


def test_circuit_breaker_open_skips_health_check():
    """Test that when circuit breaker is already open (tripped),
    it immediately falls back without calling httpx.Client.get.
    """
    # Force trip the circuit breaker
    cb.trip("agora", "mcp-gateway", ttl=10)
    assert cb.is_available("agora", "mcp-gateway") is False

    wf_node = {
        "name": "test-cb-open-wf",
        "steps": [{"name": "step1", "action": "health_check"}],
        "execution": {"backend": "agora", "mode": "sequential"},
    }

    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch("httpx.Client.get") as mock_get,
        patch("ecos.workflow.backend_registry._default_executor") as mock_default_exec,
    ):
        mock_default_exec.return_value = {
            "steps": [{"name": "step1", "status": "ok"}],
            "passed": 1,
            "failed": 0,
        }

        result = execute_m1_workflow("test-cb-open-wf")

        # Verify default executor is never called and health check is skipped.
        mock_default_exec.assert_not_called()
        mock_get.assert_not_called()
        assert result["passed"] == 0
        assert result["error_code"] == "BACKEND_UNAVAILABLE"


# ── 3. Proxy Bypassing Robustness Tests ──


def test_proxy_bypassed_due_to_trust_env_false():
    """Test that setting bad environment proxies (e.g. HTTP_PROXY) does not impact
    the ability of httpx to contact Agora MCP because trust_env=False is explicitly specified.
    """
    # Setup bad proxy environment variables
    env_backup = {
        k: os.environ.get(k) for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]
    }
    os.environ["HTTP_PROXY"] = "http://non-existent-proxy-host:8888"
    os.environ["HTTPS_PROXY"] = "http://non-existent-proxy-host:8888"
    os.environ["ALL_PROXY"] = "http://non-existent-proxy-host:8888"

    try:
        wf_node = {
            "name": "test-proxy-wf",
            "steps": [{"name": "step1", "action": "health_check"}],
            "execution": {"backend": "agora", "mode": "sequential"},
        }

        # Mock a successful Agora MCP RPC response
        mock_health_resp = MagicMock()
        mock_health_resp.status_code = 200

        mock_tool_resp = MagicMock()
        mock_tool_resp.status_code = 200
        mock_tool_resp.json.return_value = {
            "success": True,
            "status": "ok",
            "result": {"passed": True},
        }

        # We will spy on the client initialization to assert that trust_env=False is passed.
        original_client_init = httpx.Client.__init__
        client_init_args = []

        def spy_client_init(self, *args, **kwargs):
            client_init_args.append(kwargs)
            original_client_init(self, *args, **kwargs)

        with (
            patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
            patch.object(httpx.Client, "__init__", spy_client_init),
            patch("httpx.Client.get", return_value=mock_health_resp),
            patch("httpx.Client.post", return_value=mock_tool_resp),
        ):
            result = execute_m1_workflow("test-proxy-wf")

            # Check that execution was routed via Agora MCP successfully
            assert result["passed"] == 1
            assert result["failed"] == 0

            # Check that trust_env=False was passed to all httpx.Client instances
            assert len(client_init_args) >= 2
            for kwargs in client_init_args:
                assert kwargs.get("trust_env") is False, (
                    "trust_env must be set to False to bypass global proxies!"
                )

    finally:
        # Restore environment
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── 4. Swarm Backend Fallback/Error handling Tests ──


def test_swarm_backend_graceful_error_no_crash():
    """Test that Swarm backend does not raise unhandled exceptions and crash the workflow
    when Agora MCP is unreachable, but returns failed steps gracefully.
    """
    wf_node = {
        "name": "test-swarm-fail-wf",
        "steps": [{"name": "step1", "action": "research"}],
        "execution": {"backend": "swarm", "mode": "sequential"},
    }

    # Mock Agora health check/calls to fail
    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch(
            "httpx.Client.post",
            side_effect=httpx.ConnectError("Swarm Agora endpoint down"),
        ),
    ):
        # Run execute_m1_workflow
        result = execute_m1_workflow("test-swarm-fail-wf")

        # Verify unavailable is explicit and not a mock success.
        assert result["passed"] == 0
        assert result["failed"] >= 1
        assert "steps" in result
        assert result["run_metadata"]["state"] == "unavailable"
        assert result["error_code"] == "BACKEND_UNAVAILABLE"


# ── 5. Agora Backend mid-workflow step failures ──


def test_agora_mid_workflow_http_error_abort():
    """Test that when Agora health check succeeds but a specific step execution returns non-200,
    the Agora backend reports the step as failed. If on_failure=abort, it aborts immediately.
    """
    wf_node = {
        "name": "test-mid-fail-abort-wf",
        "steps": [
            {"name": "step1", "action": "health_check", "on_failure": "abort"},
            {"name": "step2", "action": "domain_sync"},
        ],
        "execution": {"backend": "agora", "mode": "sequential"},
    }

    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 200

    # Step 1 call returns HTTP 500
    mock_tool_resp = MagicMock()
    mock_tool_resp.status_code = 500

    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch("httpx.Client.get", return_value=mock_health_resp),
        patch("httpx.Client.post", return_value=mock_tool_resp),
    ):
        result = execute_m1_workflow("test-mid-fail-abort-wf")

        # Verify it did not crash, step1 failed, and step2 was not executed (aborted)
        assert result["passed"] == 0
        assert result["failed"] == 1
        assert len(result["steps"]) == 1
        assert result["steps"][0]["name"] == "step1"
        assert result["steps"][0]["status"] == "failed"
        assert "Agora returned HTTP 500" in result["steps"][0]["error"]


def test_agora_mid_workflow_exception_continue():
    """Test that when Agora health check succeeds but a specific step execution raises an exception,
    the backend records it as status: error. If on_failure=continue (default), it continues to the next step.
    """
    wf_node = {
        "name": "test-mid-exc-continue-wf",
        "steps": [
            {"name": "step1", "action": "health_check"},
            {"name": "step2", "action": "domain_sync"},
        ],
        "execution": {
            "backend": "agora",
            "mode": "sequential",
            "on_failure": "continue",
        },
    }

    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 200

    # Mock tool post raising exception for step1, but succeeding for step2
    mock_success_resp = MagicMock()
    mock_success_resp.status_code = 200
    mock_success_resp.json.return_value = {
        "success": True,
        "status": "ok",
        "result": {"passed": True},
    }

    def mock_post(*args, **kwargs):
        json_data = kwargs.get("json", {})
        uri = json_data.get("arguments", {}).get("uri", "")
        if "governance/omo/audit" in uri or "health_check" in uri:
            raise httpx.ConnectError("Mid-workflow exception connection lost")
        return mock_success_resp

    with (
        patch("ecos.workflow.executor.load_workflow", return_value=wf_node),
        patch("httpx.Client.get", return_value=mock_health_resp),
        patch("httpx.Client.post", side_effect=mock_post),
    ):
        result = execute_m1_workflow("test-mid-exc-continue-wf")

        # Verify no crash, step1 is error, step2 is ok (continued execution)
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "step1"
        assert result["steps"][0]["status"] == "error"
        assert "Mid-workflow exception" in result["steps"][0]["error"]

        assert result["steps"][1]["name"] == "step2"
        assert result["steps"][1]["status"] == "ok"
        assert result["passed"] == 1
        assert result["failed"] == 1
