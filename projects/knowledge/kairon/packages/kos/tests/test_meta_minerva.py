"""Tests for metacog bridge and minerva bridge modules."""

import unittest


class TestMetacogBridge(unittest.TestCase):
    """Test kos.commands.metacog — metacognition bridge."""

    def test_metacog_has_derive(self):
        import kos.commands.metacog as mod

        self.assertTrue(hasattr(mod, "derive_protocol"))


class TestMinervaBridge(unittest.TestCase):
    """Test kos.minerva.bridge — Minerva research bridge."""

    def test_module_importable(self):
        import kos.minerva.bridge as mod

        self.assertTrue(hasattr(mod, "MainBridge") or hasattr(mod, "main"))

    def test_bridge_config(self):
        import kos.minerva.bridge as mod

        self.assertIsNotNone(mod.__doc__)


if __name__ == "__main__":
    unittest.main()
