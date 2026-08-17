"""
测试 foundation/protocols.py - 接口协议抽象类
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from ontoderive.foundation.protocols import (  # type: ignore[import-not-found]
    AnalysisResult,
    DeriveInterface,
    PipelineObservable,
    PipelineStage,
    ToolForgeInterface,
)


class TestDeriveInterface:
    """DeriveInterface - 推导引擎接口"""

    def test_cannot_instantiate_abstract(self):
        """抽象类不能直接实例化"""
        with pytest.raises(TypeError):
            DeriveInterface()  # type: ignore

    def test_concrete_subclass(self):
        """实现所有抽象方法的子类可正常实例化"""

        class ConcreteDerive(DeriveInterface):
            def derive(self):
                return {"status": "ok"}

            def check(self):
                return [{"passed": True}]

            def generate_report(self):
                return "report"

        d = ConcreteDerive()
        assert d.derive() == {"status": "ok"}
        assert d.check() == [{"passed": True}]
        assert d.generate_report() == "report"

    def test_analyze_delegates_to_derive_and_check(self):
        """analyze() 应组合 derive + check 的结果"""

        class Impl(DeriveInterface):
            def derive(self):
                return {"conclusions": ["A"]}

            def check(self):
                return [{"passed": True, "check": "c1"}]

            def generate_report(self):
                return "report"

        impl = Impl()
        result = impl.analyze(goal="test", context="ctx")
        assert result["summary"] == {"conclusions": ["A"]}
        assert result["checks"] == [{"passed": True, "check": "c1"}]
        assert result["goal"] == "test"
        assert result["context"] == "ctx"


class TestToolForgeInterface:
    """ToolForgeInterface - 工具匹配接口"""

    def test_abstract_methods_required(self):
        """必须实现 select / match / to_inference_guide"""
        with pytest.raises(TypeError):
            ToolForgeInterface()  # type: ignore

    def test_concrete_toolforge(self):
        class Impl(ToolForgeInterface):
            def select(self, goal, context="", top_n=5, mode="keyword"):
                return [{"tool": "M-001"}]

            def match(self, goal, context="", limit=3, mode="keyword"):
                return {"tools": ["M-001"]}

            def to_inference_guide(self, goal, context="", mode="keyword"):
                return "guide"

        impl = Impl()
        assert impl.select("g") == [{"tool": "M-001"}]
        assert impl.match("g") == {"tools": ["M-001"]}
        assert impl.to_inference_guide("g") == "guide"


class TestPipelineObservable:
    """PipelineObservable - 管道事件接口"""

    def test_abstract_methods(self):
        with pytest.raises(TypeError):
            PipelineObservable()  # type: ignore

    def test_concrete_observable(self):
        events = []

        class Logger(PipelineObservable):
            def on_stage_start(self, stage, context):
                events.append(("start", stage))

            def on_stage_end(self, stage, result):
                events.append(("end", stage))

            def on_error(self, stage, error):
                events.append(("error", stage))

        log = Logger()
        log.on_stage_start("extract", {})
        log.on_stage_end("reason", {})
        log.on_error("fail", ValueError("x"))

        assert events == [("start", "extract"), ("end", "reason"), ("error", "fail")]


class TestPipelineStage:
    """PipelineStage - 管道阶段基类"""

    def test_abstract_run_required(self):
        with pytest.raises(TypeError):
            PipelineStage()  # type: ignore

    def test_default_hooks_do_not_raise(self):
        class ConcreteStage(PipelineStage):
            name = "test_stage"

            def run(self, ctx):
                return {"result": "ok"}

        stage = ConcreteStage()
        assert stage.run({}) == {"result": "ok"}
        # 默认 hook 调用不应抛异常
        stage.before({})
        stage.after({}, {})
        stage.on_error({}, ValueError("x"))


class TestAnalysisResult:
    """AnalysisResult - 统一分析结果"""

    def test_passed_when_all_checks_pass(self):
        result = AnalysisResult(
            summary={"c": 1},
            checks=[{"passed": True}, {"passed": True}],
        )
        assert result.passed is True
        assert result.summary == {"c": 1}

    def test_failed_when_any_check_fails(self):
        result = AnalysisResult(
            summary={},
            checks=[{"passed": True}, {"passed": False}],
        )
        assert result.passed is False

    def test_default_toolforge_matches_empty_list(self):
        result = AnalysisResult(summary={}, checks=[])
        assert result.toolforge_matches == []

    def test_to_dict(self):
        result = AnalysisResult(
            summary={"c": 1},
            checks=[{"passed": True}],
            toolforge_matches=[{"tool": "T1"}],
        )
        d = result.to_dict()
        assert d["summary"] == {"c": 1}
        assert d["checks"] == [{"passed": True}]
        assert d["toolforge_matches"] == [{"tool": "T1"}]
        assert d["passed"] is True
