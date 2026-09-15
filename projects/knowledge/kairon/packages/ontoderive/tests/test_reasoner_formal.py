"""Tests for FormalReasoner — 形式推理引擎"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.reasoners.reasoner_formal import FormalConclusion, FormalReasoner


class TestFormalConclusion:
    def test_defaults(self):
        fc = FormalConclusion(conclusion="测试", certainty="certain", method="subsumption")
        assert fc.confidence == 0.90
        assert fc.derives_from == []


class TestFormalReasoner:
    def test_reason_empty(self):
        fr = FormalReasoner()

        class DummyKnowledge:
            abox = {"facts": {}, "entities": {}}

            class Tbox:
                def get(self, k, d=None):
                    return {}

            tbox = Tbox()
            inferences = []

        results = fr.reason(DummyKnowledge())
        assert isinstance(results, list)

    def test_summary_empty(self):
        fr = FormalReasoner()
        s = fr.summary()
        assert s["total"] == 0
