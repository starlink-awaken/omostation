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

    def test_search_finds_match(self):
        m = Market()
        results = m.search("research")
        assert len(results) >= 1
        assert any("research" in r.get("description", "").lower() or "research" in r.get("tags", []) for r in results)

    def test_search_no_match(self):
        m = Market()
        results = m.search("xyznonexistent12345")
        assert len(results) == 0

    def test_publish_adds_service(self):
        m = Market()
        result = m.publish(
            "test-market-svc", repo="example/test", description="A test service", entry="server.py", svc_type="python"
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
