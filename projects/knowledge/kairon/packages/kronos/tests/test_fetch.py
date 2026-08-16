"""Kronos tests."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kronos.fetch_router import _is_error_page, content_type_label, plan_for_url


class TestFetchRouter:
    def test_error_page_detection(self):
        """错误页检测"""
        error = '{"error":{"message":"请求异常","code":40362}}'
        real = "<html>" + "<p>内容</p>" * 200 + "</html>"
        short = "<p>short</p>"
        assert _is_error_page(error)
        assert not _is_error_page(real)
        assert _is_error_page(short)

    def test_url_classification(self):
        """URL 分类"""
        tests = [
            ("https://mp.weixin.qq.com/s/test", "公众号"),
            ("https://zhuanlan.zhihu.com/p/123", "文章"),
            ("https://arxiv.org/abs/2301.07041", "论文"),
            ("https://github.com/user/repo", "GitHub仓库"),
            ("https://example.com", "未知"),
        ]
        for url, expected_type in tests:
            plan = plan_for_url(url)
            label = content_type_label(plan.content_type)
            assert label == expected_type, f"{url}: {label} != {expected_type}"

    def test_fallback_chain_structure(self):
        """fallback 链结构"""
        chain = plan_for_url("https://mp.weixin.qq.com/s/test")
        layers = []
        p = chain
        while p:
            layers.append(p.layer.name)
            p = p.fallback_plan
        assert len(layers) >= 4, f"只有 {len(layers)} 层"
        assert "L0_NATIVE" in layers
        assert "L4_BROWSER" in layers or "L1_MCP_DIRECT" in layers

    def test_version(self):
        from kronos import __version__

        assert __version__ == "0.5.0"


if __name__ == "__main__":
    t = TestFetchRouter()
    for name in dir(t):
        if name.startswith("test_"):
            getattr(t, name)()
            print(f"  ✅ {name}")
    print("全部通过")
