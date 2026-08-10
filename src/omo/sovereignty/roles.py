"""W2-01 Sovereignty — Principal / Role / Responsibility / RoleAssignment models.

Local-only sovereignty governance layer on top of the causal event ledger:

- Every write goes through :meth:`LedgerBroker.append` — no second write path.
- Every query replays the ledger for a single ``principal_id`` (events are
  appended with the affected principal as the envelope ``principal_id`` and
  filtered in Python, since the broker has no principal_id filter).
- Strict ID prefixes: ``principal:`` principals, ``role:`` roles,
  ``responsibility:`` responsibilities, ``assignment:`` role assignments.
- All four aggregates are validated, immutable (frozen) and versioned:
  ``Principal`` / ``Role`` / ``Responsibility`` / ``RoleAssignment``.
- Every mutation persists exactly ONE assignment-lifecycle event that carries
  the post-mutation snapshots of all four aggregates; deterministic replay
  reconstructs every aggregate and its version from the event log.

Version rules
-------------

- ``Principal``: increments on every principal mutation (assign / replace /
  revoke all touch the principal).
- ``Role``: increments on definition (first assign), reactivation (assign of a
  previously revoked role) and ``replace``; NOT incremented by ``revoke``.
- ``Responsibility``: increments only when its same-ID definition (name)
  changes; identical re-definitions keep the version.
- ``RoleAssignment``: increments on every lifecycle mutation.

Legal transitions per (principal_id, role_id) assignment::

    (none)    --assign--> active(v1)
    revoked   --assign--> active(v_next)      # reactivation, version bumps
    active    --replace--> active(v_next)     # definition update
    active    --revoke--> revoked(v_next)

Illegal: assign while active; replace/revoke while absent or revoked;
assign/replace/revoke with a stale ``expected_version`` (reactivation included).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from uuid import uuid4

from omo.event_ledger.broker import LedgerBroker

# ---------------------------------------------------------------------------
# Identity / event constants
# ---------------------------------------------------------------------------

PRODUCER = "omo-sovereignty"
SPACE_ID = "sovereignty"

EVT_ASSIGN = "Sovereignty.RoleAssigned.v1"
EVT_REPLACE = "Sovereignty.RoleReplaced.v1"
EVT_REVOKE = "Sovereignty.RoleRevoked.v1"

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"

#: Strict literal prefixes per aggregate kind (SSOT: BET-Y1Q2-T1-04).
_ID_PREFIXES: dict[str, str] = {
    "principal": "principal:",
    "role": "role:",
    "responsibility": "responsibility:",
    "assignment": "assignment:",
}
_ID_PATTERNS: dict[str, re.Pattern[str]] = {
    kind: re.compile(rf"^{prefix}[A-Za-z0-9][A-Za-z0-9_-]*$")
    for kind, prefix in _ID_PREFIXES.items()
}

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SovereigntyError(ValueError):
    """Base error for the sovereignty layer with a stable dispatch reason."""

    reason = "sovereignty_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidIdError(SovereigntyError):
    reason = "invalid_id"


class IllegalTransitionError(SovereigntyError):
    reason = "illegal_transition"


class StaleVersionError(SovereigntyError):
    reason = "stale_version"


class SovereigntyReplayError(SovereigntyError):
    """A sovereignty event row cannot be deterministically replayed.

    Raised instead of silently skipping malformed rows so operators get a
    stable domain failure instead of silent state corruption.
    """

    reason = "malformed_replay"


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------


def validate_id(kind: str, value: Any) -> None:
    """Enforce the strict ``<prefix><slug>`` shape for a sovereignty id."""
    pattern = _ID_PATTERNS.get(kind)
    if pattern is None:
        raise SovereigntyError(f"unknown id kind {kind!r}")
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise InvalidIdError(
            f"invalid {kind} id {value!r}: must match "
            f"{_ID_PREFIXES[kind]}<alnum/dash/underscore>"
        )


def generate_id(kind: str) -> str:
    """Generate a fresh strict-prefix id (12 hex chars of uuid4)."""
    if kind not in _ID_PREFIXES:
        raise SovereigntyError(f"unknown id kind {kind!r}")
    return f"{_ID_PREFIXES[kind]}{uuid4().hex[:12]}"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return slug or uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Models — validated, immutable, versioned
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Responsibility:
    """A single responsibility aggregate (id + name + monotonic version)."""

    resp_id: str
    name: str
    version: int = 1

    def __post_init__(self) -> None:
        validate_id("responsibility", self.resp_id)
        if self.version < 1:
            raise SovereigntyError(
                f"responsibility version must be >= 1, got {self.version}"
            )
        object.__setattr__(self, "name", self.name or self.resp_id)

    def to_dict(self) -> dict[str, Any]:
        return {"resp_id": self.resp_id, "name": self.name, "version": self.version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Responsibility:
        return cls(
            resp_id=data["resp_id"],
            name=data.get("name", data["resp_id"]),
            version=int(data.get("version", 1)),
        )


@dataclass(frozen=True)
class Role:
    """Role definition aggregate (id + name + scope + monotonic version)."""

    role_id: str
    name: str
    scope: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        validate_id("role", self.role_id)
        if self.version < 1:
            raise SovereigntyError(f"role version must be >= 1, got {self.version}")
        object.__setattr__(self, "name", self.name or self.role_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "scope": self.scope,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Role:
        return cls(
            role_id=data["role_id"],
            name=data.get("name", data["role_id"]),
            scope=data.get("scope", ""),
            version=int(data.get("version", 1)),
        )


@dataclass(frozen=True)
class RoleAssignment:
    """Assignment aggregate — a role bound to a principal, monotonic version."""

    assignment_id: str
    principal_id: str
    role_id: str
    role_name: str
    role_scope: str
    responsibilities: tuple[Responsibility, ...] = ()
    version: int = 1
    status: str = STATUS_ACTIVE

    def __post_init__(self) -> None:
        validate_id("assignment", self.assignment_id)
        validate_id("principal", self.principal_id)
        validate_id("role", self.role_id)
        if self.version < 1:
            raise SovereigntyError(
                f"assignment version must be >= 1, got {self.version}"
            )
        if self.status not in (STATUS_ACTIVE, STATUS_REVOKED):
            raise SovereigntyError(f"invalid assignment status {self.status!r}")
        object.__setattr__(self, "role_name", self.role_name or self.role_id)
        object.__setattr__(self, "responsibilities", tuple(self.responsibilities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "principal_id": self.principal_id,
            "role_id": self.role_id,
            "role_name": self.role_name,
            "role_scope": self.role_scope,
            "responsibilities": [r.to_dict() for r in self.responsibilities],
            "version": self.version,
            "status": self.status,
        }


@dataclass(frozen=True)
class Principal:
    """Principal aggregate; assignments keyed by role_id (replayed state)."""

    principal_id: str
    version: int = 0
    name: str = ""
    assignments: Mapping[str, RoleAssignment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id("principal", self.principal_id)
        if self.version < 0:
            raise SovereigntyError(
                f"principal version must be >= 0, got {self.version}"
            )
        object.__setattr__(
            self, "assignments", MappingProxyType(dict(self.assignments))
        )

    @property
    def count(self) -> int:
        """Number of active role assignments."""
        return sum(1 for a in self.assignments.values() if a.status == STATUS_ACTIVE)

    @property
    def role_ids(self) -> list[str]:
        """Sorted ids of active role assignments."""
        return sorted(
            a.role_id for a in self.assignments.values() if a.status == STATUS_ACTIVE
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "count": self.count,
            "assignments": [
                a.to_dict()
                for a in sorted(self.assignments.values(), key=lambda a: a.role_id)
            ],
            "role_ids": self.role_ids,
        }


@dataclass(frozen=True)
class SovereigntyState:
    """Deterministic replay of all four versioned aggregates for a principal."""

    principal: Principal
    roles: Mapping[str, Role]
    responsibilities: Mapping[str, Responsibility]
    assignments: Mapping[str, RoleAssignment]


# ---------------------------------------------------------------------------
# Responsibility normalization
# ---------------------------------------------------------------------------


def _normalize_responsibilities(value: Iterable[Any]) -> list[Responsibility]:
    """Normalize responsibility input into validated Responsibility objects.

    Accepted item shapes: :class:`Responsibility`, mapping (resp_id/name),
    or plain string (name → auto ``responsibility:<slug>`` id).  Duplicate
    resp_ids are dropped.  Responsibility ids always get strict validation.
    """
    result: list[Responsibility] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, Responsibility):
            validate_id("responsibility", item.resp_id)
            resp = item
        elif isinstance(item, dict):
            validate_id("responsibility", item.get("resp_id"))
            resp = Responsibility(
                resp_id=item["resp_id"],
                name=str(item.get("name", item["resp_id"])),
            )
        elif isinstance(item, str) and item.strip():
            resp = Responsibility(
                resp_id=f"responsibility:{_slugify(item)}", name=item.strip()
            )
        else:
            raise SovereigntyError(f"unsupported responsibility item {item!r}")
        if resp.resp_id in seen:
            continue
        seen.add(resp.resp_id)
        result.append(resp)
    return result


def _with_versions(
    registry: Mapping[str, Responsibility], resp_list: Iterable[Responsibility]
) -> list[Responsibility]:
    """Return responsibility snapshots with version numbers applied.

    A responsibility keeps its version when a same-ID definition (name) is
    re-persisted unchanged; any same-ID definition change (or a brand-new
    resp_id) bumps the version by one.
    """
    result: list[Responsibility] = []
    for resp in resp_list:
        prev = registry.get(resp.resp_id)
        if prev is not None and prev.name == resp.name:
            version = prev.version
        else:
            version = (prev.version if prev is not None else 0) + 1
        result.append(Responsibility(resp.resp_id, resp.name, version))
    return result


def _canonicalize(
    current: Iterable[Responsibility],
    registry: Mapping[str, Responsibility],
) -> list[Responsibility]:
    """Resolve each responsibility to its latest canonical snapshot.

    A Responsibility is a Principal-scoped first-class aggregate: when an
    assignment is revoked / reactivated / replaced without explicit new
    definitions, its read model must reflect the *current* canonical
    definition from the registry, not a stale snapshot frozen at the
    assignment's last mutation.
    """
    return [registry.get(r.resp_id, r) for r in current]


# ---------------------------------------------------------------------------
# Service — write via LedgerBroker.append, query by per-principal replay
# ---------------------------------------------------------------------------


class SovereigntyService:
    """Sovereignty operations over a causal event ledger.

    ``broker`` must be an already-connected :class:`LedgerBroker` (or the
    ``broker`` property of an :class:`EventLedgerSurface`).  All writes go
    through ``broker.append`` with producer ``omo-sovereignty``; all queries
    replay events filtered by principal_id.  Every mutation appends exactly
    one assignment-lifecycle event carrying the aggregate snapshots.
    """

    def __init__(self, broker: LedgerBroker) -> None:
        self._broker = broker

    @classmethod
    def open(cls, db_path: str | Any) -> SovereigntyService:
        return cls(LedgerBroker.connect(db_path))

    # -- write path --------------------------------------------------------

    def assign(
        self,
        principal_id: str,
        role_id: str,
        *,
        role_name: str | None = None,
        scope: str = "",
        responsibilities: Iterable[Any] | None = None,
        expected_version: int | None = None,
    ) -> RoleAssignment:
        """Assign ``role_id`` to ``principal_id`` (fresh or reactivation).

        Legal only when no active assignment exists for the (principal, role)
        pair.  Version becomes ``current_version + 1`` (1 on first assign).
        ``expected_version`` (when given) must equal the replayed current
        version (0 for a fresh assign) — stale versions are rejected.
        ``responsibilities=None`` means: empty for a fresh assign, preserved
        from the previous definition for a reactivation.
        """
        validate_id("principal", principal_id)
        validate_id("role", role_id)

        state = self._replay(principal_id)
        current = state.assignments.get(role_id)
        if current is not None and current.status == STATUS_ACTIVE:
            raise IllegalTransitionError(
                f"role {role_id} is already active for {principal_id}; use replace"
            )

        base_version = current.version if current is not None else 0
        if expected_version is not None and expected_version != base_version:
            raise StaleVersionError(
                f"stale version for {principal_id}/{role_id}: expected "
                f"{expected_version}, current {base_version}"
            )
        version = base_version + 1
        assignment_id = (
            current.assignment_id if current is not None else generate_id("assignment")
        )

        if responsibilities is None:
            resp_list = (
                _canonicalize(current.responsibilities, state.responsibilities)
                if current is not None
                else []
            )
        else:
            resp_list = _normalize_responsibilities(responsibilities)
        resp_snapshots = _with_versions(state.responsibilities, resp_list)

        role_version = (
            state.roles.get(role_id).version if role_id in state.roles else 0
        ) + 1
        payload: dict[str, Any] = {
            "kind": "assign",
            "assignment_id": assignment_id,
            "principal_id": principal_id,
            "principal_name": state.principal.name,
            "principal_version": state.principal.version + 1,
            "role_id": role_id,
            "role_name": role_name or (current.role_name if current else role_id),
            "role_scope": scope or (current.role_scope if current else ""),
            "role_version": role_version,
            "responsibilities": [r.to_dict() for r in resp_snapshots],
            "version": version,
            "prev_version": base_version,
            "status": STATUS_ACTIVE,
        }
        self._append_event(EVT_ASSIGN, payload)
        return self._build_assignment(payload, STATUS_ACTIVE)

    def replace(
        self,
        principal_id: str,
        role_id: str,
        *,
        role_name: str | None = None,
        scope: str | None = None,
        responsibilities: Iterable[Any] | None = None,
        expected_version: int | None = None,
    ) -> RoleAssignment:
        """Replace the definition of an active assignment (version bumps).

        Raises :class:`IllegalTransitionError` when the assignment is absent
        or revoked, and :class:`StaleVersionError` when ``expected_version``
        does not match the replayed current version.  ``responsibilities=None``
        preserves the existing responsibility list.
        """
        validate_id("principal", principal_id)
        validate_id("role", role_id)

        state = self._replay(principal_id)
        current = state.assignments.get(role_id)
        if current is None or current.status != STATUS_ACTIVE:
            raise IllegalTransitionError(
                f"role {role_id} is not active for {principal_id}; cannot replace"
            )
        if expected_version is not None and expected_version != current.version:
            raise StaleVersionError(
                f"stale version for {principal_id}/{role_id}: expected "
                f"{expected_version}, current {current.version}"
            )

        resp_list = (
            _canonicalize(current.responsibilities, state.responsibilities)
            if responsibilities is None
            else _normalize_responsibilities(responsibilities)
        )
        resp_snapshots = _with_versions(state.responsibilities, resp_list)

        version = current.version + 1
        role_version = (
            state.roles.get(role_id).version
            if role_id in state.roles
            else current.version
        ) + 1
        payload: dict[str, Any] = {
            "kind": "replace",
            "assignment_id": current.assignment_id,
            "principal_id": principal_id,
            "principal_name": state.principal.name,
            "principal_version": state.principal.version + 1,
            "role_id": role_id,
            "role_name": role_name or current.role_name,
            "role_scope": current.role_scope if scope is None else scope,
            "role_version": role_version,
            "responsibilities": [r.to_dict() for r in resp_snapshots],
            "version": version,
            "prev_version": current.version,
            "status": STATUS_ACTIVE,
        }
        self._append_event(EVT_REPLACE, payload)
        return self._build_assignment(payload, STATUS_ACTIVE)

    def revoke(
        self,
        principal_id: str,
        role_id: str,
        *,
        expected_version: int | None = None,
    ) -> RoleAssignment:
        """Revoke an active assignment (version bumps, status → revoked).

        The Role aggregate version is NOT bumped by a revoke-only mutation.
        Raises :class:`IllegalTransitionError` when the assignment is absent
        or already revoked, and :class:`StaleVersionError` on version drift.
        """
        validate_id("principal", principal_id)
        validate_id("role", role_id)

        state = self._replay(principal_id)
        current = state.assignments.get(role_id)
        if current is None or current.status != STATUS_ACTIVE:
            raise IllegalTransitionError(
                f"role {role_id} is not active for {principal_id}; cannot revoke"
            )
        if expected_version is not None and expected_version != current.version:
            raise StaleVersionError(
                f"stale version for {principal_id}/{role_id}: expected "
                f"{expected_version}, current {current.version}"
            )

        version = current.version + 1
        role_version = (
            state.roles.get(role_id).version
            if role_id in state.roles
            else current.version
        )
        payload: dict[str, Any] = {
            "kind": "revoke",
            "assignment_id": current.assignment_id,
            "principal_id": principal_id,
            "principal_name": state.principal.name,
            "principal_version": state.principal.version + 1,
            "role_id": role_id,
            "role_name": current.role_name,
            "role_scope": current.role_scope,
            "role_version": role_version,
            "responsibilities": [
                r.to_dict()
                for r in _canonicalize(current.responsibilities, state.responsibilities)
            ],
            "version": version,
            "prev_version": current.version,
            "status": STATUS_REVOKED,
        }
        self._append_event(EVT_REVOKE, payload)
        return self._build_assignment(payload, STATUS_REVOKED)

    # -- query path --------------------------------------------------------

    def query(self, principal_id: str) -> Principal:
        """Replay the ledger for ``principal_id`` and return current state."""
        validate_id("principal", principal_id)
        return self._replay(principal_id).principal

    def versions(self, principal_id: str) -> SovereigntyState:
        """Deterministically replay all four versioned aggregates."""
        validate_id("principal", principal_id)
        return self._replay(principal_id)

    def current_assignment(
        self, principal_id: str, role_id: str
    ) -> RoleAssignment | None:
        """Return the current (replayed) assignment, or None when absent."""
        validate_id("principal", principal_id)
        validate_id("role", role_id)
        return self._replay(principal_id).assignments.get(role_id)

    # -- internals ---------------------------------------------------------

    def _replay(self, principal_id: str) -> SovereigntyState:
        """Replay sovereignty events for one principal, by sequence.

        Every sovereignty row belonging to ``principal_id`` must be a valid
        assignment-lifecycle event; a malformed row raises
        :class:`SovereigntyReplayError` instead of being silently skipped.
        The persisted version chain is fully validated:

        - ``principal_version`` must be exactly previous + 1;
        - ``prev_version`` must equal the previous assignment version (or 0
          for a fresh assign);
        - the assignment ``version`` must be exactly ``prev_version + 1``;
        - ``assignment_id`` must remain stable across an assignment's
          lifecycle;
        - kind/status/legal transitions must agree (assign over active,
          replace/revoke on absent or revoked, status vs kind);
        - the Role version must increment on assign/reactivation/replace and
          remain unchanged on revoke;
        - a same-ID Responsibility keeps its version on an unchanged name and
          increments exactly one on a rename (new resp_ids start at 1).
        """
        principal_version = 0
        principal_name = ""
        roles: dict[str, Role] = {}
        responsibilities: dict[str, Responsibility] = {}
        assignments: dict[str, RoleAssignment] = {}
        rows = self._broker.read(producer=PRODUCER)
        for row in rows:
            if row.get("principal_id") != principal_id:
                continue
            sequence = row.get("sequence")
            payload = self._decode_event(row)
            kind = payload["kind"]
            role_id = payload["role_id"]
            status = payload["status"]
            event_version = int(payload["version"])
            prev_version = int(payload["prev_version"])
            event_principal_version = int(payload["principal_version"])
            event_role_version = int(payload["role_version"])

            # Principal aggregate version chain: exactly previous + 1.
            if event_principal_version != principal_version + 1:
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: principal "
                    f"version {event_principal_version} != previous + 1 "
                    f"({principal_version + 1})"
                )
            principal_version = event_principal_version

            previous = assignments.get(role_id)
            expected_prev = previous.version if previous is not None else 0
            if prev_version != expected_prev:
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: "
                    f"prev_version {prev_version} != previous assignment "
                    f"version {expected_prev} for {role_id}"
                )
            if event_version != prev_version + 1:
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: "
                    f"assignment version {event_version} != prev_version + 1 "
                    f"({prev_version + 1}) for {role_id}"
                )
            if (
                previous is not None
                and payload["assignment_id"] != previous.assignment_id
            ):
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: "
                    f"assignment_id changed for {role_id} (was "
                    f"{previous.assignment_id}, got {payload['assignment_id']})"
                )

            # Kind / status / legal transition agreement.
            if kind == "assign":
                if previous is not None and previous.status == STATUS_ACTIVE:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"assign over active assignment for {role_id}"
                    )
                if status != STATUS_ACTIVE:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"assign must carry status active, got {status!r}"
                    )
            elif kind == "replace":
                if previous is None or previous.status != STATUS_ACTIVE:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"replace on absent/revoked assignment for {role_id}"
                    )
                if status != STATUS_ACTIVE:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"replace must carry status active, got {status!r}"
                    )
            elif kind == "revoke":
                if previous is None or previous.status != STATUS_ACTIVE:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"revoke on absent/revoked assignment for {role_id}"
                    )
                if status != STATUS_REVOKED:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"revoke must carry status revoked, got {status!r}"
                    )

            # Role version rules: bump by exactly one on assign/reactivate/
            # replace; unchanged on revoke.
            previous_role_version = roles[role_id].version if role_id in roles else 0
            if kind == "revoke":
                if event_role_version != previous_role_version:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"role version changed on revoke "
                        f"({previous_role_version} -> {event_role_version})"
                    )
            elif event_role_version != previous_role_version + 1:
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: "
                    f"role version {event_role_version} != previous + 1 "
                    f"({previous_role_version + 1})"
                )

            # Responsibility version rules: new resp_id starts at 1; same-ID
            # unchanged name keeps the version; same-ID rename bumps exactly
            # one.  Missing/invalid items are a stable replay failure.
            resp_snapshots: list[Responsibility] = []
            for item in payload["responsibilities"]:
                resp = self._decode_responsibility(item, sequence)
                previous_resp = responsibilities.get(resp.resp_id)
                if previous_resp is None:
                    if resp.version != 1:
                        raise SovereigntyReplayError(
                            f"malformed sovereignty event at seq {sequence}: "
                            f"new responsibility {resp.resp_id} must start at "
                            f"version 1, got {resp.version}"
                        )
                elif previous_resp.name == resp.name:
                    if resp.version != previous_resp.version:
                        raise SovereigntyReplayError(
                            f"malformed sovereignty event at seq {sequence}: "
                            f"responsibility {resp.resp_id} version changed "
                            f"({previous_resp.version} -> {resp.version}) "
                            "without a name change"
                        )
                elif resp.version != previous_resp.version + 1:
                    raise SovereigntyReplayError(
                        f"malformed sovereignty event at seq {sequence}: "
                        f"renamed responsibility {resp.resp_id} must bump "
                        f"exactly one version ({previous_resp.version} -> "
                        f"{previous_resp.version + 1}), got {resp.version}"
                    )
                resp_snapshots.append(resp)

            assignments[role_id] = self._build_assignment(payload, status)
            if kind in ("assign", "replace"):
                roles[role_id] = Role(
                    role_id=role_id,
                    name=payload.get("role_name", role_id),
                    scope=payload.get("role_scope", ""),
                    version=event_role_version,
                )
            for resp in resp_snapshots:
                responsibilities[resp.resp_id] = resp
            principal_name = payload.get("principal_name", principal_name)

        # Resolve each assignment's responsibility references to the latest
        # canonical snapshots from the final registry (Responsibility is a
        # Principal-scoped first-class aggregate, not assignment-scoped).
        for rid, asm in list(assignments.items()):
            canonical = tuple(
                responsibilities.get(r.resp_id, r) for r in asm.responsibilities
            )
            if canonical != asm.responsibilities:
                assignments[rid] = RoleAssignment(
                    assignment_id=asm.assignment_id,
                    principal_id=asm.principal_id,
                    role_id=asm.role_id,
                    role_name=asm.role_name,
                    role_scope=asm.role_scope,
                    responsibilities=canonical,
                    version=asm.version,
                    status=asm.status,
                )

        principal = Principal(
            principal_id=principal_id,
            version=principal_version,
            name=principal_name,
            assignments=assignments,
        )
        return SovereigntyState(
            principal=principal,
            roles=roles,
            responsibilities=responsibilities,
            assignments=assignments,
        )

    @staticmethod
    def _decode_responsibility(item: Any, sequence: Any) -> Responsibility:
        """Strictly decode one responsibility snapshot; never raw KeyError.

        Missing or invalid ``resp_id`` / ``name`` / ``version`` (and any
        :class:`InvalidIdError`) are wrapped in
        :class:`SovereigntyReplayError` with reason ``malformed_replay``.
        """
        if not isinstance(item, dict):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                "responsibility item must be an object, got "
                f"{type(item).__name__}"
            )
        resp_id = item.get("resp_id")
        name = item.get("name")
        version = item.get("version")
        if not isinstance(resp_id, str) or not resp_id:
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                "responsibility missing/invalid resp_id"
            )
        if not isinstance(name, str):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                f"responsibility {resp_id!r} missing/invalid name"
            )
        if not isinstance(version, int):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                f"responsibility {resp_id!r} missing/invalid version"
            )
        if version < 1:
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                f"responsibility {resp_id!r} version must be >= 1, got {version}"
            )
        try:
            validate_id("responsibility", resp_id)
        except InvalidIdError as exc:
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: {exc.message}"
            ) from exc
        return Responsibility(resp_id=resp_id, name=name, version=version)

    def _decode_event(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Strictly decode one sovereignty event row; raise a stable failure."""
        sequence = row.get("sequence")
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError, KeyError):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                "payload is not valid JSON"
            ) from None
        if not isinstance(payload, dict):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                "payload must be a JSON object"
            )
        kind = payload.get("kind")
        if kind not in ("assign", "replace", "revoke"):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: unknown kind {kind!r}"
            )
        if not isinstance(payload.get("role_id"), str) or not payload["role_id"]:
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: missing role_id"
            )
        if (
            not isinstance(payload.get("assignment_id"), str)
            or not payload["assignment_id"]
        ):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: missing assignment_id"
            )
        if (
            not isinstance(payload.get("principal_id"), str)
            or not payload["principal_id"]
        ):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: missing principal_id"
            )
        for field_name in (
            "version",
            "prev_version",
            "principal_version",
            "role_version",
        ):
            value = payload.get(field_name)
            if not isinstance(value, int):
                raise SovereigntyReplayError(
                    f"malformed sovereignty event at seq {sequence}: "
                    f"{field_name} must be an integer"
                )
        if payload.get("status") not in (STATUS_ACTIVE, STATUS_REVOKED):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                f"invalid status {payload.get('status')!r}"
            )
        if not isinstance(payload.get("responsibilities", []), list):
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: "
                "responsibilities must be a list"
            )
        # The payload principal must be the envelope principal.  A mismatched
        # row cannot be deterministically replayed for any principal, and it
        # must never leak an assignment into another principal's replay.
        envelope_principal = row.get("principal_id")
        if payload["principal_id"] != envelope_principal:
            raise SovereigntyReplayError(
                f"malformed sovereignty event at seq {sequence}: payload "
                f"principal_id {payload['principal_id']!r} does not match "
                f"envelope principal_id {envelope_principal!r}"
            )
        return payload

    def _append_event(self, event_type: str, payload: dict[str, Any]) -> int:
        """Append exactly one sovereignty event via LedgerBroker.append.

        The idempotency key is scoped to the Principal aggregate version
        (``principal_id|principal_version``, one event per mutation), so two
        concurrent mutations computed from the same principal base collide on
        the same key instead of persisting duplicate Principal versions.
        ``DuplicateEventError`` is deliberately NOT swallowed: a collision is
        a real conflict and must surface to the caller.
        """
        principal_id = payload["principal_id"]
        principal_version = int(payload["principal_version"])
        kind = payload["kind"]
        version = int(payload["version"])
        return self._broker.append(
            event_type=event_type,
            producer=PRODUCER,
            principal_id=principal_id,
            space_id=SPACE_ID,
            correlation_id=f"sovereignty|{payload['assignment_id']}|{kind}|{version}",
            idempotency_key=f"{principal_id}|{principal_version}",
            payload=payload,
        )

    @staticmethod
    def _build_assignment(
        payload: Mapping[str, Any], status: str = STATUS_ACTIVE
    ) -> RoleAssignment:
        return RoleAssignment(
            assignment_id=payload["assignment_id"],
            principal_id=payload["principal_id"],
            role_id=payload["role_id"],
            role_name=payload.get("role_name", payload["role_id"]),
            role_scope=payload.get("role_scope", ""),
            responsibilities=tuple(
                Responsibility.from_dict(r) for r in payload.get("responsibilities", [])
            ),
            version=int(payload["version"]),
            status=status,
        )


__all__ = [
    "EVT_ASSIGN",
    "EVT_REPLACE",
    "EVT_REVOKE",
    "PRODUCER",
    "SPACE_ID",
    "STATUS_ACTIVE",
    "STATUS_REVOKED",
    "IllegalTransitionError",
    "InvalidIdError",
    "Principal",
    "Responsibility",
    "Role",
    "RoleAssignment",
    "SovereigntyError",
    "SovereigntyReplayError",
    "SovereigntyService",
    "SovereigntyState",
    "StaleVersionError",
    "generate_id",
    "validate_id",
]
