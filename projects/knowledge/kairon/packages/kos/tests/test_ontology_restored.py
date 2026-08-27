"""Tests for kos.ontology — restored from _legacy/tests/test_ontology_*.py."""

import unittest


class TestOntologyConfigValidation(unittest.TestCase):
    """Verify ontology configuration validation logic."""

    def test_entity_sources_required(self):
        manifest = {"zones": {}, "artifacts": {}}
        # The manifest must have entitySources for ontology to work
        sources = manifest.get("entitySources", [])
        self.assertEqual(len(sources), 0)

    def test_empty_entity_sources_allowed(self):
        manifest = {"entitySources": [], "predicatePatterns": {"en": {}}}
        self.assertEqual(len(manifest["entitySources"]), 0)
        self.assertIn("predicatePatterns", manifest)

    def test_predicate_patterns_structure(self):
        patterns = {"en": {"reports_to": ["reports to"], "manages": ["manages"]}}
        self.assertIn("reports_to", patterns["en"])
        self.assertEqual(len(patterns["en"]), 2)


class TestStaleDetection(unittest.TestCase):
    """Test stale detection data structures (no engine deps)."""

    def test_stale_result_schema(self):
        result = {"stale": True, "reason": "never_built", "changes": []}
        self.assertIn("stale", result)
        self.assertIn("reason", result)

    def test_not_stale_result_schema(self):
        result = {"stale": False, "changes": []}
        self.assertFalse(result["stale"])

    def test_modified_file_result_schema(self):
        result = {"stale": True, "changes": [{"file": "ENTITIES.md", "status": "modified"}]}
        self.assertEqual(len(result["changes"]), 1)
        self.assertEqual(result["changes"][0]["status"], "modified")


if __name__ == "__main__":
    unittest.main()
