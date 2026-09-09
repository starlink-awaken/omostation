---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-09
last-reviewed: 2026-09-09
title: OMO Canonical Claims Authority Bridge
bet_id: BET-Y1Q4-T10-143
implementation_authorized: false
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# OMO Canonical Claims Authority Bridge

## 1. Status and authority

This document is the accepted R0 architecture contract for the portfolio
parent `BET-Y1Q4-T10-143`. Acceptance authorizes only the zero-write parent
binding. It does not authorize a WP1/WP2 child BET, implementation, store
creation, implementation workflow claims, Git publication effects or host
mutation.

The accepted Documents proposal input is:

- document:
  2026-09-09-Claims-Authority-Bridge机制BET提案-v1.md
- SHA-256:
  b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c

Version 0.2 resolved the R0 acceptance blockers found by the independent
post-bootstrap audit. Two final read-only reviews returned `APPROVED / CLEAR`
and `ACCEPTABLE_DRAFT / CLEAR`. Version 1.0 accepts that reviewed content and
binds one candidate while keeping implementation unauthorized. R1 remains a
separate future design.

## 2. Problem

Managed clones correctly isolate execution trees, but the current state
placement and authority policy disagree:

- agent-workflow derives its workspace from the clone that contains the
  executable, so run, lock and claim records are written inside that clone;
- agent-clone changeset verification accepts only the OS-account integration
  Workspace as claims authority;
- a valid clone-local claim therefore fails as claims_authority_mismatch or
  changeset_claims_unverified;
- current verification is not atomic with push and cannot fence a claim that
  closes, expires or changes after the snapshot.

A3 required two explicit, commit-bounded degraded publications. Those
exceptions are evidence of this design gap, not a precedent for normal
publication.

## 3. Decision

Adopt one OMO canonical claims broker.

    execution_root = managed clone
    authority_root = OMO canonical broker/store
    clone-local run/claim files = read-only projection

Reject external trusted roots as an authorization mechanism. A writer clone
must never become its own authority, and copied local YAML/JSON must never
authorize publication.

## 4. Goals

1. Give managed-clone workflows one canonical run, claim, lease and settlement
   identity under OMO.
2. Bind claims to clone identity, accepted WorkPacket, affected graph and exact
   paths.
3. Replace snapshot-only publication checks with a one-shot fenced
   PublishIntent.
4. Preserve one control plane while keeping clone execution isolated.
5. Provide replay-safe, queryable v2 receipts and a rebuildable local
   projection.
6. Separate cooperative personal-MVP integrity from adversarial security.

## 5. Non-goals

- Do not trust an arbitrary external claims root.
- Do not copy or promote v1 clone-local records into v2 authority.
- Do not rewrite historical A1/A3 identity, provenance, workflow or publication
  receipts.
- Do not mark A3 or another BET complete.
- Do not add multi-tenant RBAC, distributed consensus or high availability in
  R0.
- Do not claim that same-UID cooperative controls resist a malicious writer.
- Do not install a LaunchDaemon, create a service account, modify Keychain or
  change host configuration in a repository PR.
- Do not enable autonomous publication or broaden Agent concurrency.

## 6. Security levels

### 6.1 R0 cooperative integrity

R0 protects against normal but fallible Agents, stale state, accidental
double-writes, replay and publication races. It may run under the current
single-user account, but its receipt must say R0_COOPERATIVE.

R0 is sufficient for the personal MVP only after a real managed-clone canary
completes without a degraded waiver or no-verify publication.

### 6.2 R1 adversarial enforcement

R1 protects authority issuance from a writer with arbitrary same-account file
write ability. It requires a broker identity the writer cannot forge:

- code-signing/Keychain-bound signing, or
- a dedicated service account/LaunchDaemon with a protected store and UDS.

R1 requires a separate threat-model decision and operation-specific host
authorization. Until then, no artifact may claim ADVERSARIAL_ENFORCED.

## 7. Invariants

| ID | Invariant |
|---|---|
| CAB-I-01 | OMO is the only authority for run, claim, lease, fence and settlement. |
| CAB-I-02 | A managed clone owns an execution tree, never the authority store. |
| CAB-I-03 | Environment variables and ordinary CLI paths cannot select production authority. |
| CAB-I-04 | A local projection is rebuildable and cannot authorize an effect. |
| CAB-I-05 | Every claim binds actor, attempt, repository, identity, WorkPacket and path digest. |
| CAB-I-06 | Before publication starts, claim close, expiry, takeover or version change invalidates an issued fence. Once publication enters durable `publishing`, the claim is frozen against those transitions until settlement or operator resolution. |
| CAB-I-07 | Every PublishIntent is exact, expiring and single-use. |
| CAB-I-08 | Remote OID drift, broker unavailability or double-read disagreement fails closed. |
| CAB-I-09 | During WP1, v1 may authorize only the legacy roots it already accepts; it never authorizes a managed clone. After the WP2 cutover, v1 is audit-only and cannot authorize any publication. |
| CAB-I-10 | Dashboard and other observers remain instruction_capable=false. |
| CAB-I-11 | R0 and R1 states and evidence can never be collapsed. |
| CAB-I-12 | A degraded Human exception is bounded to one exact commit and never inherited. |
| CAB-I-13 | The production R0 store and broker executable are resolved from the OS-account identity, never from caller environment, cwd or clone bytes. |
| CAB-I-14 | `clone-lifecycle integrate --apply` remains the sole Git publication effect owner; no broker or Dashboard path can push independently. |

