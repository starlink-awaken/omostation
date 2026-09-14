"""Tests for DFlash 2 speculative integration (BET-Y1Q3-T10-114).

7 unit tests covering:
1. DFlash 2 constants defined
2. SpeculativeRoutingDecision has new fields
3. should_fallback_to_ar circuit breaker logic
4. dflash2_throughput_target_met (27B vs smaller models)
5. dflash2_speedup_target_met (>=2.4x)
6. Router decision has dflash2_enabled and draft_hit_rate
7. to_dict() includes new fields
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

WS_ROOT = Path(__file__).resolve().parent.parent
SP_PATH = WS_ROOT / "projects" / "omlxc" / "src" / "omlxc" / "dataplane" / "speculative.py"


def _load():
    """Load via exec to bypass dataclass + importlib py3.14 issue."""
    source = SP_PATH.read_text(encoding="utf-8")
    mod = types.ModuleType("sp_test")
    mod.__file__ = str(SP_PATH)
    sys.modules["sp_test"] = mod
    exec(compile(source, str(SP_PATH), "exec"), mod.__dict__)
    return mod


@pytest.fixture
def sp():
    return _load()


def test_dflash2_constants_defined(sp):
    """DFlash 2 config constants should be present."""
    assert sp.DFLASH2_BLOCK_SIZE_TOKENS == 32
    assert sp.DFLASH2_BYTES_PER_TOKEN == 2048
    assert sp.DFLASH2_DRAFT_HIT_RATE_THRESHOLD == 0.40
    assert sp.DFLASH2_TARGET_TOKENS_PER_SEC == 120
    assert sp.DFLASH2_TARGET_SPEEDUP_RATIO == 2.4


def test_routing_decision_has_dflash2_fields(sp):
    """SpeculativeRoutingDecision has new dflash2_enabled and draft_hit_rate fields."""
    decision = sp.SpeculativeRoutingDecision(
        target_tier="local",
        recommended_model="qwen3.8-27b",
        draft_model="qwen3.5-7b",
        estimated_speedup_ratio=2.5,
        reasoning="test",
        dflash2_enabled=True,
        draft_hit_rate=0.75,
    )
    assert decision.dflash2_enabled is True
    assert decision.draft_hit_rate == 0.75
    assert decision.target_tier == "local"


def test_should_fallback_below_threshold(sp):
    """草稿命中率 < 40% 时降级为自回归."""
    assert sp.should_fallback_to_ar(0.39) is True
    assert sp.should_fallback_to_ar(0.30) is True
    assert sp.should_fallback_to_ar(0.0) is True


def test_should_not_fallback_at_or_above_threshold(sp):
    """草稿命中率 >= 40% 时保持投机解码."""
    assert sp.should_fallback_to_ar(0.40) is False
    assert sp.should_fallback_to_ar(0.50) is False
    assert sp.should_fallback_to_ar(0.85) is False


def test_dflash2_throughput_target_27b(sp):
    """27B 吞吐量 >= 120 tokens/s 为达标."""
    assert sp.dflash2_throughput_target_met(120.0) is True
    assert sp.dflash2_throughput_target_met(150.0) is True
    assert sp.dflash2_throughput_target_met(119.9) is False
    assert sp.dflash2_throughput_target_met(50.0) is False


def test_dflash2_throughput_target_other_models(sp):
    """非 27B 模型不强制 120 tokens/s 阈值."""
    assert sp.dflash2_throughput_target_met(0.0, target_model="qwen3-8b") is True
    assert sp.dflash2_throughput_target_met(10.0, target_model="qwen2.5-coder:14b") is True


def test_dflash2_speedup_target(sp):
    """加速比 >= 2.4x 为达标."""
    assert sp.dflash2_speedup_target_met(2.4) is True
    assert sp.dflash2_speedup_target_met(3.0) is True
    assert sp.dflash2_speedup_target_met(2.39) is False
    assert sp.dflash2_speedup_target_met(1.5) is False


def test_router_decision_uses_dflash2(sp):
    """Router 决策含 dflash2 状态与草稿命中率."""
    decision = sp.SpeculativeRouter().evaluate("fix bug in foo.py")
    assert decision.dflash2_enabled is True  # 本地 triage 用 dflash2
    assert decision.draft_hit_rate > 0.0
    d = decision.to_dict()
    assert "dflash2_enabled" in d
    assert "draft_hit_rate" in d


def test_router_long_context_uses_dflash2(sp):
    """长上下文 (>500 字) 走 hybrid-speculative + dflash2."""
    long_prompt = "架构" + "设计" * 200
    decision = sp.SpeculativeRouter().evaluate(long_prompt)
    assert decision.target_tier == "hybrid-speculative"
    assert decision.dflash2_enabled is True
    assert 0.5 < decision.draft_hit_rate < 0.8  # 0.65 typical


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
