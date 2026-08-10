"""W2-01 sovereignty — model, ID prefix, version, transition, isolation tests.

Covers: strict literal prefix IDs (``principal:`` / ``role:`` /
``responsibility:`` / ``assignment:``), validated immutable versioned models,
legal assign/revoke/replace state machine, stale-version rejection (including
reactivation), four-model monotonic versions, true duplicate behavior, and
Alice (family+career) / Bob (independent principal) isolation.  All writes go
through LedgerBroker.append via SovereigntyService; all queries replay from
the ledger.
"""

from __future__ import annotations

import json

import pytest

from omo.event_ledger.broker import DuplicateEventError, LedgerBroker
from omo.sovereignty import (
    EVT_ASSIGN,
    PRODUCER,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    IllegalTransitionError,
    InvalidIdError,
    Principal,
    Responsibility,
    Role,
    RoleAssignment,
    SovereigntyError,
    SovereigntyReplayError,
    SovereigntyService,
    StaleVersionError,
    generate_id,
    validate_id,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sovereignty.db"


@pytest.fixture()
def svc(db_path):
    service = SovereigntyService.open(db_path)
    yield service
    service._broker.close()


def _alice(svc: SovereigntyService):
    return svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["School pickup", "Meal prep"],
    )


# ---------------------------------------------------------------------------
# Strict literal prefix IDs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,good",
    [
        ("principal", "principal:alice"),
        ("principal", "principal:A-1_2"),
        ("role", "role:family-steward"),
        ("role", "role:career-engineer"),
        ("responsibility", "responsibility:school-pickup"),
        ("responsibility", "responsibility:r1"),
        ("assignment", generate_id("assignment")),
    ],
)
def test_valid_ids(kind, good):
    validate_id(kind, good)


@pytest.mark.parametrize(
    "kind,bad",
    [
        ("principal", "alice"),  # missing prefix
        ("principal", "role:alice"),  # wrong prefix
        ("principal", "principal:"),  # empty slug
        ("role", "principal:family"),  # wrong prefix
        ("role", "role:"),  # empty slug
        ("role", "role:fam ily"),  # space not allowed
        ("responsibility", "responsibility:"),  # empty slug
        ("responsibility", "school-pickup"),  # missing prefix
        ("assignment", "assignment:"),  # empty slug
        ("assignment", "rasg_abc"),  # wrong prefix
        ("principal", None),
        ("principal", 42),
    ],
)
def test_invalid_ids_rejected(kind, bad):
    with pytest.raises(InvalidIdError):
        validate_id(kind, bad)


def test_unknown_id_kind_raises():
    with pytest.raises(SovereigntyError):
        validate_id("bogus", "x_1")


def test_generate_id_has_prefix_and_unique():
    a = generate_id("assignment")
    b = generate_id("assignment")
    assert a.startswith("assignment:") and b.startswith("assignment:")
    assert a != b


# ---------------------------------------------------------------------------
# Models — validated, immutable, versioned
# ---------------------------------------------------------------------------


def test_responsibility_roundtrip():
    r = Responsibility(resp_id="responsibility:school-pickup", name="School pickup")
    assert r.to_dict() == {
        "resp_id": "responsibility:school-pickup",
        "name": "School pickup",
        "version": 1,
    }
    assert Responsibility.from_dict(r.to_dict()) == r


def test_role_roundtrip():
    role = Role(role_id="role:family-steward", name="Family Steward", scope="family")
    assert role.to_dict() == {
        "role_id": "role:family-steward",
        "name": "Family Steward",
        "scope": "family",
        "version": 1,
    }
    assert Role.from_dict(role.to_dict()) == role


def test_assignment_to_dict_shape(svc):
    assignment = _alice(svc)
    data = assignment.to_dict()
    assert data["assignment_id"].startswith("assignment:")
    assert data["principal_id"] == "principal:alice"
    assert data["role_id"] == "role:family-steward"
    assert data["version"] == 1
    assert data["status"] == STATUS_ACTIVE
    assert [r["name"] for r in data["responsibilities"]] == [
        "School pickup",
        "Meal prep",
    ]


def test_models_are_immutable():
    r = Responsibility(resp_id="responsibility:x", name="X")
    with pytest.raises(AttributeError):
        r.name = "Y"
    role = Role(role_id="role:x", name="X")
    with pytest.raises(AttributeError):
        role.scope = "bogus"