## 8. Target architecture

    Managed Clone
      identity + manifest + readiness
      accepted Spec + WorkPacket
      affected graph + proposed operation
              |
              | ClaimMutationEnvelope
              v
    OMO Canonical Claims Broker
      identity/repository/baseline verification
      WorkPacket scope verification
      CAS claim + lease + fencing transaction
      append-only authority receipts
      one-shot PublishIntent
              |
              +----> clone-local read-only projection
              |
              +----> agent-clone verifier
                           |
                           | token consume
                           v
                     Git publish / PR / settlement

The authority chain is:

    broker receipt
      -> claim version and lease epoch
      -> changeset identity
      -> PublishIntent
      -> remote expected OID
      -> PR/merge settlement

### 8.1 R0 canonical identity and store

R0 uses one dedicated store. It does not promote the current shadow
`coordination.sqlite3` into authority.

```text
authority_id = omo-claims-authority-r0
account_home = pwd.getpwuid(os.getuid()).pw_dir
integration_root = <account_home>/Workspace
authority_dir = <account_home>/agents/_shared/runtime/omo-claims-authority-r0/
store = <authority_dir>/store.sqlite3
high_water = <authority_dir>/highwater.json
backups = <account_home>/agents/_shared/backups/omo-claims-authority-r0/
```

Production resolution must not read `$HOME`, `WORKSPACE_ROOT`,
`OMO_COORDINATION_DB`, cwd, clone-local configuration, `--claims-root`,
`--store`, or `--db`. The resolved paths and ancestors must not be symlinks and
their owner UID must equal `os.getuid()`. Existing ancestor directories must
not be group/world writable; the dedicated `authority_dir` and backup directory
must be mode `0700`, and store/high-water/backup files mode `0600`. The broker
must not chmod or otherwise mutate shared ancestor directories. A mismatch
returns `AUTHORITY_STORE_UNSAFE` and fails closed.

The store reuses WAL, transaction, CAS and backup implementation patterns from
`coordination_store.py`, but not its environment-selectable path or shadow
semantics. This separate DB remains the only R0 claims authority store.

### 8.2 R0 broker transport

R0 chooses a one-request/one-process canonical stdio broker. It does not add a
daemon, UDS, LaunchAgent or host service.

The only production entry is resolved from the account integration root:

```text
mutation: <integration_root>/bin/agent-workflow.py claims-authority <verb> --request-json -
query:    <integration_root>/bin/agent-workflow.py claims-authority status --json
```

The writer clone is a client only. Broker code, descriptor and store identity
are loaded from `integration_root`, never from the writer clone. Stdin contains
one canonical JSON request; stdout contains exactly one canonical JSON response;
stderr is diagnostic only. Extra stdout, malformed JSON, an unexpected
executable identity or repository mismatch fails closed.

Every mutation verb requires exactly one stdin request. `status --json` is the
only bodyless read-only exception and rejects a mutation body or mutation-only
flag.

`bin/agent-workflow.py` must recognize and dispatch `claims-authority` using
only the standard library before importing any Workspace module. It then loads
the broker module by exact committed path.

The registry declares operating mode and critical path names only; it does not
embed the final descriptor digest. Broker activation at an exact committed
revision computes a sorted `critical_dependency_closure` of repository-relative
path, object kind and Git object ID. At minimum it binds
`bin/agent-workflow.py`, `bin/gac/agent-clone.py`,
`bin/gac/clone-lifecycle.py`, the policy blob, the `projects/omo` gitlink and
every repo-local module imported by the claims command, plus the managed-Python
runtime receipt. No repo-local dynamic import may remain outside the manifest.

The activation CAS stores the resulting descriptor digest in the authority DB
and high-water and emits an activation receipt. This avoids a policy-blob ↔
descriptor-digest self-reference. The canonical process verifies the entire
closure before reading a mutation request. Unrelated integration-root dirt
outside this closure does not become authority and does not automatically block
the broker, but a critical-path worktree change, missing object, wrong
repository, interpreter drift or closure mismatch returns
`AUTHORITY_DESCRIPTOR_MISMATCH`.

Tests may inject a temporary SQLite connection only through an internal Python
constructor. Test receipts use `authority_id=test:<uuid>` and
`publishable=false`; the production CLI exposes no store override, and every
production verifier rejects a `test:*` receipt.

### 8.3 Publication effect ownership

`clone-lifecycle integrate --apply` remains the only Git publication effect
owner. The broker verifies and fences but never runs Git. The exact R0 effect
sequence is:

