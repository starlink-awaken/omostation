"""Tests for the Eidos visualization module."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestRenderClassDiagram:
    def test_basic_class(self):
        from eidos.viz import render

        result = render("class", class_name="TestObj", fields=[{"name": "id", "type": "str"}])
        assert "classDiagram" in result
        assert "TestObj" in result
        assert "+str id" in result

    def test_multiple_fields(self):
        from eidos.viz import render

        result = render(
            "class", class_name="Person", fields=[{"name": "name", "type": "str"}, {"name": "age", "type": "int"}]
        )
        assert "+str name" in result
        assert "+int age" in result


class TestRenderGraph:
    def test_basic_graph(self):
        from eidos.viz import render

        result = render("graph", nodes=[{"id": "n1", "label": "Node1"}], edges=[])
        assert "graph TD" in result
        assert "Node1" in result

    def test_with_edges(self):
        from eidos.viz import render

        result = render(
            "graph",
            nodes=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            edges=[{"source": "a", "target": "b", "label": "link"}],
        )
        assert "a -->|link| b" in result


class TestRenderStateDiagram:
    def test_basic_state(self):
        from eidos.viz import render

        result = render(
            "state",
            states=["draft", "review", "published"],
            transitions=[{"from": "draft", "to": "review", "trigger": "submit"}],
            initial="draft",
        )
        assert "stateDiagram-v2" in result
        assert "[*] --> draft" in result
        assert "draft --> review : submit" in result


class TestRenderPipeline:
    def test_basic_pipeline(self):
        from eidos.viz import render

        result = render(
            "pipeline", steps=[{"name": "model", "description": "建模"}, {"name": "viz", "description": "可视化"}]
        )
        assert "flowchart LR" in result
        assert "S0 --> S1" in result


class TestInvalidVizType:
    def test_raises_on_unknown(self):
        import pytest
        from eidos.viz import render

        with pytest.raises(ValueError):
            render("unknown")
