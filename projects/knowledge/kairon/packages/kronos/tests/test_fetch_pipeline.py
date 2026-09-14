"""Tests for kronos fetch_router — 5-layer fetch architecture & URL routing."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kronos.fetch_router import (
    ContentType,
    FetchLayer,
    _classify,
    _is_error_page,
    build_cloakbrowser_plan,
    build_jina_plan,
    content_type_label,
    diagnose_fetch_error,
    execute_fallback_chain,
    extract_image_urls,
    is_image_url,
    list_all_methods,
    plan_for_url,
    url_hash,
)


class TestURLClassification:
    """URL pattern → ContentType mapping."""

    def test_arxiv_is_paper(self):
        assert _classify("https://arxiv.org/abs/2301.07041") == ContentType.PAPER

    def test_pdf_is_paper(self):
        assert _classify("https://example.com/paper.pdf") == ContentType.PAPER

    def test_weixin(self):
        assert _classify("https://mp.weixin.qq.com/s/abc123") == ContentType.WEIXIN

    def test_zhihu(self):
        assert _classify("https://zhuanlan.zhihu.com/p/12345") == ContentType.ARTICLE

    def test_github(self):
        assert _classify("https://github.com/user/repo") == ContentType.GITHUB

    def test_csdn(self):
        assert _classify("https://blog.csdn.net/abc/article/123") == ContentType.CODE

    def test_twitter(self):
        assert _classify("https://twitter.com/user/status/123") == ContentType.SOCIAL

    def test_x_dot_com(self):
        assert _classify("https://x.com/user/status/456") == ContentType.SOCIAL

    def test_youtube(self):
        assert _classify("https://youtube.com/watch?v=abc") == ContentType.VIDEO

    def test_bilibili(self):
        assert _classify("https://bilibili.com/video/BV123") == ContentType.VIDEO

    def test_gov_policy(self):
        assert _classify("https://www.gov.cn/policy/2026") == ContentType.POLICY

    def test_unknown(self):
        assert _classify("https://example.com/page") == ContentType.UNKNOWN


class TestContentTypeLabel:
    """ContentType enum → Chinese label."""

    def test_labels(self):
        assert content_type_label(ContentType.ARTICLE) == "文章"
        assert content_type_label(ContentType.PAPER) == "论文"
        assert content_type_label(ContentType.SOCIAL) == "社交动态"
        assert content_type_label(ContentType.WEIXIN) == "公众号"
        assert content_type_label(ContentType.UNKNOWN) == "未知"
        assert content_type_label(ContentType.GITHUB) == "GitHub仓库"


class TestFetchLayer:
    """FetchLayer enum values."""

    def test_layer_order(self):
        """Lower number = higher priority."""
        assert FetchLayer.L0_NATIVE < FetchLayer.L1_MCP_DIRECT
        assert FetchLayer.L4_BROWSER > FetchLayer.L2_JINA_PROXY


class TestFallbackChain:
    """plan_for_url / execute_fallback_chain structure."""

    def test_chain_has_fallback(self):
        """plan_for_url returns a chain with at least 2 plans."""
        plan = plan_for_url("https://example.com/test")
        assert plan is not None
        assert plan.fallback_plan is not None

    def test_chain_depth(self):
        """execute_fallback_chain returns 4+ layers."""
        chain = execute_fallback_chain("https://example.com/test")
        assert len(chain) >= 4
        layers = [c["layer_name"] for c in chain]
        assert "L0_native_http" in layers[0]

    def test_jina_plan_structure(self):
        """build_jina_plan returns correct layer."""
        plan = build_jina_plan("https://example.com")
        assert plan.layer == FetchLayer.L2_JINA_PROXY
        assert "r.jina.ai" in plan.call_params.get("proxy_url", "")

    def test_cloakbrowser_plan_structure(self):
        """build_cloakbrowser_plan returns correct layer."""
        plan = build_cloakbrowser_plan("https://example.com")
        assert plan.layer == FetchLayer.L4_BROWSER
        assert plan.method_name == "cloakbrowser"


class TestErrorPageDetection:
    """_is_error_page behavior."""

    def test_short_page_is_error(self):
        assert _is_error_page("<p>tiny</p>")

    def test_long_normal_page_is_not_error(self):
        content = "<html>" + "<p>内容</p>" * 200 + "</html>"
        assert not _is_error_page(content)

    def test_error_signal_detected(self):
        content = "<html>" + "访问被限制" + "<p>" * 200 + "</html>"
        assert _is_error_page(content)


class TestImageExtraction:
    """Image URL helpers."""

    def test_extract_image_urls(self):
        html = '<img src="https://example.com/img/photo.jpg">'
        urls = extract_image_urls(html)
        assert len(urls) == 1
        assert urls[0].endswith(".jpg")

    def test_extract_data_src(self):
        html = '<img data-src="https://example.com/img.png">'
        urls = extract_image_urls(html)
        assert len(urls) == 1

    def test_is_image_url(self):
        assert is_image_url("https://example.com/photo.jpg")
        assert is_image_url("https://example.com/images/photo")
        assert not is_image_url("https://example.com/page.html")


class TestDiagnoseFetchError:
    """Error diagnosis table."""

    def test_403_error(self):
        exc = Exception("HTTP 403 Forbidden")
        result = diagnose_fetch_error(exc)
        assert result["code"] == "403_forbidden"

    def test_timeout_error(self):
        exc = Exception("Connection timeout after 30s")
        result = diagnose_fetch_error(exc)
        assert result["code"] == "timeout"

    def test_ssl_error(self):
        exc = Exception("SSLError: certificate verify failed")
        result = diagnose_fetch_error(exc)
        assert result["code"] == "ssl_error"

    def test_unknown_error(self):
        exc = Exception("Something weird happened")
        result = diagnose_fetch_error(exc)
        assert result["code"] == "unknown"


class TestUtilities:
    """Small utility functions."""

    def test_url_hash_consistency(self):
        h1 = url_hash("https://example.com")
        h2 = url_hash("https://example.com")
        assert h1 == h2
        assert len(h1) == 8

    def test_list_all_methods(self):
        methods = list_all_methods()
        assert len(methods) >= 5
        layers = {m["layer"] for m in methods}
        assert "L1_MCP" in layers
        assert "L2_JINA" in layers
        assert "L4_BROWSER" in layers