1. `integrate` verifies changeset, clone identity, claim and remote state;
2. it requests one PublishIntent from the broker;
3. the broker atomically moves the intent from `issued` to `publishing` and the
   claim from `active` to `publishing(intent_id)`;
4. `integrate` performs exactly one Git push;
5. it immediately rereads the remote ref twice;
6. it records state `settled` with outcome `success | rejected`, or state
   `unknown`, against the same intent;
7. PR creation is a subsequent idempotent lookup-or-create step keyed by
   repository, head and base, and never issues another token.

An unknown push result may only query the same intent and remote ref. It cannot
mint a replacement token or automatically retry the push.

While a claim is `publishing`, close, takeover, expiry, heartbeat renewal and a
second intent are rejected. `unknown` keeps the claim frozen until the same
intent is resolved to a settlement. Setting `operator_required` only marks an
escalation and cannot unfreeze the claim. A separately authorized operator
resolution must prove the effect process ended and the exact remote OID before
settlement. This durable publication state, not a last-moment snapshot, closes
the claim-to-push race.

### 8.4 Legacy v1 drain fence

WP1 must retrofit every existing v1 Git publication entry through the same
sole `clone-lifecycle integrate --apply` owner with a broker-issued
`LegacyPublishFence`. v1 still decides allow/deny for its existing legacy
roots; the fence grants no new scope. It only makes the already-allowed Git
effect visible, one-shot and drainable.

The fence binds legacy descriptor epoch/operating_mode, actor, repository,
exact HEAD,
remote ref/expected OID and expiry. Immediately before Git, `integrate` asks
the broker to move it atomically into `publishing`. A publishing fence remains
unresolved until state `settled` with outcome `success | rejected`, or state
`unknown`; cutover cannot occur while any fence is issued, publishing, unknown
or marked `operator_required`.

Before cutover, the broker CAS-closes legacy-fence issuance for the current
epoch and writes one `claims-legacy-drain-receipt/v2`. New v1 publication then
fails closed. The final cutover receipt must bind that drain receipt, the
closed legacy epoch and zero unresolved fences. A legacy process with a stale
epoch/operating_mode or without a consumable fence must reject before Git.

## 9. Contract objects

### 9.1 ClaimsAuthorityDescriptor

Schema ID: `claims-authority-descriptor/v2`.

Required fields:

- schema and authority_id;
- security_level: `cooperative-r0 | adversarial-r1`;
- operating_mode: `shadow | enforce-r0 | human-degraded-only`;
- canonical repository;
- broker transport;
- store identity;
- critical dependency closure digest and its entry/tree/gitlink/runtime
  identities;
- accepted clone identity schemas;
- v1_compatibility: `legacy-effective-shadow | readonly`; the former is legal
  only with `operating_mode=shadow`, and all other modes require `readonly`;
- descriptor digest.

The descriptor is policy input. It does not itself issue a claim.

### 9.2 ClaimMutationEnvelope

Schema ID: `claim-mutation-envelope/v2`.

Required fields:

- operation and idempotency request_id;
- actor_id and delivery_attempt_id;
- canonical repository, clone root and exact branch;
- clone identity, manifest and readiness digests;
- frozen base and current HEAD;
- accepted BET ID and WorkPacket ID;
- WorkPacket digest and accepted Spec path/digest binding;
- affected-graph digest and requested path digest;
- expected claim version.

The broker independently rereads every security-relevant field. Self-declared
envelope values are not proof.

Production v2 never signs an unbound workflow. Draft/bootstrap transactions
remain outside v2 until the bridge is enforced and require an exact Human
waiver under the existing mechanism. An unbound request returns
`WORK_PACKET_UNBOUND`.

### 9.3 ClaimsAuthorityReceipt v2

Schema ID: `claims-authority-receipt/v2`.

Required fields:

- authority epoch and monotonic sequence;
- previous receipt digest;
- receipt, run and claim IDs;
- claim version and lease epoch;
- actor, attempt, repository and clone identity digest;
- frozen base, HEAD, WorkPacket and affected-graph digests;
- claimed-path digest;
- policy revision/blob and descriptor digest;
- issued/expires timestamps;
- R0 receipt digest or R1 broker signature.

### 9.4 PublishIntent

Schema ID: `claims-publish-intent/v2`.

An intent binds:

- actor, attempt and repository;
- canonical clone root and identity/device binding;
- frozen base and exact HEAD;
- changeset ID and changed-path digest;
- WorkPacket, claim ID/version and lease epoch;
- remote ref and expected remote OID;
- policy/descriptor version;
- expiration, nonce and single-use state.

Publication must reread authority immediately before the effect and settle the
same token after the effect. Unknown outcome queries the same token; it never
creates a replacement publication.

### 9.5 Projection

Schema ID: `claims-authority-projection/v2`.

Clone-local run/claim material contains:

- canonical receipt reference and digest;
- observed broker sequence;
- projection timestamp and freshness;
- no authority secret or signing material.

Deleting the projection cannot delete the claim. Editing or copying it cannot
change the claim.

### 9.6 LegacyPublishFence and drain

