"""Basic E2E integration tests — verify core system wiring."""

import pytest

pytest.importorskip("pontus", reason="requires pontus package (not yet in kairon)")


class TestCoreImports:
    """Verify all core packages can be imported without errors."""


class TestPontusPipeline:
    """Test pontus pipeline: DSL → quality → checkpoint."""

    def test_quality_validator(self):
        from pontus.quality import QualityValidator  # type: ignore[reportMissingImports]

        v = QualityValidator()
        assert v.validate_format({"id": 1, "name": "test"}, {"id": "int", "name": "str"})
        assert not v.validate_format({"id": "not_int"}, {"id": "int"})

    def test_deduplicator(self):
        from pontus.quality import Deduplicator  # type: ignore[reportMissingImports]

        d = Deduplicator()
        entries = [{"id": 1}, {"id": 2}, {"id": 1}]
        result = d.deduplicate(entries, key_fn=lambda e: e["id"])
        assert len(result) == 2

    def test_checkpoint(self):
        import os
        import tempfile

        from pontus.checkpoint import CheckpointManager  # type: ignore[reportMissingImports]

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            cm = CheckpointManager(db_path)
            cm.save("run1", {"status": "ok"})
            state = cm.resume("run1")
            assert state == {"status": "ok"}
            runs = cm.list_runs()
            assert len(runs) >= 1
        finally:
            os.unlink(db_path)


class TestAgentRuntime:
    """Test agent-runtime basic types and creation."""

    def test_task_status(self):
        from agent_runtime.types import TaskStatus  # type: ignore[import-not-found]

        assert TaskStatus.PENDING is not None
        assert TaskStatus.RUNNING is not None

    def test_task_def(self):
        from agent_runtime.types import TaskDef  # type: ignore[import-not-found]

        t = TaskDef(id="test-1", action="test", agent_id="worker-1")
        assert t.id == "test-1"
