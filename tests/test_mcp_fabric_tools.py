"""Unit tests for Agora MCP fabric tools."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
from agora.mcp.tools.fabric import fabric_inspect, fabric_triage, fabric_vram_budget


def test_fabric_inspect_mcp_tool() -> None:
    fake_stdout = '{"schema_version":"1","data":{"thermal_pressure":"nominal","supported_tiers":["fast","standard","reasoning"]}}'
    mock_proc = MagicMock(returncode=0, stdout=fake_stdout, stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        res = fabric_inspect()
        assert res["status"] == "ok"
        assert res["fabric"]["thermal_pressure"] == "nominal"


def test_fabric_triage_mcp_tool() -> None:
    fake_stdout = '{"schema_version":"1","data":{"tier":"reasoning","confidence":0.85,"reason":"detected architectural/reasoning keywords in user prompt"}}'
    mock_proc = MagicMock(returncode=0, stdout=fake_stdout, stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        res = fabric_triage("Design a lock-free queue")
        assert res["status"] == "ok"
        assert res["triage"]["tier"] == "reasoning"


def test_fabric_vram_budget_mcp_tool() -> None:
    fake_stdout = '{"schema_version":"1","data":{"model_id":"coding","context_tokens":32768,"kv_cache_mb":8448.0}}'
    mock_proc = MagicMock(returncode=0, stdout=fake_stdout, stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        res = fabric_vram_budget("coding", 32768)
        assert res["status"] == "ok"
        assert res["vram_budget"]["kv_cache_mb"] == 8448.0