Legacy v1 effect fencing uses `claims-legacy-publish-fence/v2`; the epoch-close
receipt uses `claims-legacy-drain-receipt/v2`. Both use the same canonical
encoding, sequence, idempotency and settlement rules as other authority
objects. A legacy fence is never evidence that v2 admitted the claim.

### 9.7 PublicationSettlement and status

Publication settlement uses `claims-publication-settlement/v2`. The read-only
observer response uses `claims-authority-status/v2`.

A settlement binds the intent, exact remote ref/OID observation, outcome,
observation timestamps and the authority sequence that committed it. Repeating
the same settlement request with the same canonical payload returns the same
receipt. Reusing its request ID with a different payload returns
`REQUEST_ID_REUSE_MISMATCH`.

### 9.8 Canonical encoding and digest

All authority objects use UTF-8 JSON with:

```text
sort_keys=True
separators=(",", ":")
ensure_ascii=True
allow_nan=False
```

An object's own `digest` and `signature` fields are excluded from its digest
preimage. Digests use `sha256:<64 lowercase hex>`. A request ID is UUIDv4 and
is unique under `(authority_id, request_id)`. The same request ID with the same
canonical payload returns the original receipt; a different payload is a hard
conflict.

### 9.9 Typed error taxonomy

Production responses use a stable code from this minimum set:

```text
AUTHORITY_UNAVAILABLE
AUTHORITY_DESCRIPTOR_MISMATCH
AUTHORITY_STORE_UNSAFE
AUTHORITY_STORE_CORRUPT
AUTHORITY_HIGHWATER_ROLLBACK
AUTHORITY_HIGHWATER_GAP
AUTHORITY_CLOCK_ROLLBACK
REQUEST_SCHEMA_INVALID
REQUEST_ID_REUSE_MISMATCH
IDENTITY_MISMATCH
WORK_PACKET_UNBOUND
CLAIM_SCOPE_VIOLATION
AFFECTED_GRAPH_MISMATCH
CLAIM_VERSION_STALE
CLAIM_LEASE_EXPIRED
LEGACY_FENCE_ISSUANCE_CLOSED
LEGACY_FENCE_REPLAY
LEGACY_DRAIN_INCOMPLETE
PUBLISH_INTENT_EXPIRED
PUBLISH_INTENT_REPLAY
REMOTE_OID_DRIFT
V1_AUTHORITY_FORBIDDEN
PROJECTION_STALE
```

Unknown internal exceptions are returned as a redacted
`AUTHORITY_UNAVAILABLE` response and logged diagnostically; raw paths or
request payloads are not exposed to observers.

## 10. State machines

### 10.1 Claim

```text
proposed -> active -> closed
              |  +-> expired
              |  +-> taken_over
              +-> publishing(intent_id) -> closed
```

Every transition increments claim_version or lease_epoch. A stale expected
version is rejected. `publishing` is a durable fence: ordinary close, expiry,
takeover, heartbeat and a second intent are invalid until settlement or
operator resolution.

### 10.2 Publication

```text
requested -> issued -> publishing -> settled
      |          |          |           outcome = success | rejected
      +-> rejected          +-> unknown -> settled
                 +-> expired
```

Only `issued` can enter `publishing`, and exactly once. That transition freezes
the bound claim in the same transaction. `unknown` is resolved by querying the
same intent and remote ref; automatic retry is prohibited. State and settlement
outcome are separate fields. `operator_required` is an escalation marker on an
unresolved `unknown`, not a resolved state and not a drain escape.

### 10.2.1 Legacy drain fence

```text
issued -> publishing -> settled
                    +-> unknown -> settled
```

Closing legacy-fence issuance prevents new `issued` rows. Cutover requires zero
rows/states or escalation markers in `issued`, `publishing`, `unknown` or
`operator_required` for the closed legacy epoch. Only `settled` with outcome
`success | rejected`, or a separately authorized operator resolution that
proves the effect process ended and the exact remote OID, satisfies drain.

### 10.3 Lease, time and CAS

- Run and claim leases last 15 minutes.
- An active non-publishing claim must renew with
  `heartbeat_interval <= 5 minutes`; every successful renewal increments the
  lease epoch.
- A PublishIntent lasts 300 seconds and cannot be refreshed.
- Client timestamps never authorize an action; expiry is evaluated only by the
  broker clock.
- If broker time is more than 30 seconds behind persisted `last_broker_time`,
  the broker stops issuing receipts and returns `AUTHORITY_CLOCK_ROLLBACK`.
- Every mutation uses SQLite `BEGIN IMMEDIATE` with `journal_mode=WAL`,
  `synchronous=FULL`, `foreign_keys=ON` and `busy_timeout=5000`.
- A state update must match current state, claim version and lease epoch in one
  CAS predicate.
- Receipt sequence, previous digest, state mutation and idempotency row commit
  in the same transaction.

Entering `publishing` is exactly-once: a second attempt returns
`PUBLISH_INTENT_REPLAY`. Settlement is idempotent only for the same canonical
payload; a conflicting result cannot overwrite the first settlement.

### 10.4 High-water, backup and corruption