def test_model_validation_rejects_bad_ids():
    with pytest.raises(InvalidIdError):
        Responsibility(resp_id="school-pickup", name="School pickup")
    with pytest.raises(InvalidIdError):
        Role(role_id="family", name="Family")
    with pytest.raises(InvalidIdError):
        RoleAssignment(
            assignment_id="assignment:x",
            principal_id="alice",
            role_id="role:x",
            role_name="X",
            role_scope="",
        )


# ---------------------------------------------------------------------------
# State machine — assign
# ---------------------------------------------------------------------------


def test_assign_creates_active_v1(svc):
    assignment = _alice(svc)
    assert assignment.status == STATUS_ACTIVE
    assert assignment.version == 1


def test_assign_auto_generates_resp_ids(svc):
    assignment = _alice(svc)
    assert [r.resp_id for r in assignment.responsibilities] == [
        "responsibility:school-pickup",
        "responsibility:meal-prep",
    ]


def test_assign_while_active_is_illegal(svc):
    _alice(svc)
    with pytest.raises(IllegalTransitionError):
        _alice(svc)


def test_assign_invalid_ids_rejected_before_write(svc, db_path):
    with pytest.raises(InvalidIdError):
        svc.assign("alice", "role:family-steward")
    # Nothing was appended.
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 0


def test_assign_invalid_responsibility_id_rejected(svc):
    with pytest.raises(InvalidIdError):
        svc.assign(
            "principal:alice",
            "role:family-steward",
            responsibilities=[{"resp_id": "school-pickup", "name": "School pickup"}],
        )


# ---------------------------------------------------------------------------
# State machine — replace
# ---------------------------------------------------------------------------


def test_replace_bumps_version_and_updates_definition(svc):
    _alice(svc)
    updated = svc.replace(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward + Driver",
        responsibilities=["School pickup", "Meal prep", "Driving"],
    )
    assert updated.version == 2
    assert updated.status == STATUS_ACTIVE
    assert updated.role_name == "Family Steward + Driver"
    assert [r.name for r in updated.responsibilities] == [
        "School pickup",
        "Meal prep",
        "Driving",
    ]
    assert svc.query("principal:alice").assignments["role:family-steward"].version == 2


def test_replace_preserves_responsibilities_when_omitted(svc):
    """A replace that does not pass responsibilities must keep them (no data loss)."""
    _alice(svc)
    updated = svc.replace(
        "principal:alice", "role:family-steward", role_name="Renamed only"
    )
    assert updated.role_name == "Renamed only"
    assert [r.name for r in updated.responsibilities] == [
        "School pickup",
        "Meal prep",
    ]


def test_replace_with_stale_expected_version_rejected(svc, db_path):
    _alice(svc)
    with pytest.raises(StaleVersionError):
        svc.replace(
            "principal:alice",
            "role:family-steward",
            expected_version=5,  # current is 1
        )
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 1  # no event appended


def test_replace_with_correct_expected_version_ok(svc):
    _alice(svc)
    updated = svc.replace(
        "principal:alice",
        "role:family-steward",
        role_name="Renamed",
        expected_version=1,
    )
    assert updated.version == 2


def test_replace_absent_role_illegal(svc):
    with pytest.raises(IllegalTransitionError):
        svc.replace("principal:alice", "role:nonexistent", role_name="X")


def test_replace_revoked_role_illegal(svc):
    _alice(svc)
    svc.revoke("principal:alice", "role:family-steward")
    with pytest.raises(IllegalTransitionError):
        svc.replace("principal:alice", "role:family-steward", role_name="X")


# ---------------------------------------------------------------------------
# State machine — revoke
# ---------------------------------------------------------------------------


def test_revoke_bumps_version_and_marks_revoked(svc):
    _alice(svc)
    revoked = svc.revoke("principal:alice", "role:family-steward")
    assert revoked.status == STATUS_REVOKED
    assert revoked.version == 2
    principal = svc.query("principal:alice")
    assert principal.count == 0
    assert principal.role_ids == []
    assert principal.assignments["role:family-steward"].status == STATUS_REVOKED


def test_revoke_with_stale_version_rejected(svc, db_path):
    _alice(svc)
    with pytest.raises(StaleVersionError):
        svc.revoke("principal:alice", "role:family-steward", expected_version=9)
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 1


def test_revoke_absent_role_illegal(svc):
    with pytest.raises(IllegalTransitionError):
        svc.revoke("principal:alice", "role:nonexistent")


