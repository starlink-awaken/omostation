"""journey-engine human_gate auto-complete — confidence-gated branching.

旧版 human_gate 无条件 escalate (confidence 条件从未评估).
修复后: confidence >= 旅程 spec 阈值 → 继续后续状态自动完成;
       confidence < 阈值 / 无匹配 → escalate (兜底安全).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("je", ROOT / "bin/ssot/journey-engine.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["je"] = m
    spec.loader.exec_module(m)
    return m


def _run_with_confidence(scene_id, conf):
    m = _load()

    orig = m._execute_action

    def stub(action, state_def, ctx):
        r = orig(action, state_def, ctx)
        if action in ("llm_classify", "generate_decision"):
            r["confidence"] = conf
        return r

    m._execute_action = stub
    return m.execute_journey(scene_id, {"source": "test", "content": "x"}, dry_run=False)


def test_high_confidence_autocompletes():
    # agora gateway: intent-to-execution, review_gate confidence >= 0.7 → recorded
    ctx = _run_with_confidence("scene-agora-bos-gateway", 0.85)
    assert ctx.status == "succeeded", f"expected succeeded, got {ctx.status} conf={ctx.confidence}"
    assert ctx.confidence >= 0.7
    # 经过了 recorded → knowledge_capture → completed (多步)
    states = [s["state"] for s in ctx.trace]
    assert "recorded" in states, f"trace: {states}"


def test_low_confidence_escalates():
    ctx = _run_with_confidence("scene-agora-bos-gateway", 0.3)
    assert ctx.status == "escalated"
    assert ctx.confidence == 0.3


if __name__ == "__main__":
    for n, fn in list(globals().items()):
        if n.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {n}")
            except Exception as e:
                print(f"  FAIL: {n}: {e}")
                raise
