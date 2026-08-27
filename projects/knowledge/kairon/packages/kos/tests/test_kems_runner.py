"""Tests for fail-closed, checkpointed pipeline execution."""

import hashlib

import pytest
from kos.kems import PipelineExecutor, PipelineStep, RunStore
from kos.kems.pipeline import SourceManifest

SOURCE = SourceManifest(
    "source-1",
    "oa",
    "vault://official/one",
    "a" * 64,
    "official_work",
    "internal",
    "verified",
    "oa-v1",
    "2026-07-31T00:00:00Z",
)


def test_executor_persists_step_output_hash_and_success(tmp_path):
    executor = PipelineExecutor(
        RunStore(tmp_path / "runs.sqlite"),
        "private-ingest",
        (PipelineStep("fetch", lambda sources: b"raw"), PipelineStep("normalize", lambda sources: b"normalized")),
    )
    run = executor.run("run-1", (SOURCE,))
    assert run.status == "succeeded"
    restored = RunStore(tmp_path / "runs.sqlite").get_run("run-1")
    assert restored is not None
    assert restored.steps[-1].output_sha256 == hashlib.sha256(b"normalized").hexdigest()


def test_executor_stops_and_persists_failure(tmp_path):
    called = []

    def fail(sources):
        called.append("fail")
        raise ValueError("bad source")

    def never(sources):
        called.append("never")
        return b"never"

    executor = PipelineExecutor(
        RunStore(tmp_path / "runs.sqlite"),
        "private-ingest",
        (PipelineStep("fetch", fail), PipelineStep("normalize", never)),
    )
    with pytest.raises(RuntimeError, match="fetch"):
        executor.run("run-2", (SOURCE,))
    assert called == ["fail"]
    restored = RunStore(tmp_path / "runs.sqlite").get_run("run-2")
    assert restored is not None
    assert restored.status == "failed"
    assert restored.steps[0].status == "failed"
