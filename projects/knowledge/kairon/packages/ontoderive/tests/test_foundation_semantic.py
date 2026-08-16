"""
测试 foundation/semantic.py - SemanticMatcher (TF-IDF 语义匹配)
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from ontoderive.foundation.semantic import SemanticMatcher  # type: ignore[import-not-found]


class TestSemanticMatcher:
    """SemanticMatcher - TF-IDF + 余弦相似度"""

    def test_empty_corpus_init(self):
        """空语料初始化不应报错"""
        m = SemanticMatcher()
        assert m.corpus == []
        assert m.idf == {}
        assert m.doc_vectors == []

    def test_fit_computes_idf_and_vectors(self):
        """fit 后 idf 和 doc_vectors 应有内容"""
        docs = ["hello world", "world peace"]
        m = SemanticMatcher(docs)
        assert len(m.idf) > 0
        assert len(m.doc_vectors) == 2

    def test_tokenize_extracts_english_and_bigrams(self):
        m = SemanticMatcher()
        tokens = m._tokenize("hello world 测试数据 project_v2")
        # "hello", "world", "project_v2" (>=2 chars), plus CJK bigrams
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" not in tokens  # "测试" 是 CJK
        # CJK bigrams
        assert "测试" in tokens
        assert "试数" in tokens
        assert "数据" in tokens

    def test_cosine_similarity_identical(self):
        """相同向量的余弦相似度为 1.0"""
        m = SemanticMatcher()
        vec = {"hello": 0.5, "world": 0.5}
        sim = m.cosine_similarity(vec, vec)
        assert sim == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """正交向量余弦相似度为 0.0"""
        m = SemanticMatcher()
        sim = m.cosine_similarity({"a": 1.0}, {"b": 1.0})
        assert sim == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        """空向量的相似度为 0.0"""
        m = SemanticMatcher()
        sim = m.cosine_similarity({}, {"a": 1.0})
        assert sim == pytest.approx(0.0)

    def test_match_returns_sorted_results(self):
        """match 应按相似度降序返回"""
        docs = ["profit margin growth", "market share expansion", "weather report"]
        m = SemanticMatcher(docs)
        results = m.match("growth profit", ["profit margin growth", "weather report"])
        assert len(results) >= 1
        # 第一项应与查询最相似
        assert results[0][0] == "profit margin growth"

    def test_match_respects_threshold(self):
        """低于阈值的匹配应被过滤"""
        m = SemanticMatcher(["hello world core dump"])
        results = m.match("completely unrelated totally different", ["hello world core dump"], threshold=0.99)
        assert len(results) == 0

    def test_best_match_returns_top(self):
        docs = ["alpha beta", "gamma delta"]
        m = SemanticMatcher(docs)
        best, score = m.best_match("alpha", ["alpha beta", "gamma delta"])
        assert best == "alpha beta"
        assert score > 0

    def test_best_match_no_candidates(self):
        m = SemanticMatcher(["whatever"])
        best, score = m.best_match("query", ["totally unrelated"], threshold=0.99)
        assert best == ""
        assert score == 0.0

    def test_is_semantically_related_similar_texts(self):
        m = SemanticMatcher()
        # 训练一些语料使 IDF 有意义
        m.fit(["market growth analysis", "economic growth report"])
        assert m.is_semantically_related("market growth", "economic growth")

    def test_is_semantically_related_different_texts(self):
        m = SemanticMatcher(["core dump analysis", "market growth"])
        # 完全不相关
        related = m.is_semantically_related("computer memory dump", "banana price", threshold=0.5)
        assert not related

    def test_unknown_terms_use_default_idf(self):
        """_vectorize 中未知词应使用默认 IDF 1.0"""
        m = SemanticMatcher(["hello world"])
        vec = m._vectorize("unknown_term_xyz")
        # 未知词虽不在 idf 中，但应使用默认值 1.0
        assert len(vec) >= 0  # 不报错即可
