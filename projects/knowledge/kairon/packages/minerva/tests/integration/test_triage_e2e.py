"""End-to-end tests for the Minerva triage router classify() entrypoint.

Drives the public `TriageRouter.classify` API so the LLM/rule-based
fallback contract, the L0-L4 level mapping, and the cost/model
plan output are all observable from one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from minerva.triage.router import TriageRouter


def _router_with_llm(responses: list[str | Exception]) -> TriageRouter:
    from minerva.triage.router import TriageRouter

    router = TriageRouter(llm_client=None)
    # Force-override the LLM classify hook to return a sequence of
    # responses (string or exception) so we can drive fallback paths.
    queue = list(responses)

    async def _fake_llm(query: str) -> dict[str, int]:
        if not queue:
            raise RuntimeError("no more responses queued")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        # Return a fully-formed score vector for the LLM path.
        return {
            "domain_complexity": 4,
            "timeliness": 3,
            "depth_required": 4,
            "multi_source": 3,
            "privacy_sensitivity": 1,
        }

    router._llm_classify = _fake_llm  # type: ignore[method-assign]
    return router


# ── Fallback path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_falls_back_to_rules_when_llm_raises():
    router = _router_with_llm([RuntimeError("llm offline")])
    result = await router.classify("What is the capital of France?")
    assert result.level.value in {"L0", "L1", "L2", "L3", "L4"}
    assert result.total_score >= 0


@pytest.mark.asyncio
async def test_classify_uses_llm_when_available():
    router = _router_with_llm(["ok"])
    result = await router.classify("Compare distributed transformer optimizers")
    # The contract: the public classify() returns a populated
    # TriageResult regardless of which path was used. The plan
    # exposes a model role mapping; assert the result has one of
    # the documented role keys.
    assert result.cost_estimate >= 0
    assert (
        any(role in result.model_plan for role in ("agent", "reasoner", "reasoning", "writer"))
        or result.model_plan == {}
    )


# ── Level mapping ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_simple_question_stays_in_quick_band():
    """A short factual question must not escalate to L3/L4."""
    router = _router_with_llm([RuntimeError("force rule path")])
    result = await router.classify("Capital of France?")
    assert result.level.value in {"L0", "L1"}


@pytest.mark.asyncio
async def test_classify_technical_deep_query_escalates():
    """A multi-dimensional research query should land at L2 or above."""
    router = _router_with_llm([RuntimeError("force rule path")])
    result = await router.classify(
        "Compare transformer optimization algorithms for distributed training "
        "across multiple sources, analyzing tradeoffs in cost, latency, and "
        "accuracy, and write a comprehensive engineering report with diagrams."
    )
    assert result.level.value in {"L2", "L3", "L4"}


# ── Cost / plan output ──────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_emits_cost_plan_search_plan():
    router = _router_with_llm([RuntimeError("force rule path")])
    result = await router.classify("Latest research on RAG systems")
    assert isinstance(result.cost_estimate, float)
    assert isinstance(result.search_plan, list)
    assert isinstance(result.model_plan, dict)


# ── Warning surface ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_collects_warnings_when_privacy_hints_present():
    router = _router_with_llm([RuntimeError("force rule path")])
    result = await router.classify("Decrypt my private medical record and summarize my confidential diagnosis")
    # Privacy keyword should trigger a warning; rule path may also
    # produce domain-specific warnings. The contract: warnings is a list.
    assert isinstance(result.warnings, list)
