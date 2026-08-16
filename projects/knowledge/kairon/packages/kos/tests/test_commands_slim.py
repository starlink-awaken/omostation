"""Tests for slim CLI command modules: ai_audit, entity_governance, setup, digest."""

import sys
import unittest
from io import StringIO


class TestAIAudit(unittest.TestCase):
    """Test kos.commands.ai_audit module loading."""

    def test_module_importable(self):
        import kos.commands.ai_audit as mod

        self.assertTrue(hasattr(mod, "main"))

    def test_deprecated_exits_with_error(self):
        import kos.commands.ai_audit as mod

        stderr = StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr
        with self.assertRaises(SystemExit) as ctx:
            mod.main()
        sys.stderr = old_stderr
        self.assertEqual(ctx.exception.code, 1)


class TestEntityGovernance(unittest.TestCase):
    """Test kos.commands.entity_governance module loading."""

    def test_module_importable(self):
        import kos.commands.entity_governance as mod

        self.assertTrue(hasattr(mod, "main"))


class TestSetup(unittest.TestCase):
    """Test kos.commands.setup module loading."""

    def test_module_importable(self):
        import kos.commands.setup as mod

        self.assertTrue(hasattr(mod, "main"))


class TestDigest(unittest.TestCase):
    """Test kos.commands.digest module loading."""

    def test_module_importable(self):
        import kos.commands.digest as mod

        self.assertTrue(hasattr(mod, "main"))


if __name__ == "__main__":
    unittest.main()
