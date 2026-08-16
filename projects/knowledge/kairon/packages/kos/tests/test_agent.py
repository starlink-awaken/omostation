"""Tests for KOS Agent SDK and Subscription Service."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


def _gbrain_available() -> bool:
    """Check if gbrain MCP is reachable."""
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:3131/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


class TestKosAgentClient(unittest.TestCase):
    @unittest.skipUnless(_gbrain_available(), "gbrain MCP not running on :3131")
    def test_search(self):
        from kos.agent.client import KosAgentClient

        client = KosAgentClient()
        result = client.search("test", limit=3)
        self.assertIn("results", result)
        self.assertIn("count", result)

    def test_verify(self):
        from kos.agent.client import KosAgentClient

        client = KosAgentClient()
        result = client.verify("test claim")
        self.assertIn("claim", result)
        self.assertIn("verdict", result)
        self.assertIn("evidence", result)
        self.assertIn(result["verdict"], ["supported", "partial", "no_evidence"])

    def test_search_entities(self):
        from kos.agent.client import KosAgentClient

        client = KosAgentClient()
        entities = client.search_entities("test")
        self.assertIsInstance(entities, list)

    def test_subscribe(self):
        from kos.agent.client import KosAgentClient

        client = KosAgentClient(subscriber_id="test-sub")
        result = client.subscribe("test-topic")
        self.assertIn("sub_id", result)
        self.assertIn("topic", result)
        self.assertEqual(result["topic"], "test-topic")

    def test_list_subscriptions(self):
        from kos.agent.client import KosAgentClient

        client = KosAgentClient(subscriber_id="test-list")
        client.subscribe("topic-1")
        subs = client.list_subscriptions()
        self.assertIsInstance(subs, list)


class TestSubscriptionService(unittest.TestCase):
    """Test the SubscriptionService class."""

    def test_import(self):
        from kos.agent.subscription import SubscriptionService

        self.assertTrue(callable(SubscriptionService))

    def test_creation(self):
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService()
        self.assertIsNotNone(service)

    def test_subscribe_unsubscribe(self):
        from kos.agent.subscription import SubscriptionService
        from kos.config import get_artifact_path

        service = SubscriptionService()
        service.init_table(get_artifact_path("retrievalDatabase"))

        sub = service.subscribe("test-topic", subscriber_id="agent-1")
        self.assertIn("sub_id", sub)
        self.assertTrue(sub["active"])

        result = service.unsubscribe(sub["sub_id"])
        self.assertFalse(result["active"])

    def test_check_matches(self):
        from kos.agent.subscription import SubscriptionService
        from kos.config import get_artifact_path

        service = SubscriptionService()
        service.init_table(get_artifact_path("retrievalDatabase"))

        sub = service.subscribe("测试", subscriber_id="agent-check")
        result = service.check_matches(sub["sub_id"])
        self.assertIn("new_matches", result)
        self.assertIn("documents", result)

    def test_list_subscriptions(self):
        from kos.agent.subscription import SubscriptionService
        from kos.config import get_artifact_path

        service = SubscriptionService()
        service.init_table(get_artifact_path("retrievalDatabase"))

        service.subscribe("topic-a", subscriber_id="agent-list")
        subs = service.list_subscriptions("agent-list")
        self.assertGreater(len(subs), 0)

    def test_check_all(self):
        from kos.agent.subscription import SubscriptionService
        from kos.config import get_artifact_path

        service = SubscriptionService()
        service.init_table(get_artifact_path("retrievalDatabase"))

        service.subscribe("测试", subscriber_id="agent-all")
        results = service.check_all_subscriptions()
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