The database `meta.last_sequence` and external high-water sequence/digest must
match before an authorization read or mutation.

- If the DB is ahead by exactly one receipt and the tail digest chain is
  complete, the broker may finish one crash-tail high-water reconciliation.
- DB behind high-water, DB ahead by more than one, a broken digest chain,
  initialized DB without high-water, or high-water without DB is
  `UNPROVABLE` and fails closed.
- First initialization is allowed only when both DB and high-water are absent.
- On the first successful broker mutation of each UTC day, lazily make one
  SQLite Online Backup; do not add a scheduler. Also make a fresh backup
  immediately before schema migration or cutover, even if that day's lazy
  backup already exists. A backup manifest binds SHA-256, last sequence and
  descriptor digest; retain the newest three valid backups.
- Corruption never triggers automatic restore. Preserve the incident store,
  verify backups read-only and require a separate operator transaction to
  restore.

These checks provide cooperative R0 integrity. A malicious same-UID writer who
alters both DB and high-water remains outside the R0 claim.

## 11. RED matrix

| Case | Required result |
|---|---|
| external root or writer clone used as authority | RED |
| hand-created, copied or modified run/receipt | RED |
| environment or --claims-root overrides production authority | RED |
| clone root or descriptor symlink escape | RED |
| actor, attempt, repository, branch or HEAD mismatch | RED |
| identity, manifest or readiness digest drift | RED |
| unbound or stale WorkPacket | RED |
| claim exceeds WorkPacket write surfaces | RED |
| affected graph and requested paths disagree | RED |
| claim changes between verification and publication | RED |
| claim close, takeover, expiry or second intent while publication is `publishing` | RED; keep claim frozen |
| closed, expired or taken-over claim reuses token | RED |
| token replay or second consumption | RED |
| remote expected OID changes | RED |
| broker is unavailable or authority reads disagree | fail closed |
| v1 receipt authorizes a managed clone during WP1 | RED |
| v1 receipt authorizes any publication after WP2 cutover | RED |
| v1 passes snapshot before cutover and attempts Git after legacy epoch closes | RED at fence issue/enter-publishing; cutover waits for unresolved fence |
| v1 record is copied or promoted into v2 | RED |
| store sequence rolls back or is truncated | RED |
| production store selected through environment, cwd or CLI path | RED |
| store/high-water path is a symlink, wrong owner or unsafe mode | RED |
| critical imported helper or managed-Python receipt drifts outside the descriptor closure | RED |
| registry embeds a descriptor digest that includes the same policy blob | RED self-reference |
| test authority receipt reaches production publisher | RED |
| broker clock rolls back beyond 30 seconds | RED |
| request ID is reused with a different payload | RED |
| R0 receipt is labeled adversarial proof | RED |
| projection disagrees with authority | rebuild projection; never reverse authority |
| valid clone, claim, exact HEAD and one-shot token | GREEN |

## 12. Delivery WorkPackets

The current R0 parent is a portfolio-only coordination BET. Its Ledger-derived
canonical WorkPacket `WP-BET-Y1Q4-T10-143` has an empty implementation
`scope.write_surfaces` list and therefore cannot claim an implementation path.
WP0 is this binding transaction, not an implementation wave.

WP1 and WP2 are future child BETs. Each requires its own accepted Spec, exact
non-union WorkPacket and collision-checked binding. They are materialized
sequentially rather than pre-created together:

1. only after this parent binding is merged may a WP1 child be proposed;
2. WP2 must not exist in the Ledger and must not have an accepted binding while
   WP1 is incomplete;
3. only after WP1 is `done` with its shadow-graduation evidence may a WP2 child
   be proposed and bound, with an explicit `depends_on` edge to WP1;
4. each child exposes only the paths required for that stage and owns its own
   run, claims, PRs, evidence, rollback and closeout.

This sequencing is enforced by the absence of a later-stage executable BET,
not by prose or a union of paths in one WorkPacket. The Ledger's current
`depends_on` field remains portfolio metadata and is not treated as the sole
workflow-start fence. R1 is a separate future Spec/BET after R0.

### WP0 — Accepted contract and binding

- Accept this Spec only after an independent audit confirms the R0 decisions
  in §8–§12 are internally complete.
- Bind one collision-safe candidate BET.
- Initial matrix:
  `engineering=NOT_STARTED`, `operational/value=NOT_PROVEN`,
  `overall=evaluating`, `value_indicator_policy=false`.
- Do not implement code, create the store, change a host or issue a receipt.
- Keep the parent WorkPacket implementation write set empty. A claim of any
  implementation path must return `WORK_PACKET_SCOPE_MISMATCH`.

### WP1 — R0 shadow

WP1 is a future child BET/accepted Spec/WorkPacket. It is not created or
authorized by this parent binding.

- Add v2 schemas, canonical broker storage and shadow receipts.
- v1 remains the only effective gate for the legacy Workspace/worktree roots
  it already accepts. It cannot authorize a managed clone.
- v2 only observes. It cannot allow or deny publication and cannot display
  `admitted`.
