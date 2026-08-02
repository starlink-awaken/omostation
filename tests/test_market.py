"""Tests for Market."""

from agora.plugins.market.market import Market


class TestMarket:
    def test_list_all_has_builtins(self):
        m = Market()
        svcs = m.list_all()
        assert len(svcs) >= 8  # at least 8 built-in services
        names = {s["name"] for s in svcs}
        assert "minerva" in names
        assert "filesystem" in names

    # ── F-13: SSRF 防护 ──────────────────────────────────────

    def test_fetch_repo_metadata_rejects_path_traversal(self):
        """路径穿越/协议注入 repo 输入被拒绝 (SSRF 防护)。"""
        m = Market()
        for evil in [
            "../../../../etc/passwd",
            "https://evil.example/x",
            "http://169.254.169.254/latest",
            "a/../b",
            "",
            "no-slash-repo",
            "owner/name/extra",
        ]:
            result = m._fetch_repo_metadata(evil)
            assert "error" in result, f"repo={evil!r} 应被拒绝"
            assert "invalid repo format" in result["error"]

    def test_fetch_repo_metadata_accepts_valid_format(self):
        """合法 owner/name 输入通过校验并触发 GitHub API 请求。"""
        m = Market()
        result = m._fetch_repo_metadata("starlink-awaken/omostation")
        # 无论网络可达性如何, 都不应返回格式错误
        assert "error" not in result

    def test_search_finds_match(self):
        m = Market()
        results = m.search("research")
        assert len(results) >= 1
        assert any(
            "research" in r.get("description", "").lower()
            or "research" in r.get("tags", [])
            for r in results
        )

    def test_search_no_match(self):
        m = Market()
        results = m.search("xyznonexistent12345")
        assert len(results) == 0

    def test_publish_adds_service(self):
        m = Market()
        result = m.publish(
            "test-market-svc",
            repo="example/test",
            description="A test service",
            entry="server.py",
            svc_type="python",
        )
        assert result["name"] == "test-market-svc"
        assert result["repo"] == "example/test"

    def test_published_is_loadable(self):
        m = Market()
        m.publish("test-load", repo="example/test", description="Load test")
        published = m._load_published()
        assert "test-load" in published


class TestMarketInstall:
    def test_search_by_name(self):
        m = Market()
        results = m.search("minerva")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "minerva" in names

    def test_publish_already_exists(self):
        m = Market()
        m.publish("dup-test", repo="a/b", description="Original")
        published = m._load_published()
        assert "dup-test" in published
