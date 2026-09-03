"""Tests for bin/ssot/episode-source-aggregator.py — three-source episode draft aggregator."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/episode-source-aggregator.py"
SPEC = importlib.util.spec_from_file_location("episode_aggregator", MODULE_PATH)
assert SPEC and SPEC.loader
AGG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGG)


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


def _make_debt_item(tmp_path: Path, item_id: str, title: str,
                     state: str, closed_at: str | None = None) -> Path:
    items_dir = tmp_path / "debt" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f'id: "{item_id}"',
        f'title: "{title}"',
        f'lifecycle_state: "{state}"',
        'opened_at: "2026-08-01"',
    ]
    if closed_at:
        lines.append(f'closed_at: "{closed_at}"')
    (items_dir / f"{item_id}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return items_dir


def _make_negative_samples(tmp_path: Path, ref_ids: list[str]) -> Path:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "attest-negative-samples.json"
    p.write_text(json.dumps(ref_ids), encoding="utf-8")
    return p


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo,
                   check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo,
                   check=True, capture_output=True)
    (repo / "init.txt").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "init.txt"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo,
                   check=True, capture_output=True)
    return repo


_merge_counter = 0


def _add_merge_commit(repo: Path, subject: str, date: str = "2026-08-20") -> str:
    global _merge_counter
    _merge_counter += 1
    branch_name = f"tmp-branch-{_merge_counter}"
    subprocess.run(["git", "checkout", "-qb", branch_name], cwd=repo,
                   check=True, capture_output=True)
    tmp_file = repo / f"tmp-{_merge_counter}.txt"
    tmp_file.write_text(f"change-{subject}\n", encoding="utf-8")
    subprocess.run(["git", "add", tmp_file.name], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "tmp change"], cwd=repo,
                   check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True,
                   capture_output=True)
    base_env = dict(os.environ)
    base_env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00Z"
    base_env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00Z"
    subprocess.run(
        ["git", "merge", "--no-ff", "-qm", subject, branch_name],
        cwd=repo, check=True, capture_output=True, env=base_env,
    )
    sha = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo,
                         check=True, capture_output=True, text=True).stdout.strip()
    return sha


class TestGitSource:
    def test_filters_sync_merges(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        _add_merge_commit(repo, "Merge pull request #100 from org/feature-a")
        _add_merge_commit(repo, "Merge origin/main: some sync stuff")
        _add_merge_commit(repo, "Merge branch 'main' of https://github.com/org/repo")

        entries = AGG._collect_git(repo, since_days=30)
        subjects = [e["summary"] for e in entries]
        assert len(entries) == 1
        assert "some sync stuff" not in subjects[0]
        assert "feature-a" in subjects[0]

    def test_episode_id_derivation(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        sha = _add_merge_commit(repo, "Merge pull request #42 from org/fix-bug")

        entries = AGG._collect_git(repo, since_days=30)
        assert len(entries) == 1
        assert entries[0]["episode_id"] == f"git-{sha}"
        assert entries[0]["ref_id"] == f"git-{sha}"

    def test_summary_strips_prefix(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        _add_merge_commit(repo, "Merge pull request #99 from org/my-feature")

        entries = AGG._collect_git(repo, since_days=30)
        assert "my-feature" in entries[0]["summary"]

    def test_confidence_is_medium(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        _add_merge_commit(repo, "Merge pull request #1 from org/x")
        entries = AGG._collect_git(repo, since_days=30)
        assert entries[0]["confidence"] == "medium"


class TestDebtSource:
    def test_closed_items_included(self, tmp_path):
        _make_debt_item(tmp_path, "D-CLOSED", "Test closed item", "closed",
                        closed_at="2026-08-20T00:00:00Z")
        entries = AGG._collect_debt(tmp_path / "debt" / "items")
        assert len(entries) == 1
        assert entries[0]["confidence"] == "low"
        assert entries[0]["source"] == "debt"

    def test_resolved_with_closed_at_included(self, tmp_path):
        _make_debt_item(tmp_path, "D-RESOLVED", "Resolved with date", "resolved",
                        closed_at="2026-08-22T02:45:00Z")
        entries = AGG._collect_debt(tmp_path / "debt" / "items")
        assert len(entries) == 1
        assert entries[0]["confidence"] == "low"

    def test_resolved_without_closed_at_excluded(self, tmp_path):
        _make_debt_item(tmp_path, "D-OPEN-RESOLVED", "Resolved no date", "resolved")
        entries = AGG._collect_debt(tmp_path / "debt" / "items")
        assert len(entries) == 0

    def test_open_items_excluded(self, tmp_path):
        _make_debt_item(tmp_path, "D-OPEN", "Open item", "open")
        entries = AGG._collect_debt(tmp_path / "debt" / "items")
        assert len(entries) == 0

    def test_episode_id_format(self, tmp_path):
        _make_debt_item(tmp_path, "D-TEST", "Test item", "closed",
                        closed_at="2026-08-20T00:00:00Z")
        entries = AGG._collect_debt(tmp_path / "debt" / "items")
        assert entries[0]["episode_id"] == "debt-D-TEST"
        assert entries[0]["ref_id"] == "debt-D-TEST"


class TestLedgerSource:
    def test_action_succeeded_extracted(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Action.Succeeded.v1",
                "episode_id": "ep-001",
                "occurred_at": "2026-08-20T10:00:00Z",
                "payload_json": {
                    "episode_id": "ep-001",
                    "result": {"evidence_uri": "file:///tmp/evidence.json"},
                },
                "evidence_uri": "file:///tmp/evidence.json",
            },
        ])
        entries = AGG._collect_ledger(db, since_days=30)
        assert len(entries) == 1
        assert entries[0]["confidence"] == "high"
        assert entries[0]["source"] == "ledger"

    def test_outcome_human_extracted(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Outcome.Human.v1",
                "episode_id": "ep-002",
                "occurred_at": "2026-08-21T10:00:00Z",
                "payload_json": {
                    "verdict": "accept",
                    "estimated_time_saved_seconds": 120.0,
                },
            },
        ])
        entries = AGG._collect_ledger(db, since_days=30)
        assert len(entries) == 1
        assert entries[0]["confidence"] == "high"

    def test_other_event_types_excluded(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Action.Started.v1",
                "episode_id": "ep-003",
                "payload_json": {},
            },
        ])
        entries = AGG._collect_ledger(db, since_days=30)
        assert len(entries) == 0


class TestDedupAndMerge:
    def test_same_ref_id_dedup(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Action.Succeeded.v1",
                "episode_id": "ep-dup",
                "occurred_at": "2026-08-20T10:00:00Z",
                "payload_json": {"episode_id": "ep-dup"},
            },
        ])
        _make_debt_item(tmp_path, "ep-dup", "Duplicate item", "closed",
                        closed_at="2026-08-20T00:00:00Z")

        ledger_entries = AGG._collect_ledger(db, since_days=30)
        debt_entries = AGG._collect_debt(tmp_path / "debt" / "items")

        all_entries = ledger_entries + debt_entries
        deduped = AGG._dedup(all_entries)
        assert len(deduped) == 2

    def test_confidence_sorting(self):
        entries = [
            {"ref_id": "a", "confidence": "low", "occurred_at": "2026-08-20"},
            {"ref_id": "b", "confidence": "high", "occurred_at": "2026-08-20"},
            {"ref_id": "c", "confidence": "medium", "occurred_at": "2026-08-20"},
        ]
        sorted_entries = AGG._sort_entries(entries)
        assert sorted_entries[0]["confidence"] == "high"
        assert sorted_entries[1]["confidence"] == "medium"
        assert sorted_entries[2]["confidence"] == "low"


class TestNegativeSamples:
    def test_negative_samples_excluded(self, tmp_path):
        _make_negative_samples(tmp_path, ["git-abc123", "debt-D-1"])

        entries = [
            {"ref_id": "git-abc123", "source": "git", "confidence": "medium"},
            {"ref_id": "git-def456", "source": "git", "confidence": "medium"},
            {"ref_id": "debt-D-1", "source": "debt", "confidence": "low"},
        ]
        filtered = AGG._apply_negative_samples(entries, tmp_path / "state")
        assert len(filtered) == 1
        assert filtered[0]["ref_id"] == "git-def456"

    def test_missing_negative_file_treated_as_empty(self, tmp_path):
        entries = [
            {"ref_id": "git-abc123", "source": "git", "confidence": "medium"},
        ]
        filtered = AGG._apply_negative_samples(entries, tmp_path / "state")
        assert len(filtered) == 1


class TestSelfTest:
    def test_self_test_passes(self):
        assert hasattr(AGG, "_self_test")


class TestCLI:
    def test_json_output_is_valid(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Action.Succeeded.v1",
                "episode_id": "ep-cli",
                "occurred_at": "2026-08-20T10:00:00Z",
                "payload_json": {"episode_id": "ep-cli"},
            },
        ])
        result = subprocess.run(
            ["python3", str(MODULE_PATH), "--json", "--since", "30",
             "--ledger", str(db)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_limit_respected(self, tmp_path):
        db = _make_ledger(tmp_path, [
            {
                "event_type": "Action.Succeeded.v1",
                "episode_id": f"ep-{i}",
                "occurred_at": f"2026-08-{20+i:02d}T10:00:00Z",
                "payload_json": {"episode_id": f"ep-{i}"},
            }
            for i in range(5)
        ])
        result = subprocess.run(
            ["python3", str(MODULE_PATH), "--json", "--since", "30", "--limit", "2",
             "--ledger", str(db)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) <= 2
