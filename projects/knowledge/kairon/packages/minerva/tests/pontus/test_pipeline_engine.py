"""Tests for the pontus knowledge pipeline engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
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

# ---------------------------------------------------------------------------
# DSL tests
# ---------------------------------------------------------------------------


class TestDSL:
    def test_load_pipeline_from_yaml(self):
        yaml_content = """\
name: test-pipeline
steps:
  - id: fetch
    action: http_fetch
    params:
      url: https://example.com
  - id: parse
    action: parse_html
    depends_on: [fetch]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            tmp = f.name

        try:
            p = load_pipeline(tmp)
            assert p.name == "test-pipeline"
            assert len(p.steps) == 2
            assert p.steps[0].id == "fetch"
            assert p.steps[0].action == "http_fetch"
            assert p.steps[0].params == {"url": "https://example.com"}
            assert p.steps[1].depends_on == ["fetch"]
        finally:
            Path(tmp).unlink()

    def test_load_pipeline_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_pipeline("/nonexistent/path.yaml")

    def test_load_pipeline_missing_id(self):
        yaml_content = """\
name: bad
steps:
  - action: no_id
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            tmp = f.name
        try:
            with pytest.raises(ValueError, match="missing required 'id'"):
                load_pipeline(tmp)
        finally:
            Path(tmp).unlink()

    def test_validate_ok(self):
        p = PipelineDef(
            name="ok",
            steps=[
                StepDef(id="a", action="fetch"),
                StepDef(id="b", action="transform", depends_on=["a"]),
                StepDef(id="c", action="save", depends_on=["b"]),
            ],
        )
        assert validate(p) is True

    def test_validate_duplicate_ids(self):
        p = PipelineDef(
            name="dup",
            steps=[
                StepDef(id="a", action="fetch"),
                StepDef(id="a", action="fetch"),
            ],
        )
        with pytest.raises(ValueError, match="Duplicate step IDs"):
            validate(p)

    def test_validate_missing_dependency(self):
        p = PipelineDef(
            name="missing-dep",
            steps=[
                StepDef(id="a", action="fetch", depends_on=["nope"]),
            ],
        )
        with pytest.raises(ValueError, match="unknown step"):
            validate(p)

    def test_validate_cycle(self):
        p = PipelineDef(
            name="cycle",
            steps=[
                StepDef(id="a", action="x", depends_on=["b"]),
                StepDef(id="b", action="y", depends_on=["a"]),
            ],
        )
        with pytest.raises(ValueError, match="Circular dependency"):
            validate(p)

    def test_validate_empty_name(self):
        p = PipelineDef(name="", steps=[])
        assert validate(p) is False


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------


class TestScheduler:
    def test_linear_pipeline(self):
        p = PipelineDef(
            name="linear",
            steps=[
                StepDef(id="s1", action="echo"),
                StepDef(id="s2", action="echo", depends_on=["s1"]),
                StepDef(id="s3", action="echo", depends_on=["s2"]),
            ],
        )
        validate(p)

        async def echo(step: StepDef, results: dict):
            return f"done:{step.id}"

        ctx = {"echo": echo}
        result = DAGScheduler().execute(p, ctx)
        assert result.status == "success"
        assert result.results == {"s1": "done:s1", "s2": "done:s2", "s3": "done:s3"}
        assert result.errors == {}

    def test_parallel_execution(self):
        p = PipelineDef(
            name="parallel",
            steps=[
                StepDef(id="a", action="slow"),
                StepDef(id="b", action="slow"),
                StepDef(id="c", action="slow"),
                StepDef(id="merge", action="merge", depends_on=["a", "b", "c"]),
            ],
        )
        validate(p)

        call_order = []

        async def slow(step: StepDef, results: dict):
            call_order.append(step.id)
            return step.id

        async def merge(step: StepDef, results: dict):
            assert "a" in results
            assert "b" in results
            assert "c" in results
            return "merged"

        ctx = {"slow": slow, "merge": merge}
        result = DAGScheduler().execute(p, ctx)
        assert result.status == "success"
        assert result.results["merge"] == "merged"

    def test_missing_handler(self):
        p = PipelineDef(
            name="missing",
            steps=[StepDef(id="s1", action="unknown")],
        )
        validate(p)
        result = DAGScheduler().execute(p, {})
        assert result.status == "failed"
        assert "s1" in result.errors

    def test_step_exception_partial(self):
        p = PipelineDef(
            name="partial-fail",
            steps=[
                StepDef(id="ok", action="ok"),
                StepDef(id="fail", action="fail"),
            ],
        )
        validate(p)

        async def ok_step(step, results):
            return "ok"

        async def fail_step(step, results):
            raise RuntimeError("boom")

        ctx = {"ok": ok_step, "fail": fail_step}
        result = DAGScheduler().execute(p, ctx)
        assert result.status == "partial"
        assert result.results == {"ok": "ok"}
        assert "fail" in result.errors

    def test_pipeline_result_dataclass(self):
        pr = PipelineResult(status="success", results={"k": "v"}, errors={})
        assert pr.status == "success"
        assert pr.results["k"] == "v"


# ---------------------------------------------------------------------------
# Checkpoint tests
# ---------------------------------------------------------------------------


class TestCheckpoint:
    def test_save_and_resume(self):
        mgr = CheckpointManager(db_path=":memory:")
        mgr.save("run-1", {"step": "fetch", "count": 5})
        state = mgr.resume("run-1")
        assert state == {"step": "fetch", "count": 5}

    def test_resume_missing(self):
        mgr = CheckpointManager(db_path=":memory:")
        assert mgr.resume("nonexistent") is None

    def test_overwrite_checkpoint(self):
        mgr = CheckpointManager(db_path=":memory:")
        mgr.save("run-2", {"step": "a"})
        mgr.save("run-2", {"step": "b"})
        assert mgr.resume("run-2") == {"step": "b"}

    def test_delete_checkpoint(self):
        mgr = CheckpointManager(db_path=":memory:")
        mgr.save("run-3", {"x": 1})
        assert mgr.delete("run-3") is True
        assert mgr.resume("run-3") is None
        assert mgr.delete("run-3") is False

    def test_list_runs(self):
        mgr = CheckpointManager(db_path=":memory:")
        mgr.save("run-a", {"n": 1})
        mgr.save("run-b", {"n": 2})
        runs = mgr.list_runs()
        assert len(runs) == 2
        assert {r["run_id"] for r in runs} == {"run-a", "run-b"}


# ---------------------------------------------------------------------------
# Quality tests
# ---------------------------------------------------------------------------


class TestQualityValidator:
    def test_valid_data(self):
        schema = {"id": "int", "name": "str", "active": "bool"}
        v = QualityValidator()
        assert v.validate_format({"id": 1, "name": "Alice", "active": True}, schema) is True

    def test_missing_field(self):
        schema = {"id": "int", "name": "str"}
        v = QualityValidator()
        assert v.validate_format({"id": 1}, schema) is False

    def test_wrong_type(self):
        schema = {"id": "int"}
        v = QualityValidator()
        assert v.validate_format({"id": "not-an-int"}, schema) is False

    def test_extra_fields_ignored(self):
        schema = {"id": "int"}
        v = QualityValidator()
        assert v.validate_format({"id": 5, "extra": "stuff"}, schema) is True

    def test_callable_predicate(self):
        schema = {"score": lambda x: 0 <= x <= 100}
        v = QualityValidator()
        assert v.validate_format({"score": 85}, schema) is True
        assert v.validate_format({"score": 150}, schema) is False

    def test_union_type(self):
        schema = {"val": (int, float)}
        v = QualityValidator()
        assert v.validate_format({"val": 3}, schema) is True
        assert v.validate_format({"val": 3.14}, schema) is True
        assert v.validate_format({"val": "str"}, schema) is False

    def test_predicate_raises(self):
        def bad_pred(val):
            raise RuntimeError("oops")

        schema = {"x": bad_pred}
        v = QualityValidator()
        assert v.validate_format({"x": 1}, schema) is False

    def test_non_dict_data(self):
        v = QualityValidator()
        assert v.validate_format("not-a-dict", {"x": "int"}) is False  # type: ignore[reportArgumentType]
        assert v.validate_format({"x": 1}, "not-a-schema") is False  # type: ignore[reportArgumentType]


class TestDeduplicator:
    def test_deduplicate_by_id(self):
        entries = [
            {"id": 1, "val": "a"},
            {"id": 2, "val": "b"},
            {"id": 1, "val": "c"},
            {"id": 3, "val": "d"},
            {"id": 2, "val": "e"},
        ]
        d = Deduplicator()
        result = d.deduplicate(entries, key_fn=lambda e: e["id"])
        assert len(result) == 3
        assert result == [
            {"id": 1, "val": "a"},
            {"id": 2, "val": "b"},
            {"id": 3, "val": "d"},
        ]

    def test_empty_list(self):
        d = Deduplicator()
        assert d.deduplicate([], key_fn=lambda x: x) == []

    def test_custom_key(self):
        entries = ["Apple", "banana", "APPLE", "Cherry"]
        d = Deduplicator()
        result = d.deduplicate(entries, key_fn=lambda s: s.lower())
        assert result == ["Apple", "banana", "Cherry"]
