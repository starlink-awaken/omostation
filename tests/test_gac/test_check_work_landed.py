"""Tests for the G1.1 work-landed gate."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-work-landed.py"
_MODULE_NAME = "bin.check_work_landed"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _module
_SPEC.loader.exec_module(_module)

PR_RE = _module.PR_RE
SHA_RE = _module.SHA_RE
_parse_ts = _module._parse_ts
_extract_landing_refs = _module._extract_landing_refs
main = _module.main


# ── regex extraction ────────────────────────────────────────


def test_pr_regex_extracts_mentioned_pr_numbers():
    assert PR_RE.findall("see PR #521 and PR#522") == ["521", "522"]
    assert PR_RE.findall("issue#12 not a PR") == ["12"]  # #\d+ matches any
    assert PR_RE.findall("no refs here") == []


def test_sha_regex_extracts_hex_only():
    assert SHA_RE.findall("merged c79ef06cc") == ["c79ef06cc"]
    assert SHA_RE.findall("0123456789abcdef0123") == ["0123456789abcdef0123"]


# ── run yaml parsing ────────────────────────────────────────


def test_extract_landing_refs_finds_pr_and_sha():
    run = {
        "evidence": ["kairon cleanup landed (PR #521 merged c79ef06cc)"],
        "objective": "ship kairon pointer bump",
    }
    refs = _extract_landing_refs(run)
    assert "pr:521" in refs
    assert "sha:c79ef06cc" in refs


def test_extract_landing_refs_handles_empty_run():
    assert _extract_landing_refs({}) == set()
    assert _extract_landing_refs({"evidence": ["text only, no refs"]}) == set()


# ── timestamp parsing ──────────────────────────────────────


def test_parse_ts_handles_z_suffix():
    ts = _parse_ts("2026-07-28T07:19:47Z")
    assert ts is not None
    assert ts.tzinfo is not None


def test_parse_ts_returns_none_for_garbage():
    assert _parse_ts("") is None
    assert _parse_ts("not a date") is None


# ── main end-to-end with fixture ────────────────────────────


def _make_run_yaml(run_id: str, status: str, age_days: int, evidence: list[str]) -> dict:
    ts = (datetime.now(UTC) - timedelta(days=age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "run_id": run_id,
        "workflow_id": "project-code-change",
        "status": status,
        "agent_profile": "governance-agent",
        "objective": "fixture",
        "evidence": evidence,
        "created_at": ts,
        "updated_at": ts,
    }


def test_main_blocks_aged_run_without_landing_ref(tmp_path: Path, monkeypatch, capsys):
    # Land-lost run: closed 30 days ago, no PR ref. Must BLOCK.
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "lost.yaml").write_text(
        "run_id: 20260101T000000Z-project-code-change-stale\n"
        "workflow_id: project-code-change\n"
        "status: ok\n"
        "agent_profile: governance-agent\n"
        "objective: stranded run, no PR ref\n"
        "evidence:\n"
        "- stranded work, no landing yet\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed", "--unconditional", "--window-days", "365"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 1, captured.out
    assert "FAIL" in captured.out
    assert "blocking" in captured.out
    assert "20260101T000000Z-project-code-change-stale" in captured.out


def test_main_passes_for_run_with_landed_pr(tmp_path: Path, monkeypatch, capsys):
    # Use a real PR number that has been merged to origin/main.
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "fresh.yaml").write_text(
        "run_id: 20260727T100000Z-project-code-change-fresh\n"
        "workflow_id: project-code-change\n"
        "status: ok\n"
        "agent_profile: governance-agent\n"
        "objective: shipped via PR #556\n"
        "evidence:\n"
        "- merged in PR #556 (commit be0575690)\n"
        "created_at: '2026-07-27T10:00:00Z'\n"
        "updated_at: '2026-07-27T10:00:00Z'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0, captured.out
    assert "PASS" in captured.out


def test_main_passes_for_run_with_landed_sha(tmp_path: Path, monkeypatch, capsys):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "sha.yaml").write_text(
        "run_id: 20260727T100000Z-project-code-change-sha\n"
        "workflow_id: project-code-change\n"
        "status: ok\n"
        "agent_profile: governance-agent\n"
        "objective: landed via commit be0575690\n"
        "evidence:\n"
        "- merged in commit be0575690 (PR #556)\n"
        "created_at: '2026-07-27T10:00:00Z'\n"
        "updated_at: '2026-07-27T10:00:00Z'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed"])
    rc = main([])
    assert rc == 0

# --- BET landing fallback (2026-10-25) ---
# run's own landing refs (intermediate SHA / superseded PR) expire, the check
# used to flag 13 already-finished BETs as blocking -- the work landed via
# later PRs, whose refs live in main's commit messages (squash writes
# "title (#NNNN)"). The tests below pin the INVERSE criterion: loosening the
# fallback is the easiest way to turn this gate into "never alarms".


def _write_bet_run(runs_dir: Path, run_id: str, bet: str | None, sha: str) -> None:
    lines = [
        "run_id: " + run_id,
        "workflow_id: project-code-change",
        "status: ok",
        "agent_profile: governance-agent",
        "objective: fixture",
    ]
    if bet:
        lines.append("bet_id: " + bet)
    lines.extend([
        "evidence:",
        "- landed as " + sha,
        "created_at: '2026-01-01T00:00:00Z'",
        "updated_at: '2026-01-01T00:00:00Z'",
    ])
    (runs_dir / f"{run_id}.yaml").write_text(
        chr(10).join(lines) + chr(10), encoding="utf-8"
    )


def test_fake_bet_with_no_main_trace_stays_blocking(tmp_path: Path, monkeypatch, capsys):
    """BET id has no trace in main -> must stay blocking (fallback must not mask)."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    _write_bet_run(
        runs_dir,
        "20260101T000000Z-project-code-change-fakebet",
        "BET-Y2Q9-ZZZ-999",
        "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed", "--window-days", "365"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 1, captured.out
    assert "blocking" in captured.out


