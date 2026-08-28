"""Tests for the fail-closed branch-protection promotion contract."""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "gac-branch-protection.sh"


def test_promotion_is_compare_and_swap_and_fail_closed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "--promote-gac-gate" in source
    assert "--rollback-gac-gate" in source
    assert "GAC_EXPECTED_PROTECTION_DIGEST" in source
    assert "If-Match" in source
    assert "expected-before" in source
    assert "required_status_checks" in source


def test_default_set_path_is_not_used_for_h1c() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    # H1c must use an explicit subcommand; the legacy default remains a
    # compatibility path and must not silently mutate live protection.
    assert 'cmd="${1:---set}"' in source
    assert "--promote-gac-gate" in source


def _normalized_protection(payload: dict) -> dict:
    reviews = payload.get("required_pull_request_reviews")
    review_payload = None
    if isinstance(reviews, dict):
        review_payload = {
            key: reviews[key]
            for key in (
                "required_approving_review_count",
                "dismiss_stale_reviews",
                "require_code_owner_reviews",
                "require_last_push_approval",
            )
            if key in reviews
        }
    status = payload.get("required_status_checks")
    status_payload = None if not isinstance(status, dict) else {
        "strict": bool(status.get("strict")),
        "contexts": list(status.get("contexts") or []),
    }
    restrictions = payload.get("restrictions")
    restrictions_payload = None if not isinstance(restrictions, dict) else {
        key: list(restrictions.get(key) or [])
        for key in ("users", "teams", "apps")
        if key in restrictions
    }

    def enabled(value: object) -> bool:
        return bool(value.get("enabled")) if isinstance(value, dict) else bool(value)

    result = {
        "required_pull_request_reviews": review_payload,
        "enforce_admins": enabled(payload.get("enforce_admins")),
        "required_status_checks": status_payload,
        "restrictions": restrictions_payload,
    }
    for key in (
        "required_linear_history",
        "allow_force_pushes",
        "allow_deletions",
        "block_creations",
        "required_conversation_resolution",
        "lock_branch",
        "allow_fork_syncing",
    ):
        if key in payload:
            result[key] = enabled(payload[key])
    return result


def _protection_digest(payload: dict) -> str:
    canonical = json.dumps(
        _normalized_protection(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _fake_gh(tmp_path: Path, protection: dict) -> tuple[Path, Path, str]:
    state_path = tmp_path / "protection.json"
    log_path = tmp_path / "puts.log"
    state_path.write_text(json.dumps(protection), encoding="utf-8")
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

state_path = Path(__import__('os').environ['FAKE_GH_STATE'])
log_path = Path(__import__('os').environ['FAKE_GH_LOG'])
args = sys.argv[1:]
if '-X' in args and args[args.index('-X') + 1] == 'PUT':
    payload_path = Path(args[args.index('--input') + 1])
    state_path.write_text(payload_path.read_text(encoding='utf-8'), encoding='utf-8')
    log_path.write_text(log_path.read_text(encoding='utf-8') + 'PUT\\n' if log_path.exists() else 'PUT\\n', encoding='utf-8')
    raise SystemExit(0)
payload = json.loads(state_path.read_text(encoding='utf-8'))
if '--include' not in args:
    print(json.dumps(payload))
    raise SystemExit(0)
print('HTTP/2.0 200 OK')
print('etag: "test-etag"')
print()
print(json.dumps(payload))
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    return fake_gh, log_path, _protection_digest(protection)


def test_promotion_only_adds_context_and_uses_cas(tmp_path: Path) -> None:
    protection = {
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
        },
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "strict": False,
            "contexts": ["phase-gate", "bet-done-transition"],
        },
        "restrictions": None,
        "required_linear_history": {"enabled": False},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
    }
    fake_gh, log_path, digest = _fake_gh(tmp_path, protection)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_GH_STATE": str(tmp_path / "protection.json"),
        "FAKE_GH_LOG": str(log_path),
        "GAC_BRANCH_PROTECTION_REPO": "test/repo",
    }
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--promote-gac-gate",
            "--expected-digest",
            digest,
            "--yes",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert log_path.read_text(encoding="utf-8") == "PUT\n"
    after = json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))
    assert _normalized_protection(after)["required_status_checks"]["contexts"] == [
        "phase-gate",
        "bet-done-transition",
        "gac-gate",
    ]
    before_normalized = _normalized_protection(protection)
    after_normalized = _normalized_protection(after)
    before_normalized["required_status_checks"]["contexts"].append("gac-gate")
    assert after_normalized == before_normalized


def test_expected_before_mismatch_does_not_put(tmp_path: Path) -> None:
    protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "strict": False,
            "contexts": ["phase-gate", "bet-done-transition"],
        },
        "restrictions": None,
    }
    _fake_gh(tmp_path, protection)
    log_path = tmp_path / "puts.log"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_GH_STATE": str(tmp_path / "protection.json"),
        "FAKE_GH_LOG": str(log_path),
        "GAC_BRANCH_PROTECTION_REPO": "test/repo",
    }
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--promote-gac-gate",
            "--expected-digest",
            "sha256:" + "0" * 64,
            "--yes",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 1
    assert not log_path.exists()


def test_check_reports_aligned_drift_and_unreadable(tmp_path: Path) -> None:
    protection = {
        "required_status_checks": {
            "strict": False,
            "contexts": ["phase-gate", "bet-done-transition"],
        }
    }
    fake_gh, _, _ = _fake_gh(tmp_path, protection)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_GH_STATE": str(tmp_path / "protection.json"),
        "FAKE_GH_LOG": str(tmp_path / "puts.log"),
        "GAC_BRANCH_PROTECTION_REPO": "test/repo",
    }

    drift = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert drift.returncode == 1

    env["GAC_CHECK_EXPECTED_CONTEXTS"] = "phase-gate,bet-done-transition"
    aligned = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert aligned.returncode == 0

    fake_gh.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    unreadable = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert unreadable.returncode == 2
