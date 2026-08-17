"""End-to-end tests for the Minerva tiered research pipeline.

Drives the public `Pipeline.run` API against mock LLM, search, and
knowledge-store collaborators so the cross-stage glue (timing, retry,
QualityGate, KOS save, vault sink) is observable from one place
rather than via per-stage unit tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from minerva.pipeline.engine import (
    IPipelineStage,
    Pipeline,
    QualityGateError,
    ResearchContext,
)
from minerva.triage.router import ResearchLevel, TriageResult


def _triage(level: ResearchLevel = ResearchLevel.L1) -> TriageResult:
    return TriageResult(
        level=level,
        scores={
            "domain_complexity": 60,
            "depth_required": 60,
            "multi_source": 60,
            "timeliness": 40,
            "privacy_sensitivity": 0,
        },
        cost_estimate=0.05,
        model_plan={"reasoner": "mock", "long_context": "mock"},
        search_plan=["ddg", "scholar"],
    )


def _stage(name: str, side_effect=None, raises: Exception | None = None) -> IPipelineStage:
    """Build a one-shot pipeline stage with a deterministic execute."""
    stage: IPipelineStage = MagicMock(spec=IPipelineStage)
    stage.name = name

    async def _execute(ctx: ResearchContext) -> ResearchContext:
        if raises is not None:
            raise raises
        if side_effect is not None:
            side_effect(ctx)
        return ctx

    stage.execute = _execute  # type: ignore[method-assign]
    return stage


# ── Basic flow ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_runs_all_stages_in_order():
    seen: list[str] = []
    pipeline = Pipeline(
        {
            ResearchLevel.L1: [
                _stage("a", side_effect=lambda c: seen.append("a")),
                _stage("b", side_effect=lambda c: seen.append("b")),
                _stage("c", side_effect=lambda c: seen.append("c")),
            ]
        }
    )
    ctx = await pipeline.run("What is X?", ResearchLevel.L1, _triage(ResearchLevel.L1))
    assert seen == ["a", "b", "c"]
    assert ctx.completed_at is not None
    assert ctx.stage_timings == {
        "a": pytest.approx(0.0, abs=0.1),
        "b": pytest.approx(0.0, abs=0.1),
        "c": pytest.approx(0.0, abs=0.1),
    }


@pytest.mark.asyncio
async def test_pipeline_unknown_level_runs_no_stages():
    pipeline = Pipeline({ResearchLevel.L0: [_stage("only-l0")]})
    ctx = await pipeline.run("Anything", ResearchLevel.L4, _triage(ResearchLevel.L4))
    assert ctx.stage_timings == {}
    assert ctx.completed_at is not None


# ── Quality gate retries ──────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_retries_after_quality_gate_failure():
    calls: list[str] = []
    pipeline = Pipeline(
        {
            ResearchLevel.L2: [
                _stage(
                    "deep_read",
                    side_effect=lambda c: calls.append("deep_read"),
                    raises=QualityGateError("nope"),
                ),
                _stage("verify", side_effect=lambda c: calls.append("verify")),
            ]
        }
    )
    # First deep_read raises → pipeline rewinds 2 stages, retries
    # deep_read once, then continues to verify. With the default
    # max_retries=2, the call must succeed on the second attempt.
    fail_once = [True]

    def _hook(ctx: ResearchContext) -> None:
        if fail_once[0]:
            fail_once[0] = False
            raise QualityGateError("nope")
        calls.append("deep_read_retry")

    retry_stage = _stage("deep_read", side_effect=_hook)
    pipeline = Pipeline(
        {ResearchLevel.L2: [retry_stage, _stage("verify", side_effect=lambda c: calls.append("verify"))]}
    )
    await pipeline.run("hi", ResearchLevel.L2, _triage(ResearchLevel.L2))
    assert "verify" in calls
    assert "deep_read_retry" in calls


@pytest.mark.asyncio
async def test_pipeline_proceeds_with_degraded_quality_after_max_retries():
    """When QualityGateError persists beyond max_retries, the pipeline
    should still set completed_at and finish — it logs and proceeds."""
    fail = _stage("stage", raises=QualityGateError("always fails"))
    pipeline = Pipeline({ResearchLevel.L1: [fail, _stage("never_reached")]})
    ctx = await pipeline.run("hi", ResearchLevel.L1, _triage(ResearchLevel.L1))
    assert ctx.completed_at is not None
    assert "stage" in ctx.stage_timings


# ── Context invariants ───────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_preserves_query_level_triage_in_context():
    captured: dict = {}

    def _capture(ctx: ResearchContext) -> None:
        captured["query"] = ctx.query
        captured["level"] = ctx.level
        captured["triage"] = ctx.triage

    pipeline = Pipeline({ResearchLevel.L1: [_stage("capture", side_effect=_capture)]})
    triage = _triage(ResearchLevel.L1)
    await pipeline.run("captured query", ResearchLevel.L1, triage)
    assert captured == {"query": "captured query", "level": ResearchLevel.L1, "triage": triage}


@pytest.mark.asyncio
async def test_pipeline_records_stage_timing_even_when_stage_no_ops():
    pipeline = Pipeline({ResearchLevel.L0: [_stage("noop"), _stage("noop2")]})
    ctx = await pipeline.run("hi", ResearchLevel.L0, _triage(ResearchLevel.L0))
    assert "noop" in ctx.stage_timings
    assert "noop2" in ctx.stage_timings
    assert all(duration >= 0 for duration in ctx.stage_timings.values())


# ── Stage immutability vs context mutability ────────────────


@pytest.mark.asyncio
async def test_pipeline_stages_share_mutable_context():
    """Stages communicate by mutating the shared context, not by
    returning new values. This invariant test guards against a
    refactor that would break the contract by making stages pure."""
    seen: list[ResearchContext] = []

    def _record(ctx: ResearchContext) -> None:
        ctx.metadata["touched_by"] = ctx.metadata.get("touched_by", []) + ["stage"]
        seen.append(ctx)

    pipeline = Pipeline(
        {ResearchLevel.L1: [_stage("first", side_effect=_record), _stage("second", side_effect=_record)]}
    )
    ctx = await pipeline.run("hi", ResearchLevel.L1, _triage(ResearchLevel.L1))
    # Both stages saw the same context object reference.
    assert seen[0] is seen[1] is ctx
    assert ctx.metadata["touched_by"] == ["stage", "stage"]


# ── Failure handling ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_stops_on_unexpected_exception():
    bad = _stage("boom", raises=RuntimeError("kaboom"))
    pipeline = Pipeline({ResearchLevel.L1: [_stage("a"), bad, _stage("never")]})
    with pytest.raises(RuntimeError, match="kaboom"):
        await pipeline.run("hi", ResearchLevel.L1, _triage(ResearchLevel.L1))


# ── KOS save / vault sink sidecars ──────────────────────────


@pytest.mark.asyncio
async def test_pipeline_with_kos_save_appends_save_stage():
    """When a downstream caller wires KOSSaveStage in front of the
    pipeline factory, the save stage should fire alongside the
    regular stages. We assert this by injecting a stage that records
    metadata on the context so the integration boundary is observable.
    """
    seen: list[str] = []

    def _record(ctx: ResearchContext) -> None:
        ctx.metadata.setdefault("stages_touched", []).append("kos_save")
        seen.append("kos_save")

    save_stage = _stage("KOSSaveStage", side_effect=_record)
    pipeline = Pipeline({ResearchLevel.L1: [_stage("search"), _stage("analyze"), save_stage]})
    ctx = await pipeline.run("hi", ResearchLevel.L1, _triage(ResearchLevel.L1))
    assert seen == ["kos_save"]
    assert ctx.metadata["stages_touched"] == ["kos_save"]


@pytest.mark.asyncio
async def test_pipeline_vault_sink_emits_publish_metadata():
    """Mirrors the L4 vault sink: a stage that publishes the report
    path into the context so downstream search engines can pick it up.
    """

    def _publish(ctx: ResearchContext) -> None:
        ctx.report = "# mock report body"
        ctx.report_path = "/vault/notes/minerva-mock.md"
        ctx.metadata["vault_published"] = True

    publish_stage = _stage("VaultSinkStage", side_effect=_publish)
    pipeline = Pipeline({ResearchLevel.L4: [publish_stage]})
    ctx = await pipeline.run("hi", ResearchLevel.L4, _triage(ResearchLevel.L4))
    assert ctx.report == "# mock report body"
    assert ctx.report_path == "/vault/notes/minerva-mock.md"
    assert ctx.metadata["vault_published"] is True
