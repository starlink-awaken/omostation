"""Tests for WorkPacket Compiler."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ecos.ssot.tools.work_packet_compiler import (
    PLATFORMS,
    VALID_STATUSES,
    VALID_VERDICTS,
    CompletionManifest,
    VerificationReceipt,
    build_completion_manifest,
    build_verification_receipt,
    canonicalize,
    compute_packet_hash,
    detect_packet_changes,
    render_platform_envelope,
    build_command_check,
    stdout_hash,
)

# 固定输入保证稳定性
FIXED_PACKET = {
    "packet_id": "WP-TEST-001",
    "schema_version": "work-packet/v1",
    "blueprint_ref": "blueprint://test/001",
    "wave": "W1",
    "bet_id": "BET-TEST",
    "strategic_outcome": "outcome",
    "objective": "objective",
    "why_now": "because",
    "status": "active",
    "authority": {"strategist": "s1", "human_gate": False, "risk_level": "R1"},
    "scope": {
        "read_surfaces": ["src/"],
        "write_surfaces": ["src/"],
        "non_goals": ["nothing"],
    },
    "dependencies": {"required_packets": [], "required_services": [], "required_decisions": []},
    "acceptance": {
        "done_when": [{"id": "AC1", "assertion": "x", "evidence_type": "test_result"}],
        "verify_commands": [["pytest", "tests/"]],
    },
    "budgets": {
        "appetite_hours": 1.0,
        "max_elapsed_hours": 2.0,
        "max_changed_files": 5,
        "max_new_files": 3,
        "max_new_top_level_components": 1,
    },
    "rollback": {"strategy": "revert", "data_migration": False},
    "circuit_breaker": {"when": ["x"], "action": "interrupt"},
    "assignment": {
        "executor_class": "E1",
        "verifier_class": "V1",
        "same_model_verification_allowed": False,
        "expires_at": "2026-08-11T00:00:00+08:00",
    },
    "description": "desc",
    "tags": ["a"],
}


class TestCanonicalize:
    def test_deterministic(self):
        a = canonicalize(FIXED_PACKET)
        b = canonicalize(FIXED_PACKET)
        assert a == b

    def test_sorted_keys(self):
        data = {"packet_id": "WP-1", "objective": "x"}
        canonical = canonicalize(data)
        assert canonical == '{"objective":"x","packet_id":"WP-1"}'

    def test_none_excluded(self):
        data = {"a": 1, "b": None, "c": 2}
        canonical = canonicalize(data)
        assert "b" not in canonical

    def test_compact_separators(self):
        data = {"a": {"b": 1}}
        canonical = canonicalize(data)
        assert " " not in canonical
        assert "\n" not in canonical

    def test_non_contract_metadata_does_not_change_hash(self):
        base = canonicalize(FIXED_PACKET)
        changed = dict(FIXED_PACKET, description="a different description", tags=["new"])
        assert compute_packet_hash(base) == compute_packet_hash(canonicalize(changed))

    def test_schema_envelope_hashes_body(self):
        wrapped = {"m2_type": "WorkPacket", "WorkPacket": FIXED_PACKET}
        assert canonicalize(wrapped) == canonicalize(FIXED_PACKET)


class TestComputePacketHash:
    def test_prefix(self):
        h = compute_packet_hash("abc")
        assert h.startswith("sha256:")

    def test_length(self):
        h = compute_packet_hash("abc")
        assert len(h) == 7 + 64

    def test_hex(self):
        h = compute_packet_hash("abc")
        digest = h.split(":", 1)[1]
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic(self):
        a = compute_packet_hash("hello")
        b = compute_packet_hash("hello")
        assert a == b

    def test_different_inputs(self):
        a = compute_packet_hash("a")
        b = compute_packet_hash("b")
        assert a != b


class TestRenderPlatformEnvelope:
    def test_valid_platforms(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        for p in PLATFORMS:
            env = render_platform_envelope(FIXED_PACKET, p, p_hash)
            assert env["platform"] == p
            assert env["packet_hash"] == p_hash
            assert env["invariant_payload"] == json.loads(canonical)

    def test_invalid_platform(self):
        with pytest.raises(ValueError):
            render_platform_envelope(FIXED_PACKET, "unknown", "sha256:abc")

    def test_hash_identical_across_platforms(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        hashes = [render_platform_envelope(FIXED_PACKET, p, p_hash)["packet_hash"] for p in PLATFORMS]
        assert len(set(hashes)) == 1

    def test_payload_identical_across_platforms(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        payloads = [json.dumps(render_platform_envelope(FIXED_PACKET, p, p_hash)["invariant_payload"], sort_keys=True) for p in PLATFORMS]
        assert len(set(payloads)) == 1

    def test_envelope_is_deterministic_except_platform_label(self):
        p_hash = compute_packet_hash(canonicalize(FIXED_PACKET))
        first = render_platform_envelope(FIXED_PACKET, "opencode", p_hash)
        second = render_platform_envelope(FIXED_PACKET, "opencode", p_hash)
        assert first == second
        assert "rendered_at" not in first


class TestBuildCompletionManifest:
    def test_valid_statuses(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        for status in VALID_STATUSES:
            m = build_completion_manifest(
                packet=FIXED_PACKET,
                packet_hash=p_hash,
                assignment_id="ASG-1",
                agent_id="agent-1",
                status=status,
            )
            assert m.status == status

    def test_rejects_done(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        with pytest.raises(ValueError):
            build_completion_manifest(
                packet=FIXED_PACKET,
                packet_hash=p_hash,
                assignment_id="ASG-1",
                agent_id="agent-1",
                status="done",
            )

    def test_manifest_direct_construction_keeps_done_forbidden(self):
        with pytest.raises(ValueError, match="no 'done'"):
            CompletionManifest(
                packet_id="WP-TEST-001",
                packet_hash="sha256:" + "a" * 64,
                assignment_id="ASG-1",
                agent_id="agent-1",
                status="done",
            )

    def test_checks_missing_command_is_descriptive(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        checks = [{"returncode": 0, "stdout_hash": "sha256:" + "a" * 64}]
        with pytest.raises(ValueError, match="check.command"):
            build_completion_manifest(
                packet=FIXED_PACKET,
                packet_hash=p_hash,
                assignment_id="ASG-1",
                agent_id="agent-1",
                status="candidate",
                checks=checks,
            )

    def test_checks_stdout_hash(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        fake_digest = hashlib.sha256(b"fake stdout").hexdigest()
        checks = [{"command": ["pytest"], "returncode": 0, "stdout_hash": f"sha256:{fake_digest}"}]
        m = build_completion_manifest(
            packet=FIXED_PACKET,
            packet_hash=p_hash,
            assignment_id="ASG-1",
            agent_id="agent-1",
            status="candidate",
            checks=checks,
        )
        assert len(m.checks) == 1
        assert m.checks[0].stdout_hash.startswith("sha256:")

    def test_stdout_hash_helper_and_command_check(self):
        digest = stdout_hash("hello")
        assert digest == compute_packet_hash("hello")
        check = build_command_check(["echo", "hello"], 0, "hello")
        assert check["stdout_hash"] == digest

    def test_checks_invalid_stdout_hash(self):
        canonical = canonicalize(FIXED_PACKET)
        p_hash = compute_packet_hash(canonical)
        checks = [{"command": ["pytest"], "returncode": 0, "stdout_hash": "bad"}]
        with pytest.raises(ValueError):
            build_completion_manifest(
                packet=FIXED_PACKET,
                packet_hash=p_hash,
                assignment_id="ASG-1",
                agent_id="agent-1",
                status="candidate",
                checks=checks,
            )


class TestDetectPacketChanges:
    def test_no_change(self):
        res = detect_packet_changes(FIXED_PACKET, FIXED_PACKET)
        assert res["changed"] is False
        assert res["old_hash"] == res["new_hash"]

    def test_change_detected(self):
        new_packet = dict(FIXED_PACKET)
        new_packet["objective"] = "new"
        res = detect_packet_changes(FIXED_PACKET, new_packet)
        assert res["changed"] is True
        assert res["old_hash"] != res["new_hash"]

    def test_hashes_present(self):
        res = detect_packet_changes(FIXED_PACKET, FIXED_PACKET)
        assert res["old_hash"].startswith("sha256:")
        assert res["new_hash"].startswith("sha256:")


# ── SR-05 VerificationReceipt fixtures ──
_FAKE_HASH = "sha256:" + "a" * 64
_FAKE_HASH_2 = "sha256:" + "b" * 64


class TestBuildVerificationReceipt:
    """SR-05 receipt builder — success path and invariant enforcement."""

    def test_success_with_valid_inputs(self):
        receipt = build_verification_receipt(
            packet=FIXED_PACKET,
            candidate_packet_hash=_FAKE_HASH,
            measured_packet_hash=_FAKE_HASH,
            executor_model_family="claude-opus",
            verifier_model_family="codex-o3",
            verdict="accept",
            checks=[
                {"command": ["pytest", "-q"], "returncode": 0, "stdout_hash": _FAKE_HASH_2}
            ],
        )
        assert receipt.verdict == "accept"
        assert receipt.receipt_hash.startswith("sha256:")
        assert len(receipt.checks) == 1
        assert receipt.read_only is True
        assert receipt.direct_measurement is True

    def test_same_model_family_rejected_without_override(self):
        with pytest.raises(ValueError, match="model_family"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="claude-opus",
                verifier_model_family="claude-opus",
                verdict="accept",
            )

    def test_same_model_family_allowed_with_flag(self):
        receipt = build_verification_receipt(
            packet=FIXED_PACKET,
            candidate_packet_hash=_FAKE_HASH,
            measured_packet_hash=_FAKE_HASH,
            executor_model_family="claude-opus",
            verifier_model_family="claude-opus",
            verdict="accept",
            allow_same_model=True,
            checks=[{"command": ["pytest"], "returncode": 0, "stdout_hash": _FAKE_HASH_2}],
        )
        assert receipt.allow_same_model is True

    def test_rejects_non_read_only(self):
        with pytest.raises(ValueError, match="read_only"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="accept",
                read_only=False,
            )

    def test_rejects_non_direct_measurement(self):
        with pytest.raises(ValueError, match="direct_measurement"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="accept",
                direct_measurement=False,
            )

    def test_rejects_invalid_hash(self):
        with pytest.raises(ValueError, match="candidate_packet_hash"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash="bad",
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="accept",
            )

    def test_rejects_invalid_verdict(self):
        with pytest.raises(ValueError, match="verdict"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="done",
            )

    def test_deterministic_receipt_hash(self):
        kwargs = dict(
            packet=FIXED_PACKET,
            candidate_packet_hash=_FAKE_HASH,
            measured_packet_hash=_FAKE_HASH,
            executor_model_family="claude-opus",
            verifier_model_family="codex-o3",
            verdict="accept",
            checks=[{"command": ["pytest"], "returncode": 0, "stdout_hash": _FAKE_HASH_2}],
        )
        r1 = build_verification_receipt(**kwargs)
        r2 = build_verification_receipt(**kwargs)
        assert r1.receipt_hash == r2.receipt_hash

    def test_receipt_hash_changes_with_different_verdict(self):
        base = dict(
            packet=FIXED_PACKET,
            candidate_packet_hash=_FAKE_HASH,
            measured_packet_hash=_FAKE_HASH,
            executor_model_family="claude-opus",
            verifier_model_family="codex-o3",
            checks=[{"command": ["pytest"], "returncode": 0, "stdout_hash": _FAKE_HASH_2}],
        )
        r_accept = build_verification_receipt(**base, verdict="accept")
        r_revise = build_verification_receipt(**base, verdict="revise")
        assert r_accept.receipt_hash != r_revise.receipt_hash

    def test_rejects_empty_checks(self):
        with pytest.raises(ValueError, match="at least one command check"):
            build_verification_receipt(
                packet=FIXED_PACKET,
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="accept",
            )

    def test_direct_construction_enforces_invariants(self):
        """Even bypassing the builder, dataclass __post_init__ must reject."""
        with pytest.raises(ValueError, match="verdict"):
            VerificationReceipt(
                packet_id="WP-1",
                candidate_packet_hash=_FAKE_HASH,
                measured_packet_hash=_FAKE_HASH,
                executor_model_family="a",
                verifier_model_family="b",
                verdict="done",
            )
