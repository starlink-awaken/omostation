"""Tests for omo audit subcommands (cards, vault, freshness)."""

from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import patch

from omo.omo_audit_cards import collect_metrics, find_card_db
from omo.omo_audit_freshness import check_debt_evidence, check_mof_version_bump
from omo.omo_audit_vault import audit_vault, content_hash, find_markdown_files


class TestAuditCards:
    """Tests for omo audit cards."""

    def test_find_card_db_returns_none_when_missing(self, tmp_path):
        """find_card_db returns None when no standard db exists."""
        with patch(
            "omo.omo_audit_cards.DEFAULT_DB_PATHS", [tmp_path / "nonexistent.db"]
        ), patch("omo.omo_audit_cards.WORKSPACE_ROOT", tmp_path):
            result = find_card_db()
            assert result is None

    def test_collect_metrics_returns_error_for_missing_db(self, tmp_path):
        """collect_metrics returns error dict for nonexistent db."""
        db_path = tmp_path / "nonexistent.db"
        result = collect_metrics(db_path)
        assert "error" in result
        assert result["stale"] == 1

    def test_collect_metrics_with_valid_db(self, tmp_path):
        """collect_metrics returns correct metrics for valid db."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                status TEXT,
                type TEXT,
                created_at TEXT
            )
        """)
        conn.execute(
            "INSERT INTO cards (status, type, created_at) VALUES ('active', 'task', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO cards (status, type, created_at) VALUES ('done', 'bug', '2026-06-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        result = collect_metrics(db_path)
        assert result["card_count"] == 2
        assert result["status_distribution"]["active"] == 1
        assert result["status_distribution"]["done"] == 1
        assert result["type_distribution"]["task"] == 1
        assert result["type_distribution"]["bug"] == 1
        assert result["mean_age_days"] > 0

    def test_cmd_cards_json_output(self, tmp_path, capsys):
        """cmd_cards outputs JSON when json_output=True."""
        from omo.omo_audit_cards import cmd_cards

        with patch("omo.omo_audit_cards.find_card_db", return_value=None):
            result = cmd_cards(json_output=True)
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert "error" in output
            assert result == 1


class TestAuditVault:
    """Tests for omo audit vault."""

    def test_content_hash_returns_sha256_prefix(self, tmp_path):
        """content_hash returns first 16 chars of SHA-256."""
        test_file = tmp_path / "test.md"
        test_file.write_text("hello world")
        result = content_hash(test_file)
        assert len(result) == 16
        assert result != "ERROR"

    def test_content_hash_returns_error_for_missing_file(self, tmp_path):
        """content_hash returns 'ERROR' for missing file."""
        test_file = tmp_path / "nonexistent.md"
        result = content_hash(test_file)
        assert result == "ERROR"

    def test_find_markdown_files_excludes_patterns(self, tmp_path):
        """find_markdown_files excludes standard patterns."""
        (tmp_path / "good.md").write_text("good")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "bad.md").write_text("bad")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "bad.md").write_text("bad")

        result = find_markdown_files(tmp_path)
        assert len(result) == 1
        assert result[0].name == "good.md"

    def test_audit_vault_returns_correct_structure(self, tmp_path):
        """audit_vault returns expected dict structure."""
        (tmp_path / "test.md").write_text("# Test")
        with patch("omo.omo_audit_vault.WORKSPACE_ROOT", tmp_path):
            result = audit_vault(tmp_path, days=90)
        assert "generated_at" in result
        assert "total_files" in result
        assert "stale_files" in result
        assert "results" in result
        assert result["total_files"] == 1


class TestAuditFreshness:
    """Tests for omo audit freshness."""

    def test_check_debt_evidence_returns_ok_when_no_dir(self, tmp_path):
        """check_debt_evidence returns ok when debt dir missing."""
        with patch("omo.omo_audit_freshness.OMO_ROOT", tmp_path):
            result = check_debt_evidence()
            assert result["status"] == "ok"
            assert result["stale"] == 0

    def test_check_debt_evidence_detects_stale_closed(self, tmp_path):
        """check_debt_evidence detects closed debt without evidence."""
        import yaml

        debt_dir = tmp_path / "debt" / "items"
        debt_dir.mkdir(parents=True)
        debt_file = debt_dir / "test.yaml"
        debt_file.write_text(
            yaml.dump(
                {
                    "id": "DEBT-001",
                    "lifecycle_state": "closed",
                    "resolution_evidence": "",
                }
            )
        )

        with patch("omo.omo_audit_freshness.OMO_ROOT", tmp_path):
            result = check_debt_evidence()
            assert result["status"] == "warning"
            assert result["stale"] == 1

    def test_check_mof_version_bump_returns_ok_for_recent(self, tmp_path):
        """check_mof_version_bump returns ok for recent version."""
        from datetime import UTC, datetime

        import yaml

        truth_dir = tmp_path / "_truth"
        truth_dir.mkdir()
        version_file = truth_dir / "mof-version.yaml"
        version_file.write_text(
            yaml.dump(
                {
                    "version": "0.0.108",
                    "history": [
                        {
                            "timestamp": datetime.now(UTC).isoformat(),
                            "version": "0.0.108",
                        }
                    ],
                }
            )
        )

        with patch("omo.omo_audit_freshness.OMO_ROOT", tmp_path):
            result = check_mof_version_bump()
            assert result["status"] == "ok"
            assert result["stale"] == 0


class TestAuditCLI:
    """Tests for omo audit CLI integration."""

    def test_audit_help(self):
        """omo audit --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "audit", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "X 审计工具集" in result.stdout

    def test_audit_cards_help(self):
        """omo audit cards --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "audit", "cards", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "CARDS X3" in result.stdout

    def test_audit_vault_help(self):
        """omo audit vault --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "audit", "vault", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Vault X1" in result.stdout

    def test_audit_freshness_help(self):
        """omo audit freshness --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "audit", "freshness", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "X2 freshness" in result.stdout

    def test_audit_unknown_subcommand(self):
        """omo audit unknown exits 1."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "audit", "unknown"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