def test_revoke_revoked_role_illegal(svc):
    _alice(svc)
    svc.revoke("principal:alice", "role:family-steward")
    with pytest.raises(IllegalTransitionError):
        svc.revoke("principal:alice", "role:family-steward")


# ---------------------------------------------------------------------------
# Versions — four-model monotonic across the full lifecycle
# ---------------------------------------------------------------------------


def test_versions_strictly_monotonic_across_lifecycle(svc):
    a1 = _alice(svc)  # v1 active
    a2 = svc.replace("principal:alice", "role:family-steward", role_name="V2")  # v2
    a3 = svc.revoke("principal:alice", "role:family-steward")  # v3 revoked
    a4 = svc.assign(
        "principal:alice", "role:family-steward", role_name="Reactivated"
    )  # v4 active (reactivation)
    assert [a1.version, a2.version, a3.version, a4.version] == [1, 2, 3, 4]
    assert a4.status == STATUS_ACTIVE
    assert a4.assignment_id == a1.assignment_id  # same aggregate, version bumps


def test_four_model_monotonic_versions(svc):
    """Principal, Role, Responsibility and RoleAssignment version rules."""
    _alice(svc)
    svc.replace(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward + Driver",
        responsibilities=["School pickup", "Meal prep", "Driving"],
    )
    svc.revoke("principal:alice", "role:family-steward")
    a4 = svc.assign("principal:alice", "role:family-steward", role_name="Reactivated")

    state = svc.versions("principal:alice")

    # Principal: bumps on every principal mutation (4 mutations).
    assert state.principal.version == 4
    # RoleAssignment: bumps on every lifecycle mutation.
    assert state.assignments["role:family-steward"].version == 4
    assert a4.version == 4
    # Role: bumped by definition + replace + reactivation, NOT by revoke-only.
    assert state.roles["role:family-steward"].version == 3
    # Responsibility: version only changes when its same-ID definition changes.
    assert state.responsibilities["responsibility:school-pickup"].version == 1
    assert state.responsibilities["responsibility:meal-prep"].version == 1
    assert state.responsibilities["responsibility:driving"].version == 1


def test_responsibility_version_bumps_on_definition_change(svc):
    _alice(svc)
    svc.replace(
        "principal:alice",
        "role:family-steward",
        responsibilities=["School pickup", "Driving"],
    )
    # Same-ID definition change: school-pickup name unchanged (v1), driving new (v1).
    state = svc.versions("principal:alice")
    assert state.responsibilities["responsibility:school-pickup"].version == 1
    assert state.responsibilities["responsibility:driving"].version == 1

    # Now rename the same-ID responsibility: version must bump.
    svc.replace(
        "principal:alice",
        "role:family-steward",
        responsibilities=[
            {"resp_id": "responsibility:school-pickup", "name": "Carline"}
        ],
    )
    state = svc.versions("principal:alice")
    assert state.responsibilities["responsibility:school-pickup"].name == "Carline"
    assert state.responsibilities["responsibility:school-pickup"].version == 2


# ---------------------------------------------------------------------------
# Expected-version enforcement — stale mutations (reactivation included)
# ---------------------------------------------------------------------------


def test_reactivation_enforces_expected_version(svc, db_path):
    _alice(svc)
    svc.revoke("principal:alice", "role:family-steward")
    with pytest.raises(StaleVersionError):
        svc.assign(
            "principal:alice",
            "role:family-steward",
            role_name="Reactivated",
            expected_version=5,  # current is 2
        )
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 2  # no event appended

    a4 = svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Reactivated",
        expected_version=2,
    )
    assert a4.version == 3
    # Reactivation preserves responsibilities when none are passed.
    assert [r.name for r in a4.responsibilities] == ["School pickup", "Meal prep"]


def test_fresh_assign_rejects_expected_version_gt_zero(svc, db_path):
    with pytest.raises(StaleVersionError):
        svc.assign(
            "principal:alice",
            "role:family-steward",
            expected_version=1,  # fresh assign base is 0
        )
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 0


# ---------------------------------------------------------------------------
# Duplicate events are a real error, not a swallowed success
# ---------------------------------------------------------------------------


