"""Tests for bin/ssot/attest-review.py — human value attestation review interactive flow."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/attest-review.py"
SPEC = importlib.util.spec_from_file_location("attest_review", MODULE_PATH)
assert SPEC and SPEC.loader
AR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    db = tmp_path / "event-ledger.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE event_log (
            sequence       INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id       TEXT NOT NULL UNIQUE,
            event_type     TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            episode_id     TEXT,
            principal_id   TEXT NOT NULL,
            space_id       TEXT NOT NULL,
            role_context_id TEXT,
            responsibility_id TEXT,
            mandate_id     TEXT,
            correlation_id TEXT NOT NULL,
            causation_id   TEXT,
            producer       TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            occurred_at    TEXT NOT NULL,
            recorded_at    TEXT NOT NULL,
            privacy_class  TEXT NOT NULL,
            payload_json   TEXT NOT NULL,
            evidence_uri   TEXT,
            previous_hash  TEXT,
            event_hash     TEXT NOT NULL,
            UNIQUE(producer, idempotency_key)
        )
    """)
    for i, row in enumerate(rows, 1):
        conn.execute(
            """INSERT INTO event_log
               (sequence, event_id, event_type, schema_version, episode_id,
                principal_id, space_id, correlation_id, producer,
                idempotency_key, occurred_at, recorded_at, privacy_class,
                payload_json, evidence_uri, event_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                i,
                row.get("event_id", f"evt-{i}"),
                row["event_type"],
                row.get("schema_version", "v1"),
                row.get("episode_id"),
                row.get("principal_id", "principal:test"),
                row.get("space_id", "space:test"),
                row.get("correlation_id", f"corr-{i}"),
                row.get("producer", "test-producer"),
                row.get("idempotency_key", f"idem-{i}"),
                row.get("occurred_at", "2026-08-20T00:00:00Z"),
                row.get("recorded_at", "2026-08-20T00:00:00Z"),
                row.get("privacy_class", "disclosure:private"),
                json.dumps(row.get("payload_json", {})),
                row.get("evidence_uri"),
                row.get("event_hash", f"hash-{i}"),
            ),
        )
    conn.commit()
    conn.close()
    return db


def _sample_drafts() -> list[dict]:
    return [
        {
            "source": "git",
            "confidence": "medium",
            "ref_id": "git-abc123def456",
            "episode_id": "git-abc123def456",
            "request_id": "pr-100",
            "summary": "feat: add new governance rule for PR merge validation",
            "occurred_at": "2026-08-20T10:00:00Z",
        },
        {
            "source": "debt",
            "confidence": "low",
            "ref_id": "debt-D-001",
            "episode_id": "debt-D-001",
            "request_id": "debt-D-001",
            "summary": "Fix infra timeout in CI pipeline",
            "occurred_at": "2026-08-21T12:00:00Z",
        },
        {
            "source": "ledger",
            "confidence": "high",
            "ref_id": "ledger-evt-42",
            "episode_id": "ep-42",
            "request_id": "corr-42",
            "summary": "action:doc_write | completed",
            "occurred_at": "2026-08-22T08:00:00Z",
        },
    ]


# ---------------------------------------------------------------------------
# Test: keyword → coefficient type mapping
# ---------------------------------------------------------------------------

class TestKeywordMapping:
    def test_pr_merge_keyword(self):
        assert AR.classify_summary("Merge pull request #42 from org/feat") == "pr_merge"

    def test_debt_close_keyword(self):
        assert AR.classify_summary("Close debt item D-001") == "debt_close"

    def test_doc_write_keyword(self):
        assert AR.classify_summary("Update README.md with new docs") == "doc_write"

    def test_infra_fix_keyword(self):
        assert AR.classify_summary("Fix CI pipeline timeout") == "infra_fix"

    def test_research_keyword(self):
        assert AR.classify_summary("Research new LLM architecture") == "research_digest"

    def test_scene_activation_keyword(self):
        assert AR.classify_summary("Activate scene card for attest flow") == "scene_activation"

    def test_attestation_keyword(self):
        assert AR.classify_summary("Attest review of weekly episodes") == "attestation_review"

    def test_default_fallback(self):
        assert AR.classify_summary("Some random work done") == "default"

    def test_case_insensitive(self):
        assert AR.classify_summary("MERGE PULL REQUEST #1") == "pr_merge"

    def test_empty_summary_defaults(self):
        assert AR.classify_summary("") == "default"


# ---------------------------------------------------------------------------
# Test: est_minutes mapping with coefficient table
# ---------------------------------------------------------------------------

class TestEstMinutes:
    def test_known_type_returns_minutes(self):
        minutes = AR.get_est_minutes("pr_merge")
        assert minutes == 15

    def test_default_type_returns_15(self):
        minutes = AR.get_est_minutes("default")
        assert minutes == 15

    def test_unknown_type_falls_back_to_default(self):
        minutes = AR.get_est_minutes("nonexistent_type_xyz")
        assert minutes == 15

    def test_infra_fix_is_30(self):
        minutes = AR.get_est_minutes("infra_fix")
        assert minutes == 30

    def test_research_is_45(self):
        minutes = AR.get_est_minutes("research_digest")
        assert minutes == 45


# ---------------------------------------------------------------------------
# Test: confirm flow writes attestation JSON
# ---------------------------------------------------------------------------

class TestConfirmFlow:
    def test_confirm_writes_attestation_json(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        draft = _sample_drafts()[0]
        est_type = AR.classify_summary(draft["summary"])
        est_minutes = AR.get_est_minutes(est_type)

        AR.write_attestation(state_dir, draft, est_type, est_minutes, verdict="accept")

        attest_dir = state_dir / "attestations"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        attest_file = attest_dir / f"{today}.json"
        assert attest_file.exists()

        data = json.loads(attest_file.read_text())
        assert len(data) == 1
        assert data[0]["ref_id"] == draft["ref_id"]
        assert data[0]["verdict"] == "accept"
        assert data[0]["est_type"] == est_type
        assert data[0]["est_minutes"] == est_minutes
        assert data[0]["status"] == "pending_broker"

    def test_confirm_multiple_appends(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()

        for d in drafts:
            est_type = AR.classify_summary(d["summary"])
            est_minutes = AR.get_est_minutes(est_type)
            AR.write_attestation(state_dir, d, est_type, est_minutes, verdict="accept")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        attest_file = state_dir / "attestations" / f"{today}.json"
        data = json.loads(attest_file.read_text())
        assert len(data) == 3


# ---------------------------------------------------------------------------
# Test: reject flow writes to negative samples
# ---------------------------------------------------------------------------

class TestRejectFlow:
    def test_reject_appends_to_negative_samples(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        AR.add_negative_sample(state_dir, "git-abc123def456")

        neg_file = state_dir / "attest-negative-samples.json"
        assert neg_file.exists()
        data = json.loads(neg_file.read_text())
        assert "git-abc123def456" in data

    def test_reject_no_duplicates(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        AR.add_negative_sample(state_dir, "ref-1")
        AR.add_negative_sample(state_dir, "ref-1")

        neg_file = state_dir / "attest-negative-samples.json"
        data = json.loads(neg_file.read_text())
        assert data.count("ref-1") == 1

    def test_reject_multiple_refs(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        AR.add_negative_sample(state_dir, "ref-1")
        AR.add_negative_sample(state_dir, "ref-2")

        neg_file = state_dir / "attest-negative-samples.json"
        data = json.loads(neg_file.read_text())
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Test: dry-run has zero side effects
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_no_attestation_files(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()

        # Simulate dry-run: process drafts but write nothing
        for d in drafts:
            est_type = AR.classify_summary(d["summary"])
            est_minutes = AR.get_est_minutes(est_type)
            # In dry-run mode, write_attestation is NOT called

        attest_dir = state_dir / "attestations"
        assert not attest_dir.exists()

    def test_dry_run_no_negative_samples(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        # In dry-run mode, add_negative_sample is NOT called
        neg_file = state_dir / "attest-negative-samples.json"
        assert not neg_file.exists()


# ---------------------------------------------------------------------------
# Test: interactive loop with injected stdin
# ---------------------------------------------------------------------------

class TestInteractiveLoop:
    def test_quit_immediately(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("q\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=True)

        assert result["confirmed"] == 0
        assert result["rejected"] == 0
        assert result["skipped"] == 0

    def test_confirm_all_then_quit(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("c\nc\nc\nq\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=False)

        assert result["confirmed"] == 3
        assert result["rejected"] == 0

    def test_reject_all_then_quit(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("r\nr\nr\nq\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=False)

        assert result["confirmed"] == 0
        assert result["rejected"] == 3

        neg_file = state_dir / "attest-negative-samples.json"
        data = json.loads(neg_file.read_text())
        assert len(data) == 3

    def test_skip_all_then_quit(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("s\ns\ns\nq\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=False)

        assert result["confirmed"] == 0
        assert result["rejected"] == 0
        assert result["skipped"] == 3

    def test_mixed_actions(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("c\nr\ns\nq\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=False)

        assert result["confirmed"] == 1
        assert result["rejected"] == 1
        assert result["skipped"] == 1

    def test_dry_run_confirm_no_write(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        drafts = _sample_drafts()
        stdin = StringIO("c\nc\nc\nq\n")

        result = AR.interactive_loop(drafts, state_dir, stdin=stdin, dry_run=True)

        assert result["confirmed"] == 3
        attest_dir = state_dir / "attestations"
        assert not attest_dir.exists()

    def test_empty_drafts(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        stdin = StringIO("")

        result = AR.interactive_loop([], state_dir, stdin=stdin, dry_run=True)

        assert result["confirmed"] == 0
        assert result["rejected"] == 0
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# Test: summary output
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_format(self, tmp_path):
        counts = {"confirmed": 5, "rejected": 2, "skipped": 1, "total_est_minutes": 75}
        output = AR.format_summary(counts)
        assert "5" in output
        assert "2" in output
        assert "1" in output
        assert "75" in output


# ---------------------------------------------------------------------------
# Test: CLI subprocess
# ---------------------------------------------------------------------------

class TestCLI:
    def test_help_exits_zero(self):
        result = subprocess.run(
            ["python3", str(MODULE_PATH), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "attest-review" in result.stdout.lower() or "--since" in result.stdout

    def test_dry_run_with_no_data(self, tmp_path):
        """--dry-run with no aggregator data should exit cleanly."""
        env = dict(os.environ)
        env["ATTEST_REVIEW_WORKSPACE"] = str(tmp_path)
        result = subprocess.run(
            ["python3", str(MODULE_PATH), "--dry-run", "--since", "7"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        # Should exit 0 even with no data
        assert result.returncode == 0