- A managed clone rejected by v1 remains rejected during shadow. Any Human
  exception remains exact and external to v2.
- Compare v1/v2 decisions on the same fixtures and lifecycle evidence.
- Any unexplained difference or v2 false-allow is `UNPROVABLE`.
- WP1 does not modify the Git push effect or perform a v2 publication.

Shadow graduation requires all of the following:

1. at least 24 continuous hours;
2. at least three independent workflow lifecycles covering a managed clone, a
   legacy Workspace/worktree regression, and claim expiry/replay;
3. the complete RED matrix;
4. zero unexplained decision differences and zero v2 false-allows;
5. the only permitted expected difference is a valid managed clone that v1
   rejects solely because of its fixed authority root while v2 shadow accepts.

### WP2 — R0 cooperative enforcement and canary

WP2 is a separate future child BET/accepted Spec/WorkPacket, created only after
WP1 is `done`. It is not created or authorized by this parent binding.

- Make the canonical broker the sole effective managed-clone claims authority.
- Reduce clone-local run/claim state to a read-only projection.
- Verify changesets through v2 receipts.
- Extend the sole `clone-lifecycle integrate --apply` owner to consume and
  settle one-shot PublishIntent tokens.
- For the operational canary, require an absent unique attempt branch and bind
  `expected_remote_oid` to forty zeroes.
- Execute a plain non-force
  `git push --porcelain origin <HEAD>:refs/heads/<attempt-branch>` exactly once.
  The existing `--force-with-lease` path does not satisfy this canary contract.
- A present branch or remote drift is rejected; an attempt branch is never
  updated in place.
- Complete PR creation, required CI, settlement and retirement without
  `--no-verify` or a degraded waiver.

Cutover is permitted only when shadow graduation passes, every legacy
publication entry is fence-aware, child/root pointers are exact and required
CI is green. It uses this fail-closed sequence:

1. the broker CAS-closes legacy-fence issuance for the current epoch and emits
   `claims-legacy-drain-receipt/v2`;
2. wait until that epoch has zero `issued`, `publishing`, `unknown` or
   `operator_required` legacy fences/markers and v2 has none of those unresolved
   states/markers;
3. merge one root policy transaction changing the registry requested operating
   mode from `shadow` to `enforce-r0`; the registry content contains only the
   requested operating mode and critical path names. The merged transaction
   yields an exact policy commit/blob, which the broker computes and binds in
   the activation receipt rather than embedding it back into the registry;
4. the canonical broker verifies that merged revision, recomputes the critical
   closure and atomically activates `enforce-r0` in the authority store;
5. the activation/cutover receipt binds policy commit/blob, descriptor digest,
   closed legacy epoch, drain receipt and zero unresolved-fence proof.

The broker activation CAS is the effective cutover point. A merged requested
mode without a successful activation receipt remains shadow and cannot admit
v2 publication. After activation, new requests accept only v2 and v1 becomes
permanently read-only.

If post-cutover enforcement must be disabled, mode becomes
`human-degraded-only`. Normal managed-clone publication stops; v1 is not
automatically re-enabled.

### R1 successor — outside this parent

R1 requires a new draft Spec, a new collision-safe candidate BET and a separate
host-operation authorization. Only that successor may select Keychain/code
signing or a service-account/LaunchDaemon/UDS design. The highest claim in this
parent is `R0_COOPERATIVE_PROVEN`.

## 13. Candidate implementation surfaces

These are design candidates, not authorized write surfaces. They must not be
copied as a union into the parent BET. Each future child binding selects only
its stage-specific subset after the preceding materialization gate passes.

### WP0 binding-only

```text
docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md
docs/plans/3y-bet-ledger.yaml
.omo/_truth/governance-evidence/waiver-2026-09-09-claims-authority-bridge-binding.md
```

### WP1 child shadow

```text
projects/omo/src/omo/workflow/claims_authority.py
projects/omo/src/omo/workflow/lifecycle.py
projects/omo/tests/test_workflow_claims_authority_bridge.py
```

### WP1 root adapter

```text
bin/agent-workflow.py
bin/gac/agent-clone.py
bin/gac/clone-lifecycle.py
tests/test_agent_workflow.py
tests/test_clone_lifecycle.py
.omo/_truth/registry/swarm-coordination.yaml
```

### WP1 root pointer

```text
projects/omo
```

The child PR, root adapter PR and root pointer PR are separate, ordered
transactions. Before the pointer advances, the root adapter must lazily detect
the unavailable v2 child interface, report shadow `UNPROVABLE`, and preserve
legacy behavior; it cannot partially activate v2. The final pointer transaction
then runs the cross-layer integration suite. WP1 may modify
`clone-lifecycle.py` only to route every legacy v1 Git effect through the
drainable fence; it must not change the Git push command or enable v2 publish.

### WP2 child enforce

```text
projects/omo/src/omo/workflow/claims_authority.py
projects/omo/src/omo/workflow/lifecycle.py
projects/omo/tests/test_workflow_claims_authority_bridge.py
```

### WP2 root publication adapter