def test_duplicate_event_raises_not_swallowed(db_path):
    """Re-appending an identical (producer, idempotency_key) raises."""
    svc = SovereigntyService.open(db_path)
    try:
        _alice(svc)
        with LedgerBroker.connect(db_path) as broker:
            row = broker.read(producer=PRODUCER)[0]
            before = broker.count()
            with pytest.raises(DuplicateEventError):
                broker.append(
                    event_type=row["event_type"],
                    producer=row["producer"],
                    principal_id=row["principal_id"],
                    space_id=row["space_id"],
                    correlation_id="retry-correlation",
                    idempotency_key=row["idempotency_key"],
                    payload=json.loads(row["payload_json"]),
                )
            assert broker.count() == before
            # State is unchanged — no false success, no phantom event.
            assert svc.query("principal:alice").count == 1
    finally:
        svc._broker.close()


def test_service_duplicate_append_is_not_swallowed(db_path):
    """The service's append path propagates DuplicateEventError (no false success)."""
    svc = SovereigntyService.open(db_path)
    try:
        _alice(svc)  # appends idempotency key principal:alice|1 (principal-scoped)
        with pytest.raises(DuplicateEventError):
            svc._append_event(
                EVT_ASSIGN,
                {
                    "kind": "assign",
                    "assignment_id": "assignment:other",
                    "principal_id": "principal:alice",
                    "principal_name": "",
                    "principal_version": 1,  # same base → same key as _alice
                    "role_id": "role:family-steward",
                    "role_name": "Family Steward",
                    "role_scope": "",
                    "role_version": 1,
                    "responsibilities": [],
                    "version": 1,
                    "prev_version": 0,
                    "status": "active",
                },
            )
    finally:
        svc._broker.close()


# ---------------------------------------------------------------------------
# Alice (family + career) and Bob (independent principal) — isolation
# ---------------------------------------------------------------------------


def _alice_full(svc: SovereigntyService) -> None:
    svc.assign(
        "principal:alice",
        "role:family-steward",
        role_name="Family Steward",
        scope="family",
        responsibilities=["School pickup", "Meal prep"],
    )
    svc.assign(
        "principal:alice",
        "role:career-engineer",
        role_name="Engineer",
        scope="career",
        responsibilities=["Code review", "On-call"],
    )


def test_alice_multi_role_query(svc):
    _alice_full(svc)
    principal = svc.query("principal:alice")
    assert principal.count == 2
    assert principal.role_ids == ["role:career-engineer", "role:family-steward"]
    assert sorted(a.role_name for a in principal.assignments.values()) == [
        "Engineer",
        "Family Steward",
    ]


def test_bob_independent_principal_isolated(svc):
    _alice_full(svc)
    bob = svc.assign(
        "principal:bob",
        "role:tenant",
        role_name="Tenant",
        scope="housing",
        responsibilities=["Pay rent"],
    )
    assert bob.version == 1

    alice = svc.query("principal:alice")
    bob_view = svc.query("principal:bob")
    assert alice.count == 2
    assert bob_view.count == 1
    assert bob_view.role_ids == ["role:tenant"]
    assert alice.role_ids == ["role:career-engineer", "role:family-steward"]
    # Bob's assignments never leak into Alice's replay and vice versa.
    assert all(a.principal_id == "principal:alice" for a in alice.assignments.values())
    assert all(a.principal_id == "principal:bob" for a in bob_view.assignments.values())


def test_query_unknown_principal_is_empty(svc):
    _alice_full(svc)
    ghost = svc.query("principal:ghost")
    assert ghost.count == 0
    assert ghost.role_ids == []
    assert ghost.assignments == {}
    assert ghost.version == 0


def test_isolation_in_separate_databases(tmp_path):
    svc_a = SovereigntyService.open(tmp_path / "a.db")
    svc_b = SovereigntyService.open(tmp_path / "b.db")
    try:
        _alice_full(svc_a)
        assert svc_b.query("principal:alice").count == 0
    finally:
        svc_a._broker.close()
        svc_b._broker.close()


# ---------------------------------------------------------------------------
# Query determinism
# ---------------------------------------------------------------------------


def test_query_is_deterministic_across_calls(svc):
    _alice_full(svc)
    first = svc.query("principal:alice").to_dict()
    second = svc.query("principal:alice").to_dict()
    assert first == second


# ---------------------------------------------------------------------------
# Shared responsibility canonicalization across roles
# ---------------------------------------------------------------------------


