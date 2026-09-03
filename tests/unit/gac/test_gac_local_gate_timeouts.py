from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gac_local_gate_timeouts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_semantic_gate_timeout_is_at_least_60_seconds() -> None:
    """Live sgf-policy often omits timeout; shipped defaults must still be 60s."""
    module = _load_module()
    assert module._DEFAULT_CHECK_TIMEOUTS["governance-semantic-gate"] == 60
    assert module._CHECK_TIMEOUTS["governance-semantic-gate"] >= 60
    fallback = next(
        gate
        for gate in module.DEFAULT_POLICY["gates"]
        if gate["id"] == "governance-semantic-gate"
    )
    assert fallback.get("timeout") == 60


def test_agent_workflow_doctor_has_explicit_full_integration_timeout() -> None:
    """The full doctor probes multiple project integrations sequentially."""
    module = _load_module()

    assert module._DEFAULT_CHECK_TIMEOUTS["agent-workflow-doctor"] == 45
    assert module._CHECK_TIMEOUTS["agent-workflow-doctor"] >= 45
