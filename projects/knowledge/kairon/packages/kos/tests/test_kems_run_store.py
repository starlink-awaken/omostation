"""Tests for durable source and pipeline checkpoints."""

import pytest
from kos.kems import PipelineRun, RunStore, SourceManifest, StepRun


def source(digest="a" * 64):
    return SourceManifest(
        "source-1",
        "oa",
        "vault://official/one",
        digest,
        "official_work",
        "internal",
        "verified",
        "oa-v1",
        "2026-07-31T00:00:00Z",
    )


def test_source_registration_is_idempotent_and_rejects_hash_drift(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    assert store.register_source(source()) is True
    assert store.register_source(source()) is False
    with pytest.raises(ValueError, match="changed content_sha256"):
        store.register_source(source("b" * 64))


def test_pipeline_steps_survive_process_restart(tmp_path):
    db = tmp_path / "runs.sqlite"
    store = RunStore(db)
    run = PipelineRun("run-1", "private-ingest", ("source-1",))
    run.start()
    run.record_step(StepRun("fetch", "succeeded", output_sha256="c" * 64))
    store.create_run(run)
    store.save_run(run)

    restored = RunStore(db).get_run("run-1")
    assert restored is not None
    assert restored.steps[0].output_sha256 == "c" * 64
    assert restored.status == "running"
