"""Test Agora Eidos pipeline routing."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_pipeline_route_knowledge_base():
    route = importlib.import_module("agora.eidos_pipeline").route
    cmd = route("knowledge-base")
    assert isinstance(cmd, list)
    assert "eidos" in cmd or "pipeline" in cmd


def test_pipeline_route_reasoning():
    route = importlib.import_module("agora.eidos_pipeline").route
    cmd = route("reasoning")
    assert isinstance(cmd, list)


def test_pipeline_route_unknown():
    import pytest

    route = importlib.import_module("agora.eidos_pipeline").route
    with pytest.raises(ValueError):
        route("nonexistent")
