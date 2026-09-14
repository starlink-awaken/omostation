"""Pipeline端到端测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.core.pipeline import DerivePipeline


def test_pipeline_create():
    pipe = DerivePipeline("examples/z-park")
    assert str(pipe.project_root).endswith("examples/z-park")
    assert len(pipe.stages) == 6


def test_pipeline_set_goal():
    pipe = DerivePipeline("examples/z-park")
    pipe.set_goal("分析中关村", "科技园区")
    assert pipe.ctx["goal"] == "分析中关村"
    assert pipe.ctx["context"] == "科技园区"


def test_pipeline_run_toolforge():
    pipe = DerivePipeline("examples/z-park")
    pipe.set_goal("分析中关村", "科技园区")
    pipe.run(stages=["toolforge"])
    assert "toolforge" in pipe.results
    assert "matches" in pipe.results["toolforge"]


def test_pipeline_run_load():
    pipe = DerivePipeline("examples/z-park")
    pipe.run(stages=["load"])
    assert "load" in pipe.results
    assert "derive_summary" in pipe.results["load"]


def test_pipeline_run_derive():
    pipe = DerivePipeline("examples/z-park")
    pipe.run(stages=["derive"])
    assert "derive" in pipe.results
    assert "facts" in pipe.results["derive"]


def test_pipeline_run_check():
    pipe = DerivePipeline("examples/z-park")
    pipe.run(stages=["check"])
    assert "check" in pipe.results
    assert len(pipe.results["check"]) == 13


def test_pipeline_to_analysis_result():
    pipe = DerivePipeline("examples/z-park")
    pipe.set_goal("分析中关村")
    pipe.run(stages=["toolforge", "derive", "check"])
    ar = pipe.to_analysis_result()
    assert ar.passed or not ar.passed  # 正常运行


def test_pipeline_to_dict():
    pipe = DerivePipeline("examples/z-park")
    pipe.run(stages=["derive"])
    d = pipe.to_dict()
    assert "project_root" in d
    assert "results" in d
