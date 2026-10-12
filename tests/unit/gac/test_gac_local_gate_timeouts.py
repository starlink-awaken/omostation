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
    """Live sgf-policy often omits timeout; shipped default must stay >= 60s.

    #4579 把 governance-semantic-gate 默认预算 60→180(60s 硬顶仅 3.7s 余量,
    周期性 TIMEOUT 被翻成 blocking ERROR 阻断交付——与 agent-workflow-doctor
    60→120 同病)。断言下限而非精确值, 精确值以 gac-local-gate.py 实测注释为准。
    """
    module = _load_module()
    assert module._DEFAULT_CHECK_TIMEOUTS["governance-semantic-gate"] >= 60
    assert module._CHECK_TIMEOUTS["governance-semantic-gate"] >= 60
    fallback = next(
        gate
        for gate in module.DEFAULT_POLICY["gates"]
        if gate["id"] == "governance-semantic-gate"
    )
    assert fallback.get("timeout") == module._DEFAULT_CHECK_TIMEOUTS["governance-semantic-gate"]  # 同步 #4579 口径


def test_agent_workflow_doctor_has_explicit_full_integration_timeout() -> None:
    """The aggregate doctor has an explicit end-to-end outer budget."""
    module = _load_module()

    assert module._DEFAULT_CHECK_TIMEOUTS["agent-workflow-doctor"] == 120
    assert module._CHECK_TIMEOUTS["agent-workflow-doctor"] >= 120