def test_shared_responsibility_canonicalization(svc, db_path):
    """Two roles sharing one responsibility; rename through one role, then
    query/revoke/reactivate/omitted-replace on the other stays replayable.

    Responsibility is a Principal-scoped first-class aggregate.  An
    assignment's read model must resolve to the latest canonical snapshot,
    and omitted-responsibility mutations must write canonical definitions
    — never stale per-assignment snapshots.
    """
    # Both roles share responsibility:shared / "Old".
    svc.assign("principal:alice", "role:a", responsibilities=["Shared"])
    svc.assign("principal:alice", "role:b", responsibilities=["Shared"])

    # Rename through role:a → responsibility:shared becomes "New" / v2.
    svc.replace(
        "principal:alice",
        "role:a",
        responsibilities=[{"resp_id": "responsibility:shared", "name": "New"}],
    )

    # Query: both assignments must see the canonical New / v2.
    state = svc.versions("principal:alice")
    assert state.responsibilities["responsibility:shared"].name == "New"
    assert state.responsibilities["responsibility:shared"].version == 2
    for rid in ("role:a", "role:b"):
        asm = state.assignments[rid]
        assert len(asm.responsibilities) == 1
        assert asm.responsibilities[0].name == "New"
        assert asm.responsibilities[0].version == 2

    # Revoke role:b — stale snapshot would crash replay without canonicalization.
    svc.revoke("principal:alice", "role:b")

    # Reactivate role:b (responsibilities omitted → canonical).
    reactivated = svc.assign("principal:alice", "role:b")
    assert reactivated.responsibilities[0].name == "New"
    assert reactivated.responsibilities[0].version == 2

    # Omitted-responsibilities replace on role:b.
    svc.replace("principal:alice", "role:b", role_name="B Renamed")

    # Final query still consistent.
    state = svc.versions("principal:alice")
    assert state.responsibilities["responsibility:shared"].name == "New"
    assert state.responsibilities["responsibility:shared"].version == 2
    asm_b = state.assignments["role:b"]
    assert asm_b.role_name == "B Renamed"
    assert asm_b.responsibilities[0].name == "New"
    assert asm_b.responsibilities[0].version == 2

    # verify_chain green, one event per mutation (6 mutations).
    with LedgerBroker.connect(db_path) as broker:
        result = broker.verify_chain()
        assert result["ok"] is True
        assert broker.count() == 6


# ---------------------------------------------------------------------------
# Replay hardening — envelope/payload agreement and version-chain validation
# ---------------------------------------------------------------------------


def _valid_assign_payload(**overrides):
    payload = {
        "kind": "assign",
        "assignment_id": generate_id("assignment"),
        "principal_id": "principal:alice",
        "principal_name": "",
        "principal_version": 1,
        "role_id": "role:raw",
        "role_name": "role:raw",
        "role_scope": "",
        "role_version": 1,
        "responsibilities": [],
        "version": 1,
        "prev_version": 0,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def _inject_event(db_path, *, envelope_principal, payload, ik):
    """Append a raw sovereignty row via the broker (bypasses the service)."""
    with LedgerBroker.connect(db_path) as broker:
        broker.append(
            event_type=EVT_ASSIGN,
            producer=PRODUCER,
            principal_id=envelope_principal,
            space_id="sovereignty",
            correlation_id=f"inject-{ik}",
            idempotency_key=ik,
            payload=payload,
        )


def test_replay_rejects_envelope_payload_principal_mismatch(svc, db_path):
    """Payload principal_id must equal the envelope principal_id."""
    _alice(svc)
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(principal_id="principal:bob"),
        ik="mismatch-1",
    )
    # Alice's replay sees the row (envelope matches) and must fail loudly.
    with pytest.raises(SovereigntyReplayError) as exc_info:
        svc.query("principal:alice")
    assert exc_info.value.reason == "malformed_replay"
    # Bob must never see the leaked assignment (envelope filter excludes it).
    assert svc.query("principal:bob").count == 0
    assert svc.query("principal:bob").role_ids == []


def test_replay_rejects_principal_version_regression(svc, db_path):
    _alice(svc)  # principal_version 1
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            role_id="role:career-engineer", principal_version=5
        ),
        ik="pv-regression-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_prev_version_mismatch(svc, db_path):
    _alice(svc)  # assignment version 1
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="replace",
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=6,
            prev_version=5,  # previous assignment version is 1
            role_version=2,
        ),
        ik="prev-mismatch-1",
    )
    with pytest.raises(SovereigntyReplayError) as exc_info:
        svc.query("principal:alice")
    assert exc_info.value.reason == "malformed_replay"


