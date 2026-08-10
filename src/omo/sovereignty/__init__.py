"""OMO Sovereignty (W2-01) — Principal/Role/Responsibility/RoleAssignment.

Local-only sovereignty governance on top of the causal event ledger:

- models: :class:`Principal`, :class:`Role`, :class:`Responsibility`,
  :class:`RoleAssignment` with strict literal prefix ids (``principal:`` /
  ``role:`` / ``responsibility:`` / ``assignment:``) and monotonic versions;
- every model is validated, immutable and versioned; each mutation persists
  exactly one assignment-lifecycle event carrying the four aggregate snapshots;
- state machine: :class:`SovereigntyService` implements legal
  ``assign`` / ``replace`` / ``revoke`` transitions and rejects stale
  versions (including reactivation) before any write;
- every write goes through ``LedgerBroker.append`` and every query replays
  the ledger for a single principal_id (no projection table, no remote
  surface — local only); malformed sovereignty rows raise a stable
  :class:`SovereigntyReplayError` instead of being silently dropped.

Explicitly out of scope (W2-01): Mandate / PDP / PEP / W2-04 projections /
Constitution / any Agora or remote interface.
"""

from omo.sovereignty.roles import (
    EVT_ASSIGN,
    EVT_REPLACE,
    EVT_REVOKE,
    PRODUCER,
    SPACE_ID,
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
    SovereigntyState,
    StaleVersionError,
    generate_id,
    validate_id,
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
