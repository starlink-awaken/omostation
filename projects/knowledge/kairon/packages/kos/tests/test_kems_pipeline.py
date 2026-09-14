"""Tests for source admission and fail-closed pipeline status."""

from kos.kems import PipelineRun, SourceManifest, StepRun


def source(**overrides):
    values = {
        "source_id": "source-1",
        "source_type": "oa",
        "source_uri": "vault://official/one",
        "content_sha256": "a" * 64,
        "domain": "official_work",
        "sensitivity": "internal",
        "redaction_status": "verified",
        "connector_version": "oa-v1",
        "captured_at": "2026-07-31T00:00:00Z",
    }
    values.update(overrides)
    return SourceManifest(**values)  # type: ignore[reportArgumentType]


def test_source_admission_blocks_personal_and_unredacted_data():
    assert source().admitted_to_work_graph
    assert not source(domain="personal", sensitivity="personal").admitted_to_work_graph
    assert not source(redaction_status="pending").admitted_to_work_graph
    assert not source(sensitivity="credential").admitted_to_work_graph


def test_pipeline_run_fails_when_required_step_is_missing_or_failed():
    run = PipelineRun("run-1", "private-ingest", ("source-1",))
    run.start()
    run.record_step(StepRun("fetch", "succeeded"))
    run.finish(required_steps=("fetch", "normalize", "admit"))
    assert run.status == "failed"
    assert run.error_count > 0

    run2 = PipelineRun("run-2", "private-ingest", ("source-1",))
    run2.start()
    for step_id in ("fetch", "normalize", "admit"):
        run2.record_step(StepRun(step_id, "succeeded"))
    run2.finish(required_steps=("fetch", "normalize", "admit"))
    assert run2.status == "succeeded"
