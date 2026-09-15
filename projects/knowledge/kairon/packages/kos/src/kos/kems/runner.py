"""Fail-closed pipeline executor backed by the KEMS run store."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .pipeline import PipelineRun, SourceManifest, StepRun
from .run_store import RunStore

StepHandler = Callable[[tuple[SourceManifest, ...]], bytes]


@dataclass(frozen=True)
class PipelineStep:
    step_id: str
    handler: StepHandler


class PipelineExecutor:
    """Execute registered steps with persisted checkpoints and fail-closed status."""

    def __init__(self, store: RunStore, pipeline_id: str, steps: Iterable[PipelineStep]) -> None:
        self.store = store
        self.pipeline_id = pipeline_id
        self.steps = tuple(steps)
        if not self.steps or len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("a pipeline requires unique, non-empty steps")

    def run(self, run_id: str, sources: Iterable[SourceManifest]) -> PipelineRun:
        source_tuple = tuple(sources)
        if not source_tuple:
            raise ValueError("pipeline runs require at least one source")
        for source in source_tuple:
            self.store.register_source(source)

        run = PipelineRun(run_id, self.pipeline_id, tuple(source.source_id for source in source_tuple))
        run.start()
        self.store.create_run(run)
        for step in self.steps:
            checkpoint = StepRun(step.step_id, "running")
            run.record_step(checkpoint)
            self.store.record_step(run.run_id, checkpoint)
            try:
                output = step.handler(source_tuple)
                if not isinstance(output, bytes):
                    raise TypeError("pipeline steps must return bytes")
                finished = StepRun(step.step_id, "succeeded", output_sha256=hashlib.sha256(output).hexdigest())
            except Exception as exc:
                finished = StepRun(step.step_id, "failed", error_code=type(exc).__name__)
                run.record_step(finished)
                run.finish(required_steps=tuple(item.step_id for item in self.steps))
                self.store.save_run(run)
                raise RuntimeError(f"KEMS pipeline step failed: {step.step_id}") from exc
            run.record_step(finished)
            self.store.record_step(run.run_id, finished)
        run.finish(required_steps=tuple(step.step_id for step in self.steps))
        self.store.save_run(run)
        return run
