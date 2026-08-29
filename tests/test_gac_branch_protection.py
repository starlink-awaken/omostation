from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/gac/gac-branch-protection.sh"

BASE = {
    "required_status_checks": {
        "strict": False,
        "contexts": ["phase-gate", "bet-done-transition"],
    },
    "required_pull_request_reviews": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
    },
    "enforce_admins": {"enabled": True},
    "restrictions": {
        "users": [{"id": 11, "login": "alice"}],
        "teams": [{"id": 22, "slug": "release-team"}],
        "apps": [{"id": 33, "slug": "deploy-bot"}],
    },
    "required_linear_history": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "block_creations": {"enabled": False},
    "required_conversation_resolution": {"enabled": True},
    "lock_branch": {"enabled": False},
    "allow_fork_syncing": {"enabled": False},
}


def _fake_gh(tmp_path: Path, protection: dict | None = None) -> tuple[dict[str, str], Path, Path]:
    state = tmp_path / "state.json"
    writes = tmp_path / "writes.jsonl"
    gets = tmp_path / "gets.txt"
    calls = tmp_path / "calls.txt"
    race_marker = tmp_path / "race-result.txt"
    payload = json.loads(json.dumps(BASE if protection is None else protection))
    state.write_text(json.dumps(payload), encoding="utf-8")
    gets.write_text("0", encoding="utf-8")
    calls.write_text("", encoding="utf-8")
    fake = tmp_path / "gh"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

state_path=Path(os.environ['FAKE_PROTECTION_STATE'])
writes_path=Path(os.environ['FAKE_GH_WRITES'])
gets_path=Path(os.environ['FAKE_GH_GETS'])
calls_path=Path(os.environ['FAKE_GH_CALLS'])
race_marker=Path(os.environ['FAKE_GH_RACE_MARKER'])
args=sys.argv[1:]
if os.environ.get('FAKE_GH_UNREADABLE') == '1':
    raise SystemExit(2)
is_patch='-X' in args and args[args.index('-X')+1] == 'PATCH'
with calls_path.open('a', encoding='utf-8') as fh:
    fh.write(('PATCH' if is_patch else 'GET')+'\\n')

race_receipt=os.environ.get('FAKE_GH_RACE_RECEIPT')
if race_receipt and not race_marker.exists():
    try:
        fd=os.open(race_receipt, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    except FileExistsError:
        race_marker.write_text('blocked', encoding='utf-8')
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write('{"raced": true}')
        race_marker.write_text('created', encoding='utf-8')

if is_patch:
    if os.environ.get('FAKE_GH_PATCH_FAIL') == '1':
        raise SystemExit(7)
    input_path=args[args.index('--input')+1]
    patch=json.load(open(input_path, encoding='utf-8'))
    with writes_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(patch, sort_keys=True)+'\\n')
    response=json.loads(state_path.read_text(encoding='utf-8'))
    response['required_status_checks']={
        'strict': bool(patch['strict']),
        'contexts': list(patch['contexts']),
    }
    state_path.write_text(json.dumps(response), encoding='utf-8')
else:
    count=int(gets_path.read_text(encoding='utf-8'))
    gets_path.write_text(str(count+1), encoding='utf-8')
    if os.environ.get('FAKE_GH_GET_C_FAIL') == '1' and count >= 2:
        raise SystemExit(13)
    response=json.loads(state_path.read_text(encoding='utf-8'))
    if os.environ.get('FAKE_GH_RACE_AFTER_GET') == '1' and count >= 1:
        response['required_status_checks']['contexts'].append('concurrent-context')
        state_path.write_text(json.dumps(response), encoding='utf-8')
    if os.environ.get('FAKE_GH_DRIFT_AFTER_PATCH') == '1' and count >= 2:
        response['required_pull_request_reviews']['required_approving_review_count']=1
        state_path.write_text(json.dumps(response), encoding='utf-8')
    if os.environ.get('FAKE_GH_CHMOD_RECEIPT') == '1' and count >= 2:
        os.chmod(os.environ['FAKE_GH_CHMOD_RECEIPT'], 0)
    swap_receipt=os.environ.get('FAKE_GH_PATH_SWAP_RECEIPT')
    swap_victim=os.environ.get('FAKE_GH_PATH_SWAP_VICTIM')
    if swap_receipt and swap_victim and count >= 2 and not race_marker.exists():
        os.unlink(swap_receipt)
        os.symlink(swap_victim, swap_receipt)
        race_marker.write_text('swapped', encoding='utf-8')

request_id=os.environ.get('FAKE_GH_REQUEST_ID')
if request_id:
    print('x-github-request-id: '+request_id)
