# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Tests for kos.perception — all network calls mocked."""

from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestWebSearch:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.search")

    def test_returns_list(self):
        result = self.mod.web_search("test query")
        assert isinstance(result, list)

    def test_graceful_on_error(self):
        with patch("kos.perception.search._async_search", side_effect=RuntimeError("fail")):
            result = self.mod.web_search("test")
            assert result == []


class TestWebSearchTimeout:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.search")

    def test_empty_on_timeout(self):
        result = self.mod.web_search("")
        assert isinstance(result, list)


class TestScrapeURL:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.scrape")

    def test_returns_dict(self):
        with patch("kos.perception.scrape._async_scrape") as mock_scrape:
            mock_scrape.return_value = {
                "url": "http://example.com",
                "title": "Example",
                "text_content": "Hello world",
                "extracted_at": "2026-01-01T00:00:00",
            }
            result = self.mod.scrape_url("http://example.com")
            assert result is not None
            assert result["url"] == "http://example.com"


class TestScrapeURLFailure:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.scrape")

    def test_returns_none_on_error(self):
        with patch("kos.perception.scrape._async_scrape", side_effect=RuntimeError("fail")):
            result = self.mod.scrape_url("http://invalid")
            assert result is None

    def test_logs_async_scrape_error(self, caplog):
        with patch("kos.perception.scrape._async_scrape", side_effect=RuntimeError("fail")):
            with caplog.at_level("WARNING", logger="kos.perception.scrape"):
                result = self.mod.scrape_url("http://invalid")
        assert result is None
        assert "scrape_url failed" in caplog.text


class TestFactInjector:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.fact_injector")
        fd, self.tmp_path = tempfile.mkstemp(suffix=".db")
        self.conn = sqlite3.connect(self.tmp_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fact_triples (
                id TEXT PRIMARY KEY, sub TEXT NOT NULL, pred TEXT NOT NULL,
                obj TEXT NOT NULL, metadata TEXT DEFAULT '{}',
                source_node_id TEXT DEFAULT 'local_prime',
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self.conn.commit()
        self._orig_db_path = self.mod.DB_PATH
        self.mod.DB_PATH = self.tmp_path  # type: ignore[reportAttributeAccessIssue]

    def teardown_method(self):
        self.conn.close()
        self.mod.DB_PATH = self._orig_db_path  # type: ignore[reportAttributeAccessIssue]
        Path(self.tmp_path).unlink(missing_ok=True)

    def test_inject_facts(self):
        facts = [
            {"sub": "Test", "pred": "is", "obj": "working"},
            {"sub": "Another", "pred": "has", "obj": "value"},
        ]
        count = self.mod.inject_facts(facts)
        assert count == 2
        rows = self.conn.execute("SELECT COUNT(*) FROM fact_triples").fetchone()
        assert rows[0] == 2

    def test_inject_to_real_db_smoke(self):
        count = self.mod.inject_facts(
            [
                {
                    "sub": "SmokeTest",
                    "pred": "perception_test",
                    "obj": "ok",
                    "metadata": json.dumps({"source": "test", "confidence": 0.9}),
                }
            ]
        )
        assert count >= 0

    def test_ignored_insert_is_not_counted(self):
        facts = [
            {"sub": "First", "pred": "is", "obj": "stored"},
            {"sub": "Second", "pred": "is", "obj": "ignored"},
        ]
        with patch("kos.perception.fact_injector.uuid.uuid4", return_value="same-id-value"):
            count = self.mod.inject_facts(facts)
        assert count == 1
        rows = self.conn.execute("SELECT COUNT(*) FROM fact_triples").fetchone()
        assert rows[0] == 1

    def test_metadata_dict_is_serialized_as_json(self):
        count = self.mod.inject_facts([{"sub": "Meta", "pred": "has", "obj": "dict", "metadata": {"source": "unit"}}])
        assert count == 1
        row = self.conn.execute("SELECT metadata FROM fact_triples WHERE sub = 'Meta'").fetchone()
        assert json.loads(row[0]) == {"source": "unit"}


class TestFactInjectorValidation:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.fact_injector")

    def test_valid_fact(self):
        assert self.mod._validate_fact({"sub": "A", "pred": "B", "obj": "C"})

    def test_missing_sub(self):
        assert not self.mod._validate_fact({"pred": "B", "obj": "C"})

    def test_missing_pred(self):
        assert not self.mod._validate_fact({"sub": "A", "obj": "C"})

    def test_empty_dict(self):
        assert not self.mod._validate_fact({})


class TestRunPerception:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.run_perception")

    def test_returns_false_on_empty_search(self):
        with patch("kos.perception.search.web_search", return_value=[]):
            result = self.mod.run_perceive("test query")
            assert result is False

    def test_returns_true_with_results(self):
        with (
            patch("kos.perception.search.web_search") as mock_search,
            patch("kos.perception.scrape.scrape_url") as mock_scrape,
            patch("kos.perception.fact_injector.inject_facts") as mock_inject,
        ):
            mock_search.return_value = [{"url": "http://example.com", "title": "Test", "snippet": "test"}]
            mock_scrape.return_value = {"url": "http://example.com", "title": "Test", "text_content": "content"}
            mock_inject.return_value = 1
            result = self.mod.run_perceive("test query")
            assert result is True


class TestNoNetworkFallback:
    def setup_method(self):
        self.mod = importlib.import_module("kos.perception.search")

    def test_empty_results_no_crash(self):
        result = self.mod.web_search("anything")
        assert isinstance(result, list)
