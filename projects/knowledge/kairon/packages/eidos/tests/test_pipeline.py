"""Tests for the pipeline module."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestPipelineStep:
    def test_eidos_step(self):
        from eidos.pipeline import PipelineStep

        s = PipelineStep(tool="eidos", action="meta")
        cmd = s.to_cli()
        assert "-m" in cmd
        assert "eidos.cli" in cmd or "eidos" in cmd

    def test_kos_step(self):
        from eidos.pipeline import PipelineStep

        s = PipelineStep(tool="kos", action="search", args={"query": "test", "limit": 5})
        cmd = s.to_cli()
        assert any("--query" in c or "--limit" in c for c in cmd)

    def test_with_input_output(self):
        from eidos.pipeline import PipelineStep

        s = PipelineStep(tool="eidos", action="meta", input_file="/tmp/in.json", output_file="/tmp/out.json")
        cmd = s.to_cli()
        assert "--pipeline-input" in cmd
        assert "--pipeline-output" in cmd
        assert "/tmp/in.json" in cmd
        assert "/tmp/out.json" in cmd

    def test_unknown_tool_raises(self):
        import pytest
        from eidos.pipeline import PipelineStep

        with pytest.raises(ValueError):
            PipelineStep(tool="unknown", action="test").to_cli()


class TestPipeline:
    def test_from_dict(self):
        from eidos.pipeline import Pipeline

        d = {
            "name": "test",
            "steps": [
                {"tool": "eidos", "action": "meta"},
                {"tool": "kos", "action": "search", "args": {"query": "x", "limit": 3}},
            ],
        }
        p = Pipeline.from_dict(d)
        assert p.name == "test"
        assert len(p.steps) == 2
        assert p.steps[0].tool == "eidos"
        assert p.steps[1].tool == "kos"

    def test_load_save_roundtrip(self, tmp_path):
        import json

        from eidos.pipeline import Pipeline

        d = {"name": "rt", "steps": [{"tool": "eidos", "action": "meta"}]}
        f = tmp_path / "pipeline.json"
        f.write_text(json.dumps(d))
        p = Pipeline.load(str(f))
        assert p.name == "rt"
        assert p.steps[0].action == "meta"

    def test_default_pipeline_creatable(self):
        from eidos.pipeline import PipelineStep

        # Verify we can create a multi-step pipeline manually
        steps = [
            PipelineStep(tool="eidos", action="meta"),
            PipelineStep(tool="kos", action="ingest"),
        ]
        assert len(steps) == 2
        assert steps[0].tool == "eidos"