print(json.dumps(response if not is_patch else json.loads(state_path.read_text(encoding='utf-8'))))
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_PROTECTION_STATE": str(state),
        "FAKE_GH_WRITES": str(writes),
        "FAKE_GH_GETS": str(gets),
        "FAKE_GH_CALLS": str(calls),
        "FAKE_GH_RACE_MARKER": str(race_marker),
    }
    return env, state, writes


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_returns_zero_one_two(tmp_path: Path) -> None:
    env, state, _writes = _fake_gh(tmp_path)
    aligned = _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition")
    assert aligned.returncode == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"] = ["phase-gate"]
    state.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition").returncode == 1
    env["FAKE_GH_UNREADABLE"] = "1"
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition").returncode == 2


def test_check_rejects_yes_and_duplicate_yes(tmp_path: Path) -> None:
    env, _state, _writes = _fake_gh(tmp_path)
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition", "--yes").returncode == 2
    assert _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition", "--yes", "--yes").returncode == 2


def test_check_runs_with_oldest_available_system_python(tmp_path: Path) -> None:
    env, _state, _writes = _fake_gh(tmp_path)
    system_python = Path("/usr/bin/python3")
    if not system_python.exists():
        pytest.skip("/usr/bin/python3 is unavailable")
    env["PATH"] = f"{tmp_path}:/usr/bin:/bin"
    result = _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition")
    assert result.returncode == 0, result.stderr


def test_embedded_python_declares_future_annotations() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    embedded = source.split('python3 - "$@" <<\'PY\'', 1)[1]
    assert "from __future__ import annotations" in embedded.split("PY", 1)[0]


