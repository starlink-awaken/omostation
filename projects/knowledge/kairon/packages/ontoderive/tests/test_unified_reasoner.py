"""Tests for UnifiedReasoner + ReasoningSelector + ContentCanonicalizer"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.reasoners.reasoning import ContentCanonicalizer, DataProfile, ReasoningSelector
from ontoderive.reasoners.unified_reasoner import UnifiedConclusion, UnifiedReasoner


class TestUnifiedConclusion:
    def test_to_dict(self):
        uc = UnifiedConclusion(conclusion="测试", certainty="certain", method="numeric_comparison")
        d = uc.to_dict()
        assert d["conclusion"] == "测试"
        assert d["type"] == "numeric_comparison"


class TestUnifiedReasoner:
    def test_reason_empty(self):
        ur = UnifiedReasoner()
        results = ur.reason({}, {})
        assert isinstance(results, list)

    def test_reason_with_facts(self):
        ur = UnifiedReasoner()
        facts = {"D-F1": {"desc": "人数", "value": "500"}, "D-F2": {"desc": "人数", "value": "100"}}
        results = ur.reason(facts, {})
        types = [r.method for r in results]
        assert "numeric_comparison" in types

    def test_summary(self):
        ur = UnifiedReasoner()
        ur.reason({"D-F1": {"desc": "人数", "value": "100"}}, {})
        s = ur.summary()
        assert "total" in s
        assert "by_source" in s


class TestContentCanonicalizer:
    def test_canonicalize_facts(self):
        cc = ContentCanonicalizer()
        raw = {"D-F1": {"desc": "人数", "value": "100人"}}
        result = cc.canonicalize_facts(raw)
        assert result["D-F1"]["structured_value"] == 100.0
        assert result["D-F1"]["has_numeric"] is True

    def test_canonicalize_facts_timestamp(self):
        cc = ContentCanonicalizer()
        raw = {"D-F1": {"desc": "2023年数据", "value": "100"}}
        result = cc.canonicalize_facts(raw)
        assert result["D-F1"]["has_timestamp"] is True

    def test_canonicalize_inferences(self):
        cc = ContentCanonicalizer()
        raw = {"INF-L1": {"text": "confidence: high\n结论: 测试结论\n", "derives_from": ["D-F1"]}}
        result = cc.canonicalize_inferences(raw)
        assert result["INF-L1"]["derives_from"] == ["D-F1"]
        assert result["INF-L1"]["confidence_value"] == 0.92


class TestReasoningSelector:
    def test_profile_empty(self):
        rs = ReasoningSelector()
        p = rs.profile({}, {})
        assert p.fact_count == 0
        assert p.inf_count == 0

    def test_select_rules(self):
        rs = ReasoningSelector()
        p = DataProfile(has_numeric=True, fact_count=1, inf_count=1)
        selected = rs.select_rules(p)
        assert "numeric_comparison" in selected
        assert "coverage_analysis" in selected

    def test_explain_selection(self):
        rs = ReasoningSelector()
        p = DataProfile(fact_count=5, inf_count=3, has_numeric=True)
        explanation = rs.explain_selection(p)
        assert "数据画像" in explanation
        assert "激活规则" in explanation
