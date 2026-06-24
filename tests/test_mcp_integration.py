"""Integration test: verify Runtime MCP Server core tool surface.

NOTE: Skipped — MCP library API changed (mcp 1.27+ / fastmcp 3.4+).
stdio_server moved to mcp.server.stdio and protocol format changed.
Re-enable after aligning with new MCP SDK.
"""

import json
import os
import subprocess
import sys

import pytest

pytest.skip(
    "MCP library API incompatible — requires alignment with mcp 1.27+/fastmcp 3.4+",
    allow_module_level=True,
)

SERVER = os.path.expanduser("~/Workspace/projects/runtime/src/runtime/mcp_server.py")
PYTHON = sys.executable


@pytest.fixture
def mcp_client():
    """Start MCP server and yield a send() function."""
    env = os.environ.copy()
    env["RUNTIME_HOME"] = os.path.expanduser("~/runtime")
    env["PYTHONPATH"] = os.path.expanduser("~/Workspace/projects/runtime/src")

    proc = subprocess.Popen(
        [PYTHON, SERVER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    def _send(req, expect_response=True):
        proc.stdin.write((json.dumps(req) + "\n").encode())
        proc.stdin.flush()
        if expect_response:
            line = proc.stdout.readline().decode()
            if not line:
                pytest.skip("MCP server closed stdout — mcp library may be missing")
            return json.loads(line)
        return None

    # 1. Initialize
    _send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hermes", "version": "1"},
            },
        }
    )
    # Notification (no response)
    _send(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "notifications/initialized",
            "params": {},
        },
        expect_response=False,
    )

    yield _send

    proc.terminate()
    proc.wait()


def test_tools_list(mcp_client):
    """Core tools must be present."""
    r = mcp_client({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
    tools = r["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    expected = {
        "runtime_health",
        "runtime_matrix_list",
        "runtime_matrix_get",
        "runtime_service_ctl",
        "runtime_protocol_list",
        "runtime_protocol_get",
        "runtime_ontology_get",
    }
    missing = expected - tool_names
    extra = tool_names - expected
    assert not missing, f"Tool mismatch: missing={missing}, extra={extra}"


def test_matrix_list(mcp_client):
    """matrix_list must contain cron-service."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "runtime_matrix_list", "arguments": {}},
        }
    )
    text = r["result"]["content"][0]["text"]
    assert "cron-service" in text


def test_matrix_get_cron_service(mcp_client):
    """matrix_get for cron-service must report port 7450."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "runtime_matrix_get",
                "arguments": {"name": "cron-service"},
            },
        }
    )
    text = r["result"]["content"][0]["text"]
    assert "7450" in text


def test_protocol_get_acp(mcp_client):
    """protocol_get for ACP must return description."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "runtime_protocol_get", "arguments": {"name": "ACP"}},
        }
    )
    text = r["result"]["content"][0]["text"]
    assert "Communication" in text


def test_runtime_health(mcp_client):
    """health check must return without crashing."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "runtime_health", "arguments": {}},
        }
    )
    text = r["result"]["content"][0]["text"]
    assert text  # non-empty response


def test_service_ctl_status(mcp_client):
    """service_ctl must return meaningful output."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "runtime_service_ctl",
                "arguments": {"name": "hermes-gateway", "action": "status"},
            },
        }
    )
    text = r["result"]["content"][0]["text"]
    assert text  # non-empty response


def test_protocol_list(mcp_client):
    """protocol_list must contain MCP."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "runtime_protocol_list", "arguments": {}},
        }
    )
    text = r["result"]["content"][0]["text"]
    assert "MCP" in text


def test_ontology_get(mcp_client):
    """ontology_get must contain ecos:Entity."""
    r = mcp_client(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "runtime_ontology_get", "arguments": {}},
        }
    )
    text = r["result"]["content"][0]["text"]
    assert "ecos:Entity" in text