def test_nonexistent_bet_stays_blocking(tmp_path: Path, monkeypatch, capsys):
    """Fabricated BET -> still blocking."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    _write_bet_run(
        runs_dir,
        "20260101T000001Z-project-code-change-nobet",
        "BET-NOT-EXIST-12345",
        "cafecafecafecafecafecafecafecafecafe",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed", "--window-days", "365"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 1, captured.out
    assert "blocking" in captured.out


def test_run_without_bet_id_stays_blocking(tmp_path: Path, monkeypatch, capsys):
    """Run without bet_id never uses the fallback -> still blocking."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    _write_bet_run(
        runs_dir,
        "20260101T000003Z-project-code-change-nobetid",
        None,
        "2222222222222222222222222222222222222222",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed", "--window-days", "365"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 1, captured.out
    assert "blocking" in captured.out


def test_real_bet_with_main_commit_is_settled(tmp_path: Path, monkeypatch, capsys):
    """Real BET with commits in main -> settled (no longer a false positive)."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    # BET-Y2Q3-T9-01 has commits in origin/main (PR #4304), same as production history
    _write_bet_run(
        runs_dir,
        "20260101T000002Z-project-code-change-realbet",
        "BET-Y2Q3-T9-01",
        "1111111111111111111111111111111111111111",
    )
    monkeypatch.setattr(_module, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(sys, "argv", ["check-work-landed", "--window-days", "365"])
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0, captured.out
    assert "PASS" in captured.out


def test_bet_log_refs_extracts_pr_from_main():
    """_bet_log_refs pulls merged PR numbers out of main's commit messages."""
    refs = _module._bet_log_refs("BET-Y2Q3-T9-01")
    assert refs, "expected PR refs from origin/main commit messages"
    assert any(r.startswith("pr:") for r in refs)
