"""
测试 intelligence/judge.py - OntoDeriveJudge 评估器
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.intelligence.judge import JudgeResult, OntoDeriveJudge  # type: ignore[import-not-found]


class TestJudgeResult:
    """JudgeResult - 判断结果数据类"""

    def test_basic_construction(self):
        r = JudgeResult(
            category="logic",
            passed=True,
            confidence=0.85,
            reasoning="推论有效",
            cites=["D-F1", "D-F2"],
        )
        assert r.category == "logic"
        assert r.passed is True
        assert r.confidence == 0.85
        assert r.reasoning == "推论有效"
        assert r.cites == ["D-F1", "D-F2"]

    def test_failed_judgment(self):
        r = JudgeResult(
            category="evidence",
            passed=False,
            confidence=0.3,
            reasoning="证据不足",
            cites=[],
        )
        assert r.passed is False
        assert r.cites == []


class TestOntoDeriveJudge:
    """OntoDeriveJudge - 知识质量评估器 (无 LLM 回退)"""

    def test_judge_project_no_enhancer_fallback(self, tmp_project):
        """LLM 不可用时 judge_project 返回 fallback 字典"""
        judge = OntoDeriveJudge(project_root=str(tmp_project), enhancer=None)
        result = judge.judge_project()
        assert result["verdict"] == "insufficient_data"
        assert result["rule_engine_only"] is True

    def test_derive_new_insights_no_enhancer(self, tmp_project):
        """LLM 不可用时 derive_new_insights 返回空列表"""
        judge = OntoDeriveJudge(project_root=str(tmp_project), enhancer=None)
        insights = judge.derive_new_insights()
        assert insights == []

    def test_evaluate_inference_quality_no_enhancer(self, tmp_project):
        """LLM 不可用时 evaluate_inference_quality 返回 None"""
        judge = OntoDeriveJudge(project_root=str(tmp_project), enhancer=None)
        result = judge.evaluate_inference_quality(
            inference_title="测试推论",
            inference_text="推论内容",
            derives_from=["D-F1"],
        )
        assert result is None

    def test_evaluate_all_inferences_no_enhancer(self, tmp_project):
        """LLM 不可用时 evaluate_all_inferences 返回空字典"""
        judge = OntoDeriveJudge(project_root=str(tmp_project), enhancer=None)
        results = judge.evaluate_all_inferences()
        assert results == {}

    def test_collect_project_context(self, tmp_project):
        """_collect_project_context 应读取项目文件"""
        judge = OntoDeriveJudge(project_root=str(tmp_project), enhancer=None)
        ctx = judge._collect_project_context()
        assert "facts" in ctx
        assert "inferences" in ctx
        assert "schemes" in ctx

    def test_constructor_when_enhancer_not_given(self, tmp_project):
        """不传 enhancer 时构造器不会抛异常"""
        judge = OntoDeriveJudge(project_root=str(tmp_project))
        # 应尝试 import .llm.get_enhancer，失败则 enhancer 为 None
        # 不应抛出异常
        assert judge.enhancer is None or hasattr(judge.enhancer, "available")

    def test_judge_project_missing_directory(self, tmp_path):
        """项目目录不存在时不应抛异常"""
        judge = OntoDeriveJudge(project_root=str(tmp_path / "nonexistent"), enhancer=None)
        result = judge.judge_project()
        assert result["verdict"] == "insufficient_data"