```text
bin/agent-workflow.py
bin/gac/agent-clone.py
bin/gac/clone-lifecycle.py
tests/test_agent_workflow.py
tests/test_clone_lifecycle.py
```

### WP2 root pointer and cutover

```text
projects/omo
.omo/_truth/registry/swarm-coordination.yaml
```

The root pointer and cutover are separate final transactions. Cutover cannot
precede child-main reachability, root integration and the shadow graduation
gate.

`coordination_store.py` is a read-only implementation reference for WAL,
`BEGIN IMMEDIATE`, CAS and backup patterns. It is not a WP1/WP2 write surface;
its environment-selectable DB and shadow semantics must not be promoted into
production authority.

### 13.1 Dashboard read contract

The only observer entry is:

```text
bin/agent-workflow.py claims-authority status --json
```

It returns `claims-authority-status/v2` with security level, operating mode,
descriptor digest, sequence, integrity, active run/claim counts,
receipt/intent IDs, state,
version, lease expiry, path count/digest and last observation. It must redact
absolute paths, OS username, account home, hostname, remote URL, raw request
payload and full repository paths.

`instruction_capable` is always `false`; this status command accepts no
mutation body. A snapshot is `FRESH` for at most 120 seconds, then `STALE`.
Sequence rollback, non-OK integrity or read failure is `UNPROVABLE`. Dashboard
must not read SQLite directly, cache a response as authority or display shadow
acceptance as `admitted`.

## 14. Acceptance criteria

| ID | Assertion | Evidence type |
|---|---|---|
| CAB-AC-01 | One canonical broker is the sole effective claims authority. | structured report |
| CAB-AC-02 | All RED cases fail closed with typed reasons. | test report |
| CAB-AC-03 | Existing Workspace/worktree behavior has exact regression coverage. | test report |
| CAB-AC-04 | Clone-local projection deletion/rebuild cannot affect authority. | replay receipt |
| CAB-AC-05 | Claim version races and token replay are deterministically rejected. | test report |
| CAB-AC-06 | A real managed clone publishes without no-verify or degraded waiver. | operational receipt |
| CAB-AC-07 | Broker restart preserves idempotency and does not duplicate claim/publish. | replay receipt |
| CAB-AC-08 | PR, required CI, merge tree and settlement are exact and replayable. | delivery receipt |
| CAB-AC-09 | R0 is labeled cooperative and value remains NOT_PROVEN. | schema check |
| CAB-AC-10 | R1 host/security work cannot start without separate authorization. | policy test |
| CAB-AC-11 | Production broker/store identity cannot be redirected by env, cwd, clone or CLI path. | negative tests |
| CAB-AC-12 | Store/high-water crash-tail, rollback, gap and corruption cases follow §10.4 exactly. | recovery matrix |
| CAB-AC-13 | WP1 completes 24 hours, three lifecycles and the full RED matrix with no unexplained difference or false-allow. | shadow report |
| CAB-AC-14 | Cutover has a closed legacy epoch, drain receipt, zero `issued/publishing/unknown/operator_required` legacy/v2 publications, one requested-mode registry transaction and one descriptor-bound broker activation receipt. | cutover receipt |
| CAB-AC-15 | The operational canary uses one ordinary non-force push to a proven-absent unique attempt branch. | Git/intent receipt |
| CAB-AC-16 | Dashboard reads only the redacted status API, reports freshness honestly and remains instruction incapable. | observer contract tests |
| CAB-AC-17 | Entering `publishing` freezes the claim durably; close, takeover, expiry, heartbeat and a second intent are rejected until settlement or separately authorized resolution proves process termination and exact remote OID. | race tests |
| CAB-AC-18 | Every legacy v1 Git effect is fence-aware and a pre-cutover v1 snapshot cannot execute after legacy epoch closure. | drain-race tests |
| CAB-AC-19 | The canonical broker rejects drift in any critical dependency closure object or runtime receipt before reading a mutation request. | closure-manifest tests |
| CAB-AC-20 | The parent WorkPacket has zero implementation write surfaces; WP2 has no Ledger/binding identity until WP1 is done, and each future child has its own exact accepted Spec and WorkPacket. | Ledger/WorkPacket contract tests |

## 15. Rollback

1. Broker-CAS closes new PublishIntent issuance in the current descriptor
   epoch; v1 remains read-only.
2. Drain or resolve every `issued`, `publishing`, `unknown` and
   `operator_required` state/marker. Marking an unknown `operator_required`
   does not resolve it or reduce the unresolved count; never mint a replacement
   or flip authority while a process may still execute its bound Git effect.
3. Only after a settlement, or separately authorized operator proof of process
   termination plus exact remote OID, yields zero unresolved publications,
   merge the requested operating mode
   `human-degraded-only` and activate it through a descriptor-bound broker
   receipt.
4. Keep v1 read-only after cutover. Normal publication remains stopped; any
   temporary delivery needs an exact Human degraded authorization.
5. Preserve all v2 receipts, store/high-water evidence and unknown outcomes;
   never rewrite them as v1 or successful settlement.
