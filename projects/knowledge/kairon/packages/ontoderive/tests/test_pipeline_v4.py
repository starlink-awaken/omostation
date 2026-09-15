"""Tests for FormalPipeline — 四阶段形式化推理管线"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.reasoners.pipeline_v4 import FormalPipeline


def test_pipeline_creates():
    p = FormalPipeline()
    assert p is not None
    assert hasattr(p, "run")


def test_pipeline_run_empty():
    p = FormalPipeline()
    result = p.run("")
    assert isinstance(result, dict)
    assert "report" in result
    assert len(result["report"]) > 0


def test_pipeline_run_with_text():
    p = FormalPipeline()
    result = p.run("测试文本，包含一些分析内容")
    assert "report" in result
    assert len(result["report"]) > 0
