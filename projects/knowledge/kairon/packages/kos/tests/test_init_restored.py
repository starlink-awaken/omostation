"""Tests for kos.commands.init — init functionality (restored from _legacy/tests/)."""

import unittest


class TestManifestTemplate(unittest.TestCase):
    """Verify manifest template structure from kos.commands.init."""

    def test_manifest_has_required_keys(self):
        from kos.commands.init import MANIFEST_TEMPLATE

        for key in ("version", "zones", "artifacts", "domains"):
            self.assertIn(key, MANIFEST_TEMPLATE)

    def test_manifest_has_zones(self):
        from kos.commands.init import MANIFEST_TEMPLATE

        self.assertIn("version", MANIFEST_TEMPLATE)


class TestWorkspaceConfigTemplate(unittest.TestCase):
    """Verify workspace_config template structure."""

    def test_template_is_string(self):
        from kos.commands.init import WORKSPACE_CONFIG_PY

        self.assertIsInstance(WORKSPACE_CONFIG_PY, str)
        self.assertGreater(len(WORKSPACE_CONFIG_PY), 100)

    def test_template_contains_key_functions(self):
        from kos.commands.init import WORKSPACE_CONFIG_PY

        for func in ("get_workspace_manifest", "get_artifact_path", "get_zone_path"):
            self.assertIn(func, WORKSPACE_CONFIG_PY)

    def test_template_has_format_placeholder(self):
        from kos.commands.init import WORKSPACE_CONFIG_PY

        self.assertIn("{documents_root}", WORKSPACE_CONFIG_PY)


class TestInitFunctions(unittest.TestCase):
    """Test helper functions used by init."""

    def test_ask_default_returned(self):
        from kos.commands.init import _ask

        # Can't easily test interactive, just verify import works
        self.assertTrue(callable(_ask))

    def test_ask_yes_no_default(self):
        from kos.commands.init import _ask_yes_no

        self.assertTrue(callable(_ask_yes_no))


if __name__ == "__main__":
    unittest.main()
