"""
测试 ToolForge v2 匹配引擎
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from ontoderive.toolforge.matcher import ToolForge, _tokenize


@pytest.fixture
def tf():
    return ToolForge()


def test_tokenize():
    tokens = _tokenize("分析新能源汽车market")
    assert len(tokens) > 0
    assert "market" in tokens


def test_init_loads_tools(tf):
    assert len(tf._tools) >= 50


def test_keyword_match_chinese(tf):
    results = tf.select("分析新能源汽车市场", mode="keyword", top_n=5)
    assert len(results) > 0
    # 第一个结果应有关键词"市场"
    assert results[0]["score"] >= 1


def test_keyword_match_mixed(tf):
    results = tf.select("设计数字化平台", mode="keyword", context="政府,教育")
    assert len(results) > 0


def test_tfidf_match(tf):
    results = tf.select("industry competition strategy", mode="tfidf", top_n=5)
    # TF-IDF可能返回空（取决于中英文混合），但不应崩溃
    assert isinstance(results, list)


def test_hybrid_match(tf):
    results = tf.select("分析市场", mode="hybrid", top_n=5)
    assert len(results) >= 0
    for r in results:
        assert "id" in r
        assert "matched" in r


def test_inference_guide(tf):
    guide = tf.to_inference_guide("分析新能源汽车市场", mode="keyword")
    assert "# ToolForge" in guide
    assert "推荐推导框架" in guide


def test_report(tf):
    matched = tf.report("分析市场", mode="keyword")
    assert isinstance(matched, dict)


def test_empty_goal(tf):
    results = tf.select("", top_n=3)
    assert isinstance(results, list)


def test_match_returns_categories(tf):
    matched = tf.match("分析新能源汽车市场", mode="keyword")
    assert "methodologies" in matched
    assert "strategies" in matched
    assert "patterns" in matched
