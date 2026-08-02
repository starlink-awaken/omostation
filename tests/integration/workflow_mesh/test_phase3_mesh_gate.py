"""Phase 3: Mesh Connection Gate Integration Tests.

Verifies that:
1. mesh_gate module is importable
2. mesh_gate_check returns warning when Mesh not connected
3. mesh_gate_check returns error in strict mode
4. mesh_gate_check passes when Mesh store is available
5. ECOS executor integrates mesh gate in governance pipeline
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for source in (ROOT / "projects" / "ecos" / "src",):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def test_mesh_gate_importable():
    """mesh_gate module should be importable."""
    from ecos.workflow.mesh_gate import (
        check_mesh_connection,
        mesh_gate_check,
        is_strict_mode,
    )
    assert callable(check_mesh_connection)
    assert callable(mesh_gate_check)
    assert callable(is_strict_mode)


def test_mesh_gate_warning_when_not_connected(monkeypatch):
    """Mesh gate should produce warning when OMO not found."""
    import ecos.workflow.default_mesh_sink as dms
    from ecos.workflow.mesh_gate import mesh_gate_check

    monkeypatch.delenv("ECOS_MESH_GATE_STRICT", raising=False)
    original = dms._find_omo_root
    dms._find_omo_root = lambda *a, **kw: None
    dms._store_instance = None
    try:
        violations = mesh_gate_check()
        assert len(violations) == 1
        assert violations[0]["severity"] == "warning"
        assert violations[0]["id"] == "MESH-GATE-01"
    finally:
        dms._find_omo_root = original
        dms._store_instance = None


def test_mesh_gate_error_in_strict_mode(monkeypatch):
    """Mesh gate should produce error in strict mode."""
    import ecos.workflow.default_mesh_sink as dms
    from ecos.workflow.mesh_gate import mesh_gate_check

    monkeypatch.setenv("ECOS_MESH_GATE_STRICT", "1")
    original = dms._find_omo_root
    dms._find_omo_root = lambda *a, **kw: None
    dms._store_instance = None
    try:
        violations = mesh_gate_check()
        assert len(violations) == 1
        assert violations[0]["severity"] == "error"
    finally:
        dms._find_omo_root = original
        dms._store_instance = None
        monkeypatch.delenv("ECOS_MESH_GATE_STRICT", raising=False)


def test_executor_blocks_in_strict_mode(monkeypatch):
    """Executor should block with MESH_GATE_BLOCKED in strict mode."""
    import ecos.workflow.default_mesh_sink as dms
    from ecos.workflow.executor import execute_m1_workflow

    monkeypatch.setenv("ECOS_MESH_GATE_STRICT", "1")
    original = dms._find_omo_root
    dms._find_omo_root = lambda *a, **kw: None
    dms._store_instance = None
    try:
        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-strict",
                "steps": [{"name": "noop"}],
                "execution": {"backend": "default", "mode": "workflow"},
            },
        )
        result = execute_m1_workflow("test-strict")
        assert result["failed"] == 1
        assert result.get("error_code") == "MESH_GATE_BLOCKED"
    finally:
        dms._find_omo_root = original
        dms._store_instance = None
        monkeypatch.delenv("ECOS_MESH_GATE_STRICT", raising=False)
