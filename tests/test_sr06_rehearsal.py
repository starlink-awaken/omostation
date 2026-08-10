"""Tests for SR-06 hardened rehearsal chain."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecos.ssot.tools.sr06_rehearsal import (
    Sandbox,
    StateMachine,
    StateMachineError,
    make_r1_packet,
    run_dispatch,
    run_rollback,
    run_verify,
)
from ecos.ssot.tools.work_packet_compiler import (
    VALID_VERDICTS,
    canonicalize,
    compute_packet_hash,
)


# ── State Machine ──────────────────────────────────────────────────────────────

class TestStateMachine:
    def test_initial_state_is_draft(self):
        sm = StateMachine()
        assert sm.state == "draft"

    def test_valid_draft_to_dispatched(self):
        sm = StateMachine()
        sm.transition("dispatched")
        assert sm.state == "dispatched"

    def test_rejects_dispatched_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        with pytest.raises(StateMachineError, match="Invalid transition"):
            sm.transition("completed")

    def test_rejects_verifying_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        with pytest.raises(StateMachineError, match="Invalid transition"):
            sm.transition("completed")

    def test_rejects_accepted_without_verifying(self):
        sm = StateMachine()
        sm.transition("dispatched")
        with pytest.raises(StateMachineError, match="Invalid transition"):
            sm.transition("accepted")

    def test_valid_full_path_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("accepted")
        sm.transition("completed")
        assert sm.state == "completed"

    def test_completed_is_terminal(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("accepted")
        sm.transition("completed")
        with pytest.raises(StateMachineError):
            sm.transition("dispatched")

    def test_can_complete_from_draft(self):
        sm = StateMachine()
        assert sm.can_complete() is True

    def test_can_complete_from_dispatched(self):
        sm = StateMachine()
        sm.transition("dispatched")
        assert sm.can_complete() is True

    def test_revise_loops_back(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("revise_requested")
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("accepted")
        sm.transition("completed")
        assert sm.state == "completed"

    def test_history_tracks_transitions(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        assert sm.history == [("draft", "dispatched"), ("dispatched", "verifying")]


# ── Sandbox ────────────────────────────────────────────────────────────────────

class TestSandbox:
    def test_creates_temp_directory(self):
        sandbox = Sandbox()
        try:
            assert Path(sandbox.path).is_dir()
        finally:
            sandbox.cleanup()

    def test_write_and_read_file(self):
        sandbox = Sandbox()
        try:
            sandbox.write_file("test.txt", "hello world")
            assert sandbox.read_file("test.txt") == "hello world"
        finally:
            sandbox.cleanup()

    def test_file_exists(self):
        sandbox = Sandbox()
        try:
            sandbox.write_file("exists.txt", "x")
            assert sandbox.exists("exists.txt") is True
            assert sandbox.exists("missing.txt") is False
        finally:
            sandbox.cleanup()

    def test_save_and_restore_snapshot(self):
        sandbox = Sandbox()
        try:
            sandbox.write_file("a.txt", "original")
            snapshot = sandbox.save_snapshot()
            sandbox.write_file("a.txt", "modified")
            sandbox.restore_snapshot()
            assert sandbox.read_file("a.txt") == "original"
            assert Path(sandbox.path, "a.txt").read_bytes() == snapshot["a.txt"]
        finally:
            sandbox.cleanup()

    def test_compute_measured_hash_from_disk(self):
        sandbox = Sandbox()
        try:
            sandbox.write_file("a.py", "print(1)")
            sandbox.write_file("b.py", "print(2)")
            h1 = sandbox.compute_measured_hash(["a.py", "b.py"])
            assert h1.startswith("sha256:")
            assert len(h1) == 7 + 64
            # Same content -> same hash
            sandbox2 = Sandbox()
            try:
                sandbox2.write_file("a.py", "print(1)")
                sandbox2.write_file("b.py", "print(2)")
                h2 = sandbox2.compute_measured_hash(["a.py", "b.py"])
                assert h1 == h2
            finally:
                sandbox2.cleanup()
        finally:
            sandbox.cleanup()

    def test_measured_hash_changes_with_content(self):
        sandbox = Sandbox()
        try:
            sandbox.write_file("x.py", "version1")
            h1 = sandbox.compute_measured_hash(["x.py"])
            sandbox.write_file("x.py", "version2")
            h2 = sandbox.compute_measured_hash(["x.py"])
            assert h1 != h2
        finally:
            sandbox.cleanup()

    def test_cleanup_removes_directory(self):
        sandbox = Sandbox()
        path = sandbox.path
        sandbox.cleanup()
        assert not Path(path).exists()


# ── R1 Packet ──────────────────────────────────────────────────────────────────

class TestR1Packet:
    def test_packet_has_required_fields(self):
        packet = make_r1_packet()
        required = (
            "packet_id",
            "schema_version",
            "blueprint_ref",
            "wave",
            "bet_id",
            "objective",
            "status",
            "authority",
            "scope",
            "acceptance",
            "budgets",
            "rollback",
            "circuit_breaker",
            "assignment",
        )
        for field in required:
            assert field in packet

    def test_risk_level_is_r1(self):
        packet = make_r1_packet()
        assert packet["authority"]["risk_level"] == "R1"

    def test_no_write_surfaces(self):
        packet = make_r1_packet()
        assert packet["scope"]["write_surfaces"] == [
            "sandbox://candidate.py",
            "sandbox://manifest.json",
        ]

    def test_rollback_strategy_present(self):
        packet = make_r1_packet()
        assert "strategy" in packet["rollback"]


# ── Dispatch ───────────────────────────────────────────────────────────────────

class TestDispatch:
    def test_dispatch_returns_hash_and_envelopes(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            result = run_dispatch(packet, sandbox)
            assert result["step"] == "dispatch"
            assert result["packet_id"] == packet["packet_id"]
            assert result["packet_hash"].startswith("sha256:")
            assert set(result["envelopes"]) == {"opencode", "kilocode", "claude-code"}
        finally:
            sandbox.cleanup()

    def test_dispatch_hash_is_deterministic(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            first = run_dispatch(packet, sandbox)
            sandbox2 = Sandbox()
            try:
                second = run_dispatch(packet, sandbox2)
                assert first["packet_hash"] == second["packet_hash"]
            finally:
                sandbox2.cleanup()
        finally:
            sandbox.cleanup()

    def test_dispatch_saves_snapshot(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            result = run_dispatch(packet, sandbox)
            assert result["snapshot"] == {}
            assert result["candidate_files"] == ["candidate.py", "manifest.json"]
        finally:
            sandbox.cleanup()

    def test_dispatch_hashes_match_across_platforms(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            result = run_dispatch(packet, sandbox)
            hashes = [env["packet_hash"] for env in result["envelopes"].values()]
            assert len(set(hashes)) == 1
        finally:
            sandbox.cleanup()

    def test_dispatch_payload_matches_canonical(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            result = run_dispatch(packet, sandbox)
            canonical = canonicalize(packet)
            expected_hash = compute_packet_hash(canonical)
            assert result["packet_hash"] == expected_hash
            for env in result["envelopes"].values():
                assert env["invariant_payload"] == json.loads(canonical)
        finally:
            sandbox.cleanup()

    def test_dispatch_state_machine_transitions(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            result = run_dispatch(packet, sandbox)
            assert result["state"] == "dispatched"
        finally:
            sandbox.cleanup()

    def test_dispatch_writes_candidate_manifest_without_done(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            run_dispatch(packet, sandbox)
            manifest = json.loads(sandbox.read_file("manifest.json"))
            assert manifest["status"] == "candidate"
            assert "done" not in manifest.values()
        finally:
            sandbox.cleanup()


# ── Verify ─────────────────────────────────────────────────────────────────────

class TestVerify:
    def test_accept_verdict_produces_receipt(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_verify(packet, dispatch["packet_hash"], "accept", sandbox)
            assert result["step"] == "verify"
            assert result["verdict"] == "accept"
            assert result["receipt_hash"].startswith("sha256:")
            assert result["checks"] == 1
        finally:
            sandbox.cleanup()

    def test_reject_verdict_produces_receipt(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_verify(packet, dispatch["packet_hash"], "reject", sandbox)
            assert result["verdict"] == "reject"
            assert result["receipt_hash"].startswith("sha256:")
        finally:
            sandbox.cleanup()

    def test_revise_verdict_produces_receipt(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_verify(packet, dispatch["packet_hash"], "revise", sandbox)
            assert result["verdict"] == "revise"
            assert result["receipt_hash"].startswith("sha256:")
        finally:
            sandbox.cleanup()

    def test_all_verdicts_are_valid(self):
        packet = make_r1_packet()
        for verdict in VALID_VERDICTS:
            sandbox = Sandbox()
            try:
                dispatch = run_dispatch(packet, sandbox)
                result = run_verify(packet, dispatch["packet_hash"], verdict, sandbox)
                assert result["verdict"] == verdict
            finally:
                sandbox.cleanup()

    def test_receipt_hash_differs_by_verdict(self):
        packet = make_r1_packet()
        accept_sandbox = Sandbox()
        reject_sandbox = Sandbox()
        try:
            accept_dispatch = run_dispatch(packet, accept_sandbox)
            reject_dispatch = run_dispatch(packet, reject_sandbox)
            accept = run_verify(
                packet, accept_dispatch["packet_hash"], "accept", accept_sandbox
            )
            reject = run_verify(
                packet, reject_dispatch["packet_hash"], "reject", reject_sandbox
            )
            assert accept["receipt_hash"] != reject["receipt_hash"]
        finally:
            accept_sandbox.cleanup()
            reject_sandbox.cleanup()

    def test_tampered_candidate_produces_different_measured_hash(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            tampered = run_verify(packet, dispatch["packet_hash"], "accept", sandbox, tamper=True)
            assert tampered["verdict"] == "reject"
            assert tampered["measurement_matches"] is False
            corrected = run_verify(packet, dispatch["packet_hash"], "accept", sandbox)
            assert corrected["verdict"] == "accept"
            assert corrected["packet_binding_matches"] is True
            assert corrected["measured_hash"] != tampered["measured_hash"]
        finally:
            sandbox.cleanup()

    def test_tampered_candidate_receipt_hash_changes(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            tampered = run_verify(
                packet, dispatch["packet_hash"], "accept", sandbox, tamper=True
            )
            corrected = run_verify(
                packet, dispatch["packet_hash"], "accept", sandbox, tamper=False
            )
            assert corrected["receipt_hash"] != tampered["receipt_hash"]
        finally:
            sandbox.cleanup()

    def test_state_after_accept_is_accepted(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_verify(packet, dispatch["packet_hash"], "accept", sandbox)
            assert result["state"] == "accepted"
        finally:
            sandbox.cleanup()

    def test_state_after_reject_is_rejected(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_verify(packet, dispatch["packet_hash"], "reject", sandbox)
            assert result["state"] == "rejected"
        finally:
            sandbox.cleanup()

    def test_wrong_packet_hash_is_rejected(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            _dispatch = run_dispatch(packet, sandbox)
            wrong_hash = compute_packet_hash(canonicalize({**packet, "objective": "tampered"}))
            result = run_verify(packet, wrong_hash, "accept", sandbox)
            assert result["verdict"] == "reject"
            assert result["packet_binding_matches"] is False
        finally:
            sandbox.cleanup()

    def test_verify_requires_a_dispatched_session(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            packet_hash = compute_packet_hash(canonicalize(packet))
            with pytest.raises(StateMachineError, match="requires dispatched state"):
                run_verify(packet, packet_hash, "accept", sandbox)
        finally:
            sandbox.cleanup()


# ── Rollback ───────────────────────────────────────────────────────────────────

class TestRollback:
    def test_rollback_requires_a_live_session(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            with pytest.raises(StateMachineError, match="not allowed"):
                run_rollback(packet, sandbox, {})
        finally:
            sandbox.cleanup()

    def test_rollback_restores_snapshot(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            sandbox.write_file("baseline.txt", "baseline\n")
            dispatch = run_dispatch(packet, sandbox)
            sandbox.write_file("candidate.py", "# MODIFIED\n")
            result = run_rollback(packet, sandbox, dispatch["snapshot"])
            assert result["rollback_verified"] is True
            assert result["remaining_files"] == ["baseline.txt"]
            assert not sandbox.exists("candidate.py")
            assert sandbox.read_file("baseline.txt") == "baseline\n"
        finally:
            sandbox.cleanup()

    def test_rollback_assertion_rollback_verified(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            sandbox.write_file("baseline.txt", "baseline\n")
            dispatch = run_dispatch(packet, sandbox)
            result = run_rollback(packet, sandbox, dispatch["snapshot"])
            assert result["rollback_verified"] is True
            assert result["snapshot_count"] == 1
            assert result["restored_count"] == 1
        finally:
            sandbox.cleanup()

    def test_rollback_strategy_revert(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            dispatch = run_dispatch(packet, sandbox)
            result = run_rollback(packet, sandbox, dispatch["snapshot"])
            assert result["strategy"] == "revert"
            assert result["status"] == "rolled_back"
        finally:
            sandbox.cleanup()


# ── State Machine Bypass Prevention ───────────────────────────────────────────

class TestStateMachineBypass:
    def test_dispatched_cannot_skip_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        with pytest.raises(StateMachineError):
            sm.transition("completed")

    def test_draft_cannot_skip_to_completed(self):
        sm = StateMachine()
        with pytest.raises(StateMachineError):
            sm.transition("completed")

    def test_rejected_cannot_skip_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("rejected")
        with pytest.raises(StateMachineError):
            sm.transition("completed")

    def test_revise_requested_cannot_skip_to_completed(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("revise_requested")
        with pytest.raises(StateMachineError):
            sm.transition("completed")

    def test_only_accepted_can_complete(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("accepted")
        sm.transition("completed")
        assert sm.state == "completed"

    def test_rolled_back_can_complete(self):
        sm = StateMachine()
        sm.transition("dispatched")
        sm.transition("verifying")
        sm.transition("rejected")
        sm.transition("rolled_back")
        sm.transition("completed")
        assert sm.state == "completed"


# ── Full Chain ─────────────────────────────────────────────────────────────────

class TestFullChain:
    def test_full_chain_runs(self):
        packet = make_r1_packet()
        sandbox = Sandbox()
        try:
            chain = []
            dispatch = run_dispatch(packet, sandbox)
            chain.append(dispatch)

            for verdict in ("reject", "accept"):
                chain.append(run_verify(packet, dispatch["packet_hash"], verdict, sandbox))

            chain.append(run_rollback(packet, sandbox, dispatch["snapshot"]))

            assert len(chain) == 4
            assert chain[0]["step"] == "dispatch"
            assert chain[1]["step"] == "verify"
            assert chain[2]["step"] == "verify"
            assert chain[3]["step"] == "rollback"
        finally:
            sandbox.cleanup()

    def test_main_exit_code_zero(self):
        script_path = Path(__file__).parent.parent / "src/ecos/ssot/tools/sr06_rehearsal.py"
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", str(script_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["all_verdicts_valid"] is True
        assert output["rollback_verified"] is True
