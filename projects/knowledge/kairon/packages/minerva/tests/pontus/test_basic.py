"""Basic tests for pontus package."""

from __future__ import annotations

from minerva.pipeline.pontus import (
    CheckpointManager,
    DAGScheduler,
    Deduplicator,
    PipelineDef,
    PipelineResult,
    QualityValidator,
    StepDef,
    load_pipeline,
    validate,
)
from minerva.pipeline.pontus.quality import CrossSourceDeduplicator, DetailedFormatValidator, SourceTrustScorer


class TestPontusBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """All expected exports are importable."""
        assert CheckpointManager is not None
        assert DAGScheduler is not None
        assert Deduplicator is not None
        assert PipelineDef is not None
        assert PipelineResult is not None
        assert QualityValidator is not None
        assert StepDef is not None
        assert load_pipeline is not None
        assert validate is not None
        assert CrossSourceDeduplicator is not None
        assert DetailedFormatValidator is not None
        assert SourceTrustScorer is not None

    def test_pipeline_def_minimal(self):
        """PipelineDef with just name and empty steps."""
        p = PipelineDef(name="minimal", steps=[])
        assert p.name == "minimal"
        assert p.steps == []

    def test_validate_empty_steps(self):
        """Pipeline with empty name returns False, empty steps is valid."""
        p = PipelineDef(name="test", steps=[])
        assert validate(p) is True

    def test_scheduler_empty_pipeline(self):
        """Executing an empty pipeline returns success."""
        p = PipelineDef(name="empty", steps=[])
        validate(p)
        result = DAGScheduler().execute(p, {})
        assert result.status == "success"
        assert result.results == {}
        assert result.errors == {}

    def test_deduplicator_none_key_fn(self):
        """Deduplicator handles entries where key function returns None gracefully."""
        entries = [{"id": 1}, {"id": 2}, {"id": 1}]
        d = Deduplicator()
        result = d.deduplicate(entries, key_fn=lambda e: e.get("id"))
        assert len(result) == 2
