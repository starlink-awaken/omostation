"""Tests for KOS maintenance modules."""

import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestIncrementalIndexer(unittest.TestCase):
    """Test the IncrementalIndexer class."""

    def test_import(self):
        from kos.maintenance.indexer import IncrementalIndexer

        self.assertTrue(callable(IncrementalIndexer))

    def test_creation(self):
        from kos.maintenance.indexer import IncrementalIndexer

        indexer = IncrementalIndexer()
        self.assertIsNotNone(indexer)
        indexer.close()

    def test_get_zones(self):
        from kos.maintenance.indexer import IncrementalIndexer

        indexer = IncrementalIndexer()
        zones = indexer._get_zones()
        self.assertIsInstance(zones, dict)
        self.assertGreater(len(zones), 0)
        indexer.close()

    def test_compute_hash(self):
        # Create a temp file
        import tempfile

        from kos.maintenance.indexer import IncrementalIndexer

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Test content")
            f.flush()
            h = IncrementalIndexer._compute_hash(Path(f.name))
            self.assertIsInstance(h, str)
            self.assertEqual(len(h), 64)  # SHA-256 hex
            os.unlink(f.name)

    def test_match_pattern(self):
        from kos.maintenance.indexer import IncrementalIndexer

        self.assertTrue(IncrementalIndexer._match_pattern("test.md", "*.md"))
        self.assertTrue(IncrementalIndexer._match_pattern("test.txt", "*.txt"))
        self.assertFalse(IncrementalIndexer._match_pattern("test.md", "*.txt"))

    def test_extract_text(self):
        import tempfile

        from kos.maintenance.indexer import IncrementalIndexer

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nBody content")
            f.flush()
            text = IncrementalIndexer._extract_text(Path(f.name))
            self.assertIn("Title", text)
            self.assertIn("Body content", text)
            os.unlink(f.name)

    def test_extract_title(self):
        from kos.maintenance.indexer import IncrementalIndexer

        self.assertEqual(IncrementalIndexer._extract_title("# My Title\n\nBody", "default"), "My Title")
        self.assertEqual(IncrementalIndexer._extract_title("No heading", "default"), "default")

    def test_context_manager(self):
        from kos.maintenance.indexer import IncrementalIndexer

        with IncrementalIndexer() as indexer:
            zones = indexer._get_zones()
            self.assertGreater(len(zones), 0)


class TestFileWatcher(unittest.TestCase):
    """Test the FileWatcher class."""

    def test_import(self):
        from kos.maintenance.watcher import FileWatcher

        self.assertTrue(callable(FileWatcher))

    def test_creation(self):
        from kos.maintenance.watcher import FileWatcher

        watcher = FileWatcher(poll_interval=10)
        self.assertIsNotNone(watcher)
        self.assertEqual(watcher.poll_interval, 10)
        watcher.stop()


class TestAlertService(unittest.TestCase):
    """Test the AlertService class."""

    def test_import(self):
        from kos.maintenance.alerts import AlertService

        self.assertTrue(callable(AlertService))

    def test_creation(self):
        from kos.maintenance.alerts import AlertService

        service = AlertService()
        self.assertIsNotNone(service)
        service.close()

    def test_checks_defined(self):
        from kos.maintenance.alerts import AlertService

        self.assertIn("index_integrity", AlertService.CHECKS)
        self.assertIn("vector_lag", AlertService.CHECKS)
        self.assertIn("search_latency", AlertService.CHECKS)
        self.assertIn("cache_hit_rate", AlertService.CHECKS)
        self.assertIn("orphan_entities", AlertService.CHECKS)
        self.assertIn("db_size", AlertService.CHECKS)

    def test_check_index_integrity(self):
        from kos.maintenance.alerts import AlertService

        service = AlertService()
        result = service._check_index_integrity(AlertService.CHECKS["index_integrity"])
        # Should return None if healthy
        self.assertIsNone(result)
        service.close()

    def test_check_orphan_entities(self):
        from kos.maintenance.alerts import AlertService

        service = AlertService()
        result = service._check_orphan_entities(AlertService.CHECKS["orphan_entities"])
        # Should return None if no orphans
        self.assertIsNone(result)
        service.close()

    def test_check_all(self):
        from kos.maintenance.alerts import AlertService

        service = AlertService()
        results = service.check_all()
        self.assertIn("timestamp", results)
        self.assertIn("alerts", results)
        self.assertIn("healthy", results)
        self.assertIsInstance(results["alerts"], list)
        service.close()


if __name__ == "__main__":
    unittest.main()