def test_add_context_expected_before_mismatch_performs_zero_patches(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate", "--receipt", str(receipt), "--yes")
    assert result.returncode != 0
    assert not writes.exists()
    assert not receipt.exists()


def test_missing_restrictions_is_treated_as_none(tmp_path: Path) -> None:
    protection = json.loads(json.dumps(BASE))
    protection.pop("restrictions")
    env, state, writes = _fake_gh(tmp_path, protection)
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 0, result.stderr
    assert writes.exists()
    assert json.loads(receipt.read_text(encoding="utf-8"))["before_digest"]


def test_add_context_preserves_object_restrictions_and_exact_network_sequence(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    before = json.loads(state.read_text(encoding="utf-8"))
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["GET", "GET", "PATCH", "GET"]
    patch = json.loads(writes.read_text(encoding="utf-8").splitlines()[0])
    assert set(patch) == {"strict", "contexts"}
    assert patch["strict"] is False
    assert sorted(patch["contexts"]) == ["bet-done-transition", "gac-gate", "phase-gate"]
    after = json.loads(state.read_text(encoding="utf-8"))
    assert after["required_status_checks"]["strict"] is False
    for key, value in before.items():
        if key != "required_status_checks":
            assert after[key] == value


def test_receipt_schema_mode_redaction_and_unproven_authority(tmp_path: Path) -> None:
    env, _state, _writes = _fake_gh(tmp_path)
    env["FAKE_GH_REQUEST_ID"] = "PRIVATE-REQUEST-ID"
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 0, result.stderr
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["schema"] == "gac-branch-protection-receipt/v1"
    assert payload["action"] == "add-required-context"
    assert payload["authorization_provenance"] == "UNPROVABLE"
    assert "human_authorization" not in payload
    assert "gh_request_ids" not in payload
    receipt_text = receipt.read_text(encoding="utf-8")
    assert "PRIVATE-REQUEST-ID" not in receipt_text
    assert "alice" not in receipt_text
    assert "release-team" not in receipt_text
    assert "deploy-bot" not in receipt_text
    assert receipt.stat().st_mode & 0o777 == 0o600


def test_receipt_reservation_blocks_path_race_before_network_write(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    receipt = tmp_path / "receipt.json"
    env["FAKE_GH_RACE_RECEIPT"] = str(receipt)
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "race-result.txt").read_text(encoding="utf-8") == "blocked"
    assert writes.read_text(encoding="utf-8").count("\n") == 1
    assert json.loads(receipt.read_text(encoding="utf-8"))["schema"] == "gac-branch-protection-receipt/v1"


def test_get_c_non_context_drift_leaves_incomplete_incident_receipt(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    env["FAKE_GH_DRIFT_AFTER_PATCH"] = "1"
    env["FAKE_GH_REQUEST_ID"] = "PRIVATE-REQUEST-ID"
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 1
    assert writes.read_text(encoding="utf-8").count("\n") == 1
    incident = json.loads(receipt.read_text(encoding="utf-8"))
    assert incident["status"] == "incomplete"
    assert incident["patch_attempted"] is True
    assert incident["incident"]["type"] == "get-c-non-context-drift"
    assert incident["authorization_provenance"] == "UNPROVABLE"
    assert "PRIVATE-REQUEST-ID" not in receipt.read_text(encoding="utf-8")


def test_path_substitution_never_overwrites_victim_and_leaves_sidecar(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    receipt = tmp_path / "receipt.json"
    victim = tmp_path / "victim.json"
    victim.write_text("victim-sentinel", encoding="utf-8")
    env["FAKE_GH_PATH_SWAP_RECEIPT"] = str(receipt)
    env["FAKE_GH_PATH_SWAP_VICTIM"] = str(victim)
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode != 0
    assert victim.read_text(encoding="utf-8") == "victim-sentinel"
    assert receipt.is_symlink()
    assert writes.read_text(encoding="utf-8").count("\n") == 1
    sidecar = Path(str(receipt) + ".incident")
    incident = json.loads(sidecar.read_text(encoding="utf-8"))
    assert incident["status"] == "incomplete"
    assert incident["incident"]["type"] == "receipt-path-identity-mismatch"


def test_post_patch_chmod_does_not_break_held_receipt_fd(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    receipt = tmp_path / "receipt.json"
    env["FAKE_GH_CHMOD_RECEIPT"] = str(receipt)
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 0, result.stderr
    assert json.loads(receipt.read_text(encoding="utf-8"))["schema"] == "gac-branch-protection-receipt/v1"
    assert not Path(str(receipt) + ".incident").exists()
    assert writes.read_text(encoding="utf-8").count("\n") == 1


def test_patch_failure_leaves_parseable_incomplete_receipts(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    env["FAKE_GH_PATCH_FAIL"] = "1"
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode != 0
    assert not writes.exists()
    incident = json.loads(receipt.read_text(encoding="utf-8"))
    sidecar = json.loads(Path(str(receipt) + ".incident").read_text(encoding="utf-8"))
    assert incident["status"] == sidecar["status"] == "incomplete"
    assert incident["incident"]["type"] == sidecar["incident"]["type"] == "patch-failed"


def test_get_c_api_failure_leaves_parseable_incomplete_receipts(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    env["FAKE_GH_GET_C_FAIL"] = "1"
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode != 0
    assert writes.read_text(encoding="utf-8").count("\n") == 1
    incident = json.loads(receipt.read_text(encoding="utf-8"))
    sidecar = json.loads(Path(str(receipt) + ".incident").read_text(encoding="utf-8"))
    assert incident["status"] == sidecar["status"] == "incomplete"
    assert incident["incident"]["type"] == sidecar["incident"]["type"] == "get-c-failed"


def test_missing_required_field_is_a_schema_error(tmp_path: Path) -> None:
    protection = json.loads(json.dumps(BASE))
    protection.pop("allow_deletions")
    env, _state, writes = _fake_gh(tmp_path, protection)
    result = _run(env, "--check", "--expected-contexts", "phase-gate,bet-done-transition")
    assert result.returncode == 2
    assert not writes.exists()


def test_failure_cleanup_does_not_override_exit_code_or_leak_temp_dir(tmp_path: Path) -> None:
    temp_root = tmp_path / "tmp"
    temp_root.mkdir()
    env, _state, writes = _fake_gh(tmp_path)
    env["TMPDIR"] = str(temp_root)
    env["FAKE_GH_RACE_AFTER_GET"] = "1"
    receipt = tmp_path / "receipt.json"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(receipt), "--yes")
    assert result.returncode == 1
    assert not writes.exists()
    assert list(temp_root.glob("gac-protection.*")) == []
    assert not receipt.exists()


def test_remove_context_removes_only_gac_gate(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"].append("gac-gate")
    state.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(env, "--remove-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition,gac-gate", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode == 0
    patch = json.loads(writes.read_text(encoding="utf-8").splitlines()[0])
    assert set(patch) == {"strict", "contexts"}
    assert sorted(patch["contexts"]) == ["bet-done-transition", "phase-gate"]


def test_unknown_extra_context_fails_closed(tmp_path: Path) -> None:
    env, state, writes = _fake_gh(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["required_status_checks"]["contexts"].append("unknown-context")
    state.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode != 0
    assert not writes.exists()


def test_second_read_change_stops_before_patch(tmp_path: Path) -> None:
    env, _state, writes = _fake_gh(tmp_path)
    env["FAKE_GH_RACE_AFTER_GET"] = "1"
    result = _run(env, "--add-required-context", "gac-gate", "--expected-contexts", "phase-gate,bet-done-transition", "--receipt", str(tmp_path / "receipt.json"), "--yes")
    assert result.returncode != 0
    assert not writes.exists()
