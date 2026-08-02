"""Tests for A2A and OMO Agent Workflow convergence metadata (ADR-0300)."""

from __future__ import annotations

import os
from unittest.mock import patch

from agora.server.tools_governance import _resolve_convergence_meta


def test_resolve_convergence_meta_default_inference():
    """验证对 tool_name 的默认 5 大主域以及 packages 的正向映射。"""
    meta = _resolve_convergence_meta("kems.graph")
    assert meta["domain"] == "memory"
    assert meta["bos_uri"] == "bos://memory/kems/graph"
    assert meta["adr_policy"] == "ADR-0300"

    meta_code = _resolve_convergence_meta("codeanalyze.scan")
    assert meta_code["domain"] == "analysis"
    assert meta_code["bos_uri"] == "bos://analysis/codeanalyze/scan"

    meta_af = _resolve_convergence_meta("aetherforge.swarm")
    assert meta_af["domain"] == "compute"
    assert meta_af["bos_uri"] == "bos://compute/aetherforge/swarm"


def test_resolve_convergence_meta_run_id_env_injection():
    """验证 OMO Agent Workflow Run-ID 从环境变量能够自感应并映射到元数据中。"""
    with patch.dict(os.environ, {"AGCP_RUN_ID": "20260802T120000Z-test-run-1234"}):
        meta = _resolve_convergence_meta("minerva.research_now")
        assert meta["run_id"] == "20260802T120000Z-test-run-1234"
        assert meta["domain"] == "analysis"


def test_resolve_convergence_meta_explicit_override():
    """验证调用方显式传参时，参数优先级高于推导值。"""
    meta = _resolve_convergence_meta(
        tool_name="kems.graph",
        run_id="20260802-explicit-id",
        bos_uri="bos://memory/kems/custom_action",
    )
    assert meta["run_id"] == "20260802-explicit-id"
    assert meta["bos_uri"] == "bos://memory/kems/custom_action"
    assert meta["domain"] == "memory"
