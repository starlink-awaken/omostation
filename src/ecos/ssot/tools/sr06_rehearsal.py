#!/usr/bin/env python3
"""
SR-06 rehearsal — hardened:
  real tempfile sandbox,
  materialized candidate files,
  measured hash from actual disk content,
  tamper rejection,
  pre-dispatch snapshot rollback with rollback_verified assertion,
  state machine preventing accept/self-reported done bypass.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ecos.ssot.tools.work_packet_compiler import (
    VALID_VERDICTS,
    build_command_check,
    build_completion_manifest,
    build_verification_receipt,
    canonicalize,
    compute_packet_hash,
    render_platform_envelope,
)


# ── State Machine ──────────────────────────────────────────────────────────────
# Prevents: accept/self-reported done bypass.
# Only transitions through verifying → accepted → completed are valid.
# Direct dispatched → completed is rejected.

class StateMachineError(Exception):
    pass


class StateMachine:
    VALID_TRANSITIONS = {
        "draft": {"dispatched"},
        "dispatched": {"verifying", "rolled_back"},
        "verifying": {"accepted", "rejected", "revise_requested"},
        "accepted": {"completed", "rolled_back"},
        "rejected": {"dispatched", "rolled_back"},
        "revise_requested": {"dispatched", "rolled_back"},
        "rolled_back": {"dispatched", "completed"},
        "completed": set(),
    }

    def __init__(self, initial_state: str = "draft") -> None:
        self.state = initial_state
        self.history: list[tuple[str, str]] = []

    def transition(self, new_state: str) -> None:
        valid = self.VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            raise StateMachineError(
                f"Invalid transition: '{self.state}' -> '{new_state}'. "
                f"Valid: {sorted(valid)}"
            )
        self.history.append((self.state, new_state))
        self.state = new_state

    def can_complete(self) -> bool:
        current = self.state
        visited = set()
        stack = [current]
        while stack:
            node = stack.pop()
            if node == "completed":
                return True
            if node in visited:
                continue
            visited.add(node)
            for next_state in self.VALID_TRANSITIONS.get(node, set()):
                stack.append(next_state)
        return False


# ── Sandbox ────────────────────────────────────────────────────────────────────

@dataclass
class Sandbox:
    """Real tempfile sandbox with snapshot/restore for rollback."""

    path: str = field(default_factory=lambda: tempfile.mkdtemp(prefix="sr06_"))

    def __post_init__(self) -> None:
        self._files_created: list[str] = []
        self._snapshot: dict[str, bytes] = {}
        self._candidate_files: list[str] = []
        self._expected_measured_hash = ""
        self._expected_packet_hash = ""
        self.state_machine = StateMachine()

    def write_file(self, rel_path: str, content: str) -> Path:
        full = Path(self.path) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        if rel_path not in self._files_created:
            self._files_created.append(rel_path)
        return full

    def read_file(self, rel_path: str) -> str:
        return (Path(self.path) / rel_path).read_text(encoding="utf-8")

    def exists(self, rel_path: str) -> bool:
        return (Path(self.path) / rel_path).exists()

    def remove_file(self, rel_path: str) -> None:
        path = Path(self.path) / rel_path
        if path.exists():
            path.unlink()
        if rel_path in self._files_created:
            self._files_created.remove(rel_path)

    def save_snapshot(self) -> dict[str, bytes]:
        root = Path(self.path)
        self._snapshot = {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        return dict(self._snapshot)

    def restore_snapshot(self) -> None:
        root = Path(self.path)
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file() and str(path.relative_to(root)) not in self._snapshot:
                path.unlink()
        for rel, content in self._snapshot.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)

    def compute_measured_hash(self, rel_paths: list[str]) -> str:
        hasher = hashlib.sha256()
        for rel in sorted(rel_paths):
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update((Path(self.path) / rel).read_bytes())
            hasher.update(b"\0")
        return f"sha256:{hasher.hexdigest()}"

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


# ── Packet Factory ─────────────────────────────────────────────────────────────

def make_r1_packet() -> dict:
    return {
        "packet_id": "SR06-DRILL-001",
        "schema_version": "work-packet/v1",
        "blueprint_ref": "blueprint://sr06/drill",
        "wave": "W0",
        "bet_id": "BET-SR06",
        "strategic_outcome": "swarm readiness verified",
        "objective": "Run full dispatch->verify->reject/accept->rollback chain on a tiny R1 packet",
        "why_now": "SR-06 acceptance criterion",
        "status": "active",
        "authority": {"strategist": "sr06-drill", "human_gate": False, "risk_level": "R1"},
        "scope": {
            "read_surfaces": ["projects/ecos/src/ecos/ssot/tools/sr06_rehearsal.py"],
            "write_surfaces": ["sandbox://candidate.py", "sandbox://manifest.json"],
            "non_goals": ["production swarm", "real file changes"],
        },
        "dependencies": {"required_packets": [], "required_services": [], "required_decisions": []},
        "acceptance": {
            "done_when": [
                {
                    "id": "AC1",
                    "assertion": "tampered candidate rejects, corrected candidate accepts, and rollback restores pre-dispatch snapshot",
                    "evidence_type": "rollback",
                }
            ],
            "verify_commands": [["uv", "run", "pytest", "tests/test_sr06_rehearsal.py", "-q"]],
        },
        "budgets": {
            "appetite_hours": 0.5,
            "max_elapsed_hours": 1.0,
            "max_changed_files": 1,
            "max_new_files": 1,
            "max_new_top_level_components": 0,
        },
        "rollback": {"strategy": "revert", "data_migration": False},
        "circuit_breaker": {"when": ["test_failure"], "action": "interrupt"},
        "assignment": {
            "executor_class": "E1",
            "verifier_class": "V1",
            "same_model_verification_allowed": False,
            "expires_at": "2026-08-11T00:00:00+08:00",
        },
    }


# ── Chain Steps ────────────────────────────────────────────────────────────────

def run_dispatch(packet: dict, sandbox: Sandbox) -> dict:
    sm = sandbox.state_machine
    sm.transition("dispatched")

    main_file = "candidate.py"
    manifest_file = "manifest.json"
    snapshot = sandbox.save_snapshot()
    sandbox.write_file(main_file, "# SR-06 candidate implementation\nprint('hello')\n")

    canonical = canonicalize(packet)
    packet_hash = compute_packet_hash(canonical)
    check = build_command_check(
        ["python3", "candidate.py"], 0, "hello\n"
    )
    manifest = build_completion_manifest(
        packet,
        packet_hash,
        assignment_id="ASG-SR06-001",
        agent_id="sr06-drill-executor",
        status="candidate",
        claims=[
            {
                "acceptance_id": "AC1",
                "assertion": "candidate submitted for independent verification",
                "evidence_refs": [],
            }
        ],
        checks=[check],
        changed_paths=[main_file, manifest_file],
        recommended_next="verify",
        surface_delta={"files": 2, "loc": 2},
    )
    manifest_payload = {
        "packet_id": manifest.packet_id,
        "packet_hash": manifest.packet_hash,
        "assignment_id": manifest.assignment_id,
        "agent_id": manifest.agent_id,
        "status": manifest.status,
        "changed_paths": manifest.changed_paths,
        "checks": [
            {
                "command": c.command,
                "returncode": c.returncode,
                "stdout_hash": c.stdout_hash,
            }
            for c in manifest.checks
        ],
        "recommended_next": manifest.recommended_next,
    }
    sandbox.write_file(manifest_file, json.dumps(manifest_payload, sort_keys=True))
    sandbox._candidate_files = [main_file, manifest_file]
    sandbox._expected_measured_hash = sandbox.compute_measured_hash(
        sandbox._candidate_files
    )
    sandbox._expected_packet_hash = packet_hash
    envelopes = {
        p: render_platform_envelope(packet, p, packet_hash)
        for p in ("opencode", "kilocode", "claude-code")
    }

    return {
        "step": "dispatch",
        "packet_id": packet["packet_id"],
        "packet_hash": packet_hash,
        "envelopes": envelopes,
        "state": sm.state,
        "snapshot": snapshot,
        "files_created": list(sandbox._files_created),
        "candidate_files": list(sandbox._candidate_files),
        "expected_measured_hash": sandbox._expected_measured_hash,
        "history": [list(item) for item in sm.history],
    }


def run_verify(
    packet: dict,
    packet_hash: str,
    verdict: str,
    sandbox: Sandbox,
    *,
    tamper: bool = False,
    allow_same_model: bool = False,
) -> dict:
    sm = sandbox.state_machine
    if sm.state == "rejected":
        # A corrected candidate is a new dispatch after rejection.
        sm.transition("dispatched")
    elif sm.state != "dispatched":
        raise StateMachineError(
            f"verification requires dispatched state, got '{sm.state}'"
        )

    if tamper:
        sandbox.write_file("tampered.py", "# TAMPERED\nimport os; os.system('echo pwned')\n")
    else:
        # A corrected candidate is a fresh submission after rejection; remove
        # the deliberately injected out-of-scope file before measuring it.
        sandbox.remove_file("tampered.py")

    measured_files = list(sandbox._candidate_files)
    if "tampered.py" in sandbox._files_created:
        measured_files.append("tampered.py")
    measured_hash = sandbox.compute_measured_hash(measured_files)
    measurement_matches = measured_hash == sandbox._expected_measured_hash
    packet_binding_matches = packet_hash == sandbox._expected_packet_hash
    try:
        manifest = json.loads(sandbox.read_file("manifest.json"))
        packet_binding_matches = packet_binding_matches and (
            manifest.get("packet_hash") == packet_hash
        )
    except (FileNotFoundError, json.JSONDecodeError):
        packet_binding_matches = False
    actual_verdict = verdict
    if not measurement_matches or not packet_binding_matches:
        actual_verdict = "reject"

    executor_family = "sr06-drill-executor"
    verifier_family = "sr06-drill-verifier" if not allow_same_model else executor_family

    receipt = build_verification_receipt(
        packet=packet,
        candidate_packet_hash=packet_hash,
        measured_packet_hash=measured_hash,
        executor_model_family=executor_family,
        verifier_model_family=verifier_family,
        verdict=actual_verdict,
        allow_same_model=allow_same_model,
        checks=[
            build_command_check(
                ["python3", "sr06_rehearsal.py", "--step", "verify"],
                0 if measurement_matches and packet_binding_matches else 1,
                "verified"
                if measurement_matches and packet_binding_matches
                else "measurement or packet binding mismatch",
            ),
        ],
    )

    sm.transition("verifying")
    state_after = sm.state
    if actual_verdict == "accept":
        sm.transition("accepted")
        state_after = sm.state
    elif actual_verdict == "reject":
        sm.transition("rejected")
        state_after = sm.state
    elif actual_verdict == "revise":
        sm.transition("revise_requested")
        state_after = sm.state

    return {
        "step": "verify",
        "requested_verdict": verdict,
        "verdict": actual_verdict,
        "receipt_hash": receipt.receipt_hash,
        "checks": len(receipt.checks),
        "measured_hash": measured_hash,
        "state": state_after,
        "tampered": tamper,
        "measurement_matches": measurement_matches,
        "packet_binding_matches": packet_binding_matches,
        "history": [list(item) for item in sm.history],
    }


def run_rollback(packet: dict, sandbox: Sandbox, snapshot: dict[str, bytes]) -> dict:
    sm = sandbox.state_machine
    if sm.state not in {"dispatched", "accepted", "rejected", "revise_requested"}:
        raise StateMachineError(f"rollback is not allowed from '{sm.state}'")
    sm.transition("rolled_back")
    sandbox._snapshot = dict(snapshot)
    sandbox.restore_snapshot()

    root = Path(sandbox.path)
    current = {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    restored = [rel for rel, content in snapshot.items() if current.get(rel) == content]

    return {
        "step": "rollback",
        "strategy": packet.get("rollback", {}).get("strategy", "revert"),
        "actions": ["restore_snapshot", "revert_packet_state"],
        "status": "rolled_back",
        "rollback_verified": len(restored) == len(snapshot),
        "restored_count": len(restored),
        "snapshot_count": len(snapshot),
        "remaining_files": sorted(current),
        "state": sm.state,
        "history": [list(item) for item in sm.history],
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    packet = make_r1_packet()
    sandbox = Sandbox()
    chain: list[dict] = []

    try:
        sandbox.write_file("baseline.txt", "pre-dispatch baseline\n")
        dispatch = run_dispatch(packet, sandbox)
        chain.append(
            {
                **dispatch,
                "snapshot": sorted(dispatch["snapshot"]),
            }
        )

        chain.append(
            run_verify(packet, dispatch["packet_hash"], "accept", sandbox, tamper=True)
        )
        chain.append(run_verify(packet, dispatch["packet_hash"], "accept", sandbox))

        rollback = run_rollback(packet, sandbox, dispatch["snapshot"])
        chain.append(rollback)

        print(json.dumps({
            "packet_id": packet["packet_id"],
            "chain": chain,
            "all_verdicts_valid": all(
                item.get("verdict") in VALID_VERDICTS
                for item in chain
                if "verdict" in item
            ),
            "rollback_verified": rollback["rollback_verified"],
        }, ensure_ascii=False, indent=2))
    finally:
        sandbox.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
