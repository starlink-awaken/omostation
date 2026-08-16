"""SemanticMatcher 测试 — TF-IDF + 余弦相似度"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from ontoderive.foundation.semantic import SemanticMatcher


class TestTokenization:
    def test_chinese_bigram(self):
        m = SemanticMatcher()
        tokens = m._tokenize("芯片供应商库存")
        assert "芯片" in tokens
        assert "供应" in tokens
        assert "库存" in tokens

    def test_english_number_tokens(self):
        m = SemanticMatcher()
        tokens = m._tokenize("CPU使用率95%")
        # 英文token和数字应被提取
        assert any("cpu" in t for t in tokens)

    def test_mixed_chinese_english(self):
        m = SemanticMatcher()
        tokens = m._tokenize("ISO9001认证标准")
        assert any("iso9001" in t for t in tokens)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        m = SemanticMatcher()
        v = m._vectorize("芯片库存不足")
        assert m.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_different_vectors(self):
        m = SemanticMatcher()
        v1 = m._vectorize("芯片库存")
        v2 = m._vectorize("骑手数量")
        sim = m.cosine_similarity(v1, v2)
        assert sim < 0.3

    def test_related_vectors(self):
        m = SemanticMatcher()
        v1 = m._vectorize("芯片供应商库存")
        v2 = m._vectorize("芯片库存不足")
        sim = m.cosine_similarity(v1, v2)
        assert sim > 0.2


class TestMatch:
    def test_best_match_returns_most_similar(self):
        m = SemanticMatcher()
        best, score = m.best_match("芯片库存", ["骑手数量", "芯片供应商库存", "审计问题"])
        assert "芯片" in best
        assert score > 0.1

    def test_match_returns_sorted(self):
        m = SemanticMatcher()
        results = m.match("芯片库存", ["芯片供应商库存", "审计问题"], threshold=0.0)
        assert results[0][1] >= results[-1][1]

    def test_is_semantically_related(self):
        m = SemanticMatcher()
        assert m.is_semantically_related("芯片库存", "芯片供应商库存", threshold=0.15)
        assert not m.is_semantically_related("芯片库存", "骑手数量", threshold=0.30)


class TestFit:
    def test_fit_builds_idf(self):
        m = SemanticMatcher(["芯片库存不足", "芯片产能利用率", "骑手社保覆盖率"])
        assert len(m.idf) > 0
        assert len(m.doc_vectors) == 3


class TestEdgeCases:
    def test_empty_corpus(self):
        m = SemanticMatcher()
        assert m.match("test", []) == []

    def test_empty_string(self):
        m = SemanticMatcher()
        assert m.cosine_similarity(m._vectorize(""), m._vectorize("test")) == 0.0

    def test_single_char(self):
        m = SemanticMatcher()
        tokens = m._tokenize("芯")
        assert tokens == []  # bigram needs 2 chars
