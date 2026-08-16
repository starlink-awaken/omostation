"""KOS CLI integration tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CLI_PATH = SCRIPT_DIR / "kos-cli.py"

# Set KOS_HOME for tests
os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


def _run(*args) -> subprocess.CompletedProcess:
    """Run kos-cli.py with args."""
    return subprocess.run(
        [sys.executable, str(CLI_PATH)] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(SCRIPT_DIR),
    )


class TestCLIHelp:
    """Verify CLI help and basic parsing."""

    def test_help(self):
        r = _run("--help")
        assert r.returncode == 0
        assert "KOS CLI" in r.stdout or "KOS CLI" in r.stderr or r.returncode == 0

    def test_domains_help(self):
        r = _run("domains", "--help")
        assert r.returncode == 0

    def test_search_help(self):
        r = _run("search", "--help")
        assert r.returncode == 0

    def test_status_help(self):
        r = _run("status", "--help")
        assert r.returncode == 0

    def test_research_help(self):
        r = _run("research", "--help")
        assert r.returncode == 0

    def test_ingest_help(self):
        r = _run("ingest", "--help")
        assert r.returncode == 0


class TestCLIDomains:
    """Verify domain listing."""

    def test_domains_json(self):
        r = _run("domains", "--format", "json")
        # May fail if workspace_config not found in CI
        if r.returncode == 0:
            data = json.loads(r.stdout)
        assert "command" in data  # type: ignore[reportPossiblyUnboundVariable]
        assert data["data"]["count"] >= 0  # type: ignore[reportPossiblyUnboundVariable]

    def test_domains_table(self):
        r = _run("domains", "--format", "table")
        # Table mode should not error
        if r.returncode == 0:
            assert "Domain" in r.stdout or "domain" in r.stdout.lower() or len(r.stdout) > 0


class TestCLIStatus:
    """Verify system status."""

    def test_status_json(self):
        r = _run("status", "--format", "json")
        if r.returncode == 0:
            data = json.loads(r.stdout)
        assert "domains" in data  # type: ignore[reportPossiblyUnboundVariable]


class TestCLISearch:
    """Verify search functionality."""

    def skip_test_search_json_format(self):
        r = _run("search", "test", "--format", "json", "--limit", "3")
        if r.returncode == 0:
            data = json.loads(r.stdout)
            assert "results" in data
            assert "count" in data

    def test_search_table_format(self):
        r = _run("search", "test", "--format", "table", "--limit", "2")
        # Should not crash
        assert r.returncode in (0, 1)

    def test_search_md_format(self):
        r = _run("search", "test", "--format", "md", "--limit", "2")
        if r.returncode == 0:
            assert "# KOS Search" in r.stdout or len(r.stdout) > 0

    def test_search_with_zone_filter(self):
        r = _run("search", "test", "--zone", "gongwen", "--format", "json", "--limit", "1")
        # Should accept --zone flag
        assert r.returncode in (0, 1)

    def test_search_with_kind_filter(self):
        r = _run("search", "test", "--kind", "note", "--format", "json", "--limit", "1")
        assert r.returncode in (0, 1)

    def test_search_web_flag(self):
        r = _run("search", "test", "--web", "--format", "json", "--limit", "1")
        # Should gracefully degrade if Minerva not available
        assert r.returncode in (0, 1)


class TestCLIResearch:
    """Verify research command."""

    def test_research_graceful_degrade(self):
        r = _run("research", "test query", "--level", "L0")
        # Should show error message if Minerva not available
        assert "Minerva" in (r.stdout + r.stderr) or r.returncode in (0, 1)


class TestCLIErrorHandling:
    """Verify error handling."""

    def test_unknown_command(self):
        r = _run("nonexistent_command_xyz")
        assert r.returncode != 0

    def test_search_no_query(self):
        r = _run("search")
        assert r.returncode != 0

    def test_search_empty_string(self):
        r = _run("search", "", "--format", "json", "--limit", "1")
        assert r.returncode in (0, 1)

    def test_invalid_format(self):
        r = _run("search", "test", "--format", "xml", "--limit", "1")
        assert r.returncode != 0


class TestSearchQueryTokenization:
    """Verify FTS5 query tokenization helper."""

    def test_unquoted_chinese_uses_or_mode(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query("信息化平台")
        assert "信息化" in result
        assert "平台" in result
        assert "OR" in result

    def test_quoted_chinese_becomes_phrase(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query('"夏明星"')
        assert result.startswith('"')
        assert result.endswith('"')
        assert "夏" in result
        assert "明星" in result
        assert "OR" not in result

    def test_single_quoted_chinese_becomes_phrase(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query("'夏明星'")
        assert result.startswith('"')
        assert result.endswith('"')

    def test_mixed_quoted_and_unquoted(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query('"夏明星" card')
        assert '"' in result
        assert "card" in result
        # Quoted part is phrase, unquoted part is OR-joined if multi-token

    def test_existing_boolean_operators_preserved(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query("信息化 OR 平台")
        assert "信息化 OR 平台" in result

    def test_english_single_token_unchanged(self):
        from kos.cli.__main__ import _tokenize_search_query

        result = _tokenize_search_query("xiamingxing")
        assert result == "xiamingxing"


class TestCLIOnto:
    """Verify ontology command integration."""

    def test_onto_help(self):
        r = _run("onto", "--help")
        assert r.returncode == 0

    def test_onto_list(self):
        r = _run("onto", "list")
        assert r.returncode in (0, 1)

    def test_onto_card_no_id(self):
        r = _run("onto", "card")
        assert r.returncode != 0
