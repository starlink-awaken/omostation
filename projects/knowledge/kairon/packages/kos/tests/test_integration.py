"""Tests for KOS ecosystem integration modules."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestGbrainBridge(unittest.TestCase):
    """Test the GbrainBridge class."""

    def test_import(self):
        from kos.gbrain_bridge import GbrainBridge

        self.assertTrue(callable(GbrainBridge))

    def test_creation(self):
        from kos.gbrain_bridge import GbrainBridge

        bridge = GbrainBridge()
        self.assertIsNotNone(bridge)
        bridge.close()

    def test_ensure_sync_table(self):
        from kos.gbrain_bridge import GbrainBridge

        bridge = GbrainBridge()
        bridge.ensure_sync_table()
        # Should not raise
        bridge.close()

    def test_sync_status(self):
        from kos.gbrain_bridge import GbrainBridge

        with GbrainBridge() as bridge:
            status = bridge.sync_status()
            self.assertIn("timestamp", status)
            self.assertIn("kos", status)
            self.assertIn("gbrain", status)
            self.assertIn("documents", status["kos"])
            self.assertIn("entities", status["kos"])

    def test_context_manager(self):
        from kos.gbrain_bridge import GbrainBridge

        with GbrainBridge() as bridge:
            status = bridge.sync_status()
            self.assertIsInstance(status, dict)


class TestMinervaBridge(unittest.TestCase):
    """Test the Minerva bridge extensions."""

    def test_import(self):
        from kos.minerva.bridge import cmd_research, cmd_status

        self.assertTrue(callable(cmd_research))
        self.assertTrue(callable(cmd_status))

    def test_cmd_status(self):
        from kos.minerva.bridge import cmd_status

        result = cmd_status()
        self.assertIn("minerva_zone", result)
        self.assertIn("kos_index", result)


class TestMCPToolHandlers(unittest.TestCase):
    """Test new MCP tool handler functions."""

    def test_tool_research_pipeline_import(self):
        from kos.mcp.server import tool_research_pipeline

        self.assertTrue(callable(tool_research_pipeline))

    def test_tool_fact_check_import(self):
        from kos.mcp.server import tool_fact_check

        self.assertTrue(callable(tool_fact_check))

    def test_tool_sync_gbrain_import(self):
        from kos.mcp.server import tool_sync_gbrain

        self.assertTrue(callable(tool_sync_gbrain))

    def test_tool_fact_check_runs(self):
        from kos.mcp.server import tool_fact_check

        result = tool_fact_check("test claim")
        self.assertIn("claim", result)
        self.assertIn("evidence", result)
        self.assertIn("verdict", result)


if __name__ == "__main__":
    unittest.main()