def test_replay_rejects_assignment_version_regression(svc, db_path):
    _alice(svc)
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="replace",
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=3,  # must be prev_version + 1 = 2
            prev_version=1,
            role_version=2,
        ),
        ik="version-regression-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_assignment_id_instability(svc, db_path):
    _alice(svc)
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="replace",
            assignment_id="assignment:other",  # must stay stable
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=2,
            prev_version=1,
            role_version=2,
        ),
        ik="id-instability-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_role_version_not_bumped_on_replace(svc, db_path):
    _alice(svc)  # role version 1
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="replace",
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=2,
            prev_version=1,
            role_version=1,  # must bump to 2 on replace
        ),
        ik="role-version-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_role_version_changed_on_revoke(svc, db_path):
    _alice(svc)
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="revoke",
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            principal_version=2,
            version=2,
            prev_version=1,
            role_version=2,  # must stay at 1 on revoke
            status="revoked",
        ),
        ik="role-version-2",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_illegal_transition_assign_over_active(svc, db_path):
    _alice(svc)
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=2,
            prev_version=1,
            role_version=2,
        ),
        ik="illegal-assign-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


def test_replay_rejects_status_kind_mismatch(svc, db_path):
    _alice(svc)
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            role_id="role:career-engineer",
            status="revoked",  # assign must be active
        ),
        ik="status-kind-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


# ---------------------------------------------------------------------------
# Replay hardening — malformed responsibility items → stable failure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_responsibilities",
    [
        [{"name": "X", "version": 1}],  # missing resp_id
        [{"resp_id": "responsibility:x", "version": 1}],  # missing name
        [{"resp_id": "responsibility:x", "name": "X"}],  # missing version
        [
            {"resp_id": "responsibility:x", "name": "X", "version": "1"}
        ],  # non-int version
        [{"resp_id": "school-pickup", "name": "X", "version": 1}],  # invalid prefix
        [42],  # not an object
    ],
)
def test_replay_rejects_malformed_responsibility(svc, db_path, bad_responsibilities):
    _alice(svc)
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            role_id="role:career-engineer",
            responsibilities=bad_responsibilities,
        ),
        ik="bad-resp-1",
    )
    # Must be SovereigntyReplayError — never raw KeyError / InvalidIdError.
    with pytest.raises(SovereigntyReplayError) as exc_info:
        svc.query("principal:alice")
    assert exc_info.value.reason == "malformed_replay"


def test_replay_rejects_responsibility_rename_version_drift(svc, db_path):
    _alice(svc)  # responsibility:school-pickup v1 "School pickup"
    current = svc.current_assignment("principal:alice", "role:family-steward")
    _inject_event(
        db_path,
        envelope_principal="principal:alice",
        payload=_valid_assign_payload(
            kind="replace",
            assignment_id=current.assignment_id,
            role_id="role:family-steward",
            role_name="V2",
            principal_version=2,
            version=2,
            prev_version=1,
            role_version=2,
            responsibilities=[
                {
                    "resp_id": "responsibility:school-pickup",
                    "name": "Carline",
                    "version": 1,
                }
            ],  # rename must bump to 2
        ),
        ik="resp-rename-1",
    )
    with pytest.raises(SovereigntyReplayError):
        svc.query("principal:alice")


# ---------------------------------------------------------------------------
# Concurrent different-role mutations conflict on the principal version
# ---------------------------------------------------------------------------


def test_concurrent_different_role_principal_version_collision(svc, db_path):
    """Two mutations computed from the same principal base must collide.

    The idempotency key is scoped to ``principal_id|principal_version``, so a
    different-role mutation replayed from the same base (same new principal
    version) raises DuplicateEventError instead of persisting duplicate
    Principal versions.
    """
    _alice(svc)  # principal_version 1, idempotency key principal:alice|1
    with pytest.raises(DuplicateEventError):
        svc._append_event(
            EVT_ASSIGN,
            _valid_assign_payload(
                role_id="role:career-engineer",  # different role
                principal_version=1,  # same base → same key
                assignment_id="assignment:career",
            ),
        )
    # No duplicate principal version persisted; exactly one event remains.
    with LedgerBroker.connect(db_path) as broker:
        assert broker.count() == 1
    assert svc.query("principal:alice").version == 1
    assert svc.query("principal:alice").count == 1