6. Rebuild or delete projections without changing canonical authority.
7. Revert child, root adapter, root pointer and cutover changes in their own
   repository-ordered PRs.
8. If corruption is suspected, preserve the incident store and validate the
   newest three backups read-only. Restore only in a separate operator
   transaction.
9. Never roll back to external-root authority or allow caller-selected store
   resolution.

## 16. Anti-metrics

The following do not prove success:

- number of receipt fields;
- number of tests without adversarial negative cases;
- a green clone-local projection;
- a copied v1 run file;
- one successful no-verify push;
- Dashboard showing a receipt;
- same-UID R0 described as cryptographic isolation;
- a local unit test without a real managed-clone publication canary.

## 17. Resolved R0 decisions and R1 deferral

| Topic | R0 ruling |
|---|---|
| Store identity | Dedicated `omo-claims-authority-r0/` directory with DB/high-water and separate backups, resolved from passwd account home; never environment or CLI selected. |
| Transport | Canonical one-request stdio subprocess from the account integration root. |
| Test backend | Internal injected connection only; `test:*`, non-publishable receipts. |
| Policy ownership | `.omo/_truth/registry/swarm-coordination.yaml` requests operating mode and lists critical paths; broker activation at an exact revision computes and stores the non-self-referential descriptor digest. |
| Publication owner | Existing `clone-lifecycle integrate --apply` is the sole Git effect owner. |
| v1 shadow | Existing legacy roots retain their current v1 gate; managed clones remain rejected; v2 only observes. |
| Shadow graduation | 24 hours, three lifecycle classes, full RED matrix, no unexplained difference or false-allow. |
| Cutover | Close legacy-fence issuance, drain unresolved fences, merge one requested-mode registry transaction, then perform one descriptor-bound broker activation CAS. |
| Cutover rollback | Drain active v2 publications, then activate `human-degraded-only`; do not re-enable v1 or external-root authority. |
| Durability | Transactional receipt chain plus external high-water, bounded crash-tail reconciliation and three backups; corruption restore is operator-only. |
| Observer | Redacted 120-second status API with `instruction_capable=false`. |

These decisions close the R0 acceptance questions. An independent audit must
still verify the resulting document before `status: accepted` or Ledger
binding.

The R1 security choice remains intentionally unresolved and does not block R0.
It requires an independent future Spec/BET and operation-specific host
authorization.

## 18. Decision log

| Decision | Ruling | Reason |
|---|---|---|
| External trusted roots | Reject for authority | They create self-authorization and dual truth. |
| Control-plane shape | OMO canonical broker | Preserves one authority while clones remain isolated. |
| Clone-local state | Projection only | Rebuildable and non-authoritative. |
| Publication | One-shot fenced intent | Closes claim/push TOCTOU and replay. |
| R0 claim | Cooperative integrity | Honest boundary under a shared Unix account. |
| R1 claim | Protected broker identity/store | Authority receipts must be unforgeable by writers. |
| Migration | Shadow then enforce | Prevents an unobserved flag-day cutover. |
| R0 store | Dedicated passwd-home store | Avoids promoting an environment-selectable shadow DB. |
| R0 transport | Canonical stdio subprocess | Minimal personal-MVP bridge without a host daemon. |
| Git effect | Existing `clone-lifecycle integrate` only | Prevents a second publisher and keeps one idempotent delivery owner. |
| Publication race | Durable `publishing` claim/fence state | Prevents claim mutation or authority cutover between verification and Git. |
| Legacy cutover | Issue/consume/settle v1 drain fence | Makes existing snapshot-based publishers observable and drainable. |
| Cutover rollback | Human-degraded-only | A failed v2 cutover must not silently resurrect v1 authority. |
| Work decomposition | Zero-write parent plus sequential WP1/WP2 child BETs | Prevents the current path-only WorkPacket compiler from exposing a stage-union claim surface; later-stage binding does not exist until its predecessor is done. |

## 19. Stop conditions

Stop if implementation would:

- trust an external or clone-local root directly;
- allow caller-selected production authority/store;
- create simultaneous v1 and v2 effective authorities;
- let v1 authorize a managed clone during shadow or any publication after
  cutover;
- cut over or roll back while a legacy fence or v2 intent is issued,
  publishing, unknown or marked `operator_required`;
- let claim close, expiry, takeover, heartbeat or a second intent mutate a
  claim in durable publishing state;
- authorize from projection bytes;
- expose an implementation path on the parent WorkPacket or materialize a WP2
  BET/binding before WP1 is done;
- omit WorkPacket/path/change/remote-OID fencing;
- introduce an automatic publish retry;
- publish the R0 canary with force, force-with-lease, an existing branch or an
  unresolved remote OID;
- restore a corrupt store automatically or continue after a high-water gap;
- accept a test authority receipt in a production verifier;
- leave a repo-local broker dependency outside the descriptor closure or
  compute a self-referential policy/descriptor digest;
- modify historical receipts;
- claim R1 security from R0 evidence;
- require host mutation inside a repository PR;
- mark any BET complete or write value evidence.
