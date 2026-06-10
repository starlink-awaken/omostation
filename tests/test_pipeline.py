"""Tests for Pipeline — orchestration engine."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from agora.core.registry import ServiceRegistry
from agora.core.router import Router
from agora.pipeline import Pipeline


def _new_pipeline():
    r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
    return Pipeline(r, Router(r))


class TestPipelineBuiltins:
    def test_builtin_pipelines_loaded(self):
        pl = _new_pipeline()
        names = pl.list_pipelines()
        assert "match-derive" in names
        assert "research-derive" in names
        assert "derive-check" in names
        assert "full-pipeline" in names

    def test_get_pipeline_definition(self):
        pl = _new_pipeline()
        steps = pl.get_pipeline("derive-check")
        assert steps is not None
        assert len(steps) == 2
        assert steps[0]["tool"] == "ontoderive.derive"
        assert steps[1]["tool"] == "ontoderive.check"

    def test_pipeline_not_found(self):
        pl = _new_pipeline()
        assert pl.get_pipeline("nonexistent") is None


class TestPipelineCustom:
    def test_define_custom_pipeline(self):
        pl = _new_pipeline()
        pl.define(
            "my-pipe",
            [
                {"tool": "toolforge.match", "args": {"goal": "{{goal}}"}},
            ],
        )
        assert "my-pipe" in pl.list_pipelines()
        assert len(pl.get_pipeline("my-pipe")) == 1

    def test_load_save_definition(self):
        pl = _new_pipeline()
        pl.define("save-test", [{"tool": "test.tool"}])
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            pl.save_definition("save-test", f.name)
            loaded_name = pl.load_definition(f.name)
        assert loaded_name == "save-test"


class TestPipelineRender:
    def test_render_template_variables(self):
        pl = _new_pipeline()
        result = pl._render_args(
            {"goal": "{{goal}}", "context": "{{context}}", "fixed": "val"},
            {"goal": "分析市场", "context": "竞争"},
            {},
        )
        assert result["goal"] == "分析市场"
        assert result["context"] == "竞争"
        assert result["fixed"] == "val"

    def test_render_no_template(self):
        pl = _new_pipeline()
        result = pl._render_args({"x": "y"}, {}, {})
        assert result["x"] == "y"


class TestPipelineRun:
    def test_run_unknown_pipeline(self):
        pl = _new_pipeline()
        result = asyncio.run(pl.run("unknown", {}))
        assert "error" in str(result).lower()

    def test_run_stream_unknown(self):
        pl = _new_pipeline()

        async def _test():
            results = []
            async for step in pl.run_stream("unknown", {}):
                results.append(step)
            return results

        results = asyncio.run(_test())
        assert results[0]["status"] == "error"


class TestPipelineRunAsync:
    """Async pipeline execution tests with mocked router."""

    @pytest.mark.asyncio
    async def test_run_stream_with_mock(self, monkeypatch):
        """run_stream yields steps in order."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        async def mock_route(tool, args, **kwargs):
            return {"status": "ok", "result": f"done_{tool}"}

        monkeypatch.setattr(pl.router, "route", mock_route)

        results = []
        async for step in pl.run_stream("derive-check", {"project": "."}):
            results.append(step)
        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "ok"
        assert "ontoderive.derive" in results[0]["tool"]
        assert "ontoderive.check" in results[1]["tool"]

    @pytest.mark.asyncio
    async def test_run_with_mock(self, monkeypatch):
        """run returns aggregated results."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        async def mock_route(tool, args, **kwargs):
            return {"status": "ok", "result": f"done_{tool}"}

        monkeypatch.setattr(pl.router, "route", mock_route)

        result = await pl.run("derive-check", {"project": "."})
        assert result["pipeline"] == "derive-check"
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_run_parallel_with_mock(self, monkeypatch):
        """run_parallel executes steps grouped by dependency level."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        async def mock_route(tool, args, **kwargs):
            return {"status": "ok", "result": f"done_{tool}"}

        monkeypatch.setattr(pl.router, "route", mock_route)

        result = await pl.run_parallel("full-pipeline", {"goal": "test", "context": "test", "project": "."})
        assert result["pipeline"] == "full-pipeline"
        assert len(result["results"]) == 4

    @pytest.mark.asyncio
    async def test_run_stream_not_found(self):
        """run_stream returns error for unknown pipeline."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        results = []
        async for step in pl.run_stream("nonexistent", {}):
            results.append(step)
        assert len(results) == 1
        assert results[0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_parallel_not_found(self):
        """run_parallel returns error for unknown pipeline."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        result = await pl.run_parallel("nonexistent", {})
        assert "error" in str(result)

    @pytest.mark.asyncio
    async def test_run_stream_step_error(self, monkeypatch):
        """run_stream handles router error gracefully."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        async def mock_route(tool, args, **kwargs):
            raise RuntimeError("service unavailable")

        monkeypatch.setattr(pl.router, "route", mock_route)

        results = []
        async for step in pl.run_stream("derive-check", {"project": "."}):
            results.append(step)
        assert results[0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_parallel_deadlock(self, monkeypatch):
        """run_parallel handles deadlocked dependencies."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))

        # A pipeline with circular/unresolvable deps
        pl.define(
            "deadlock",
            [
                {"tool": "step1", "depends_on": ["step2_output"], "output_as": "step1_output"},
                {"tool": "step2", "depends_on": ["step1_output"], "output_as": "step2_output"},
            ],
        )

        async def mock_route(tool, args, **kwargs):
            return {"status": "ok"}

        monkeypatch.setattr(pl.router, "route", mock_route)

        result = await pl.run_parallel("deadlock", {})
        assert "Unresolved dependency" in str(result)


class TestPipelineSaveLoad:
    """Pipeline definition save/load tests."""

    def test_save_definition_not_found(self):
        """save_definition raises ValueError for unknown pipeline."""
        import tempfile

        import pytest
        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))
        with pytest.raises(ValueError, match="Pipeline not found"):
            pl.save_definition("nonexistent", "/tmp/test-pipe.json")

    def test_render_args_full(self):
        """_render_args replaces all template variables."""
        import tempfile

        from agora.pipeline import Pipeline

        r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
        pl = Pipeline(r, Router(r))
        result = pl._render_args(
            {"query": "{{goal}} about {{context}}", "fixed": "val"},
            {"goal": "AI", "context": "ethics"},
            {},
        )
        assert result["query"] == "AI about ethics"
        assert result["fixed"] == "val"
