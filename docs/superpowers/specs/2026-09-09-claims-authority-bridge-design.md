---
schema_version: specification/v1
spec_version: 0.1.0
status: draft
lifecycle: contract
owner: governance-team
created: 2026-09-09
last-reviewed: 2026-09-09
title: OMO Canonical Claims Authority Bridge
bet_id: unbound
implementation_authorized: false
value_indicator_policy: false
---

# OMO Canonical Claims Authority Bridge

## 1. Status and authority

This document is a draft design contract. It is not an accepted specification,
does not create a BET, does not authorize implementation, and cannot authorize
a workflow claim or Git publication.

The accepted Documents proposal input is:

- document:
  2026-09-09-Claims-Authority-Bridge机制BET提案-v1.md
- SHA-256:
  b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c

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
| CAB-I-06 | Claim close, expiry, takeover or version change invalidates an outstanding publish fence. |
| CAB-I-07 | Every PublishIntent is exact, expiring and single-use. |
| CAB-I-08 | Remote OID drift, broker unavailability or double-read disagreement fails closed. |
| CAB-I-09 | v1 receipts are audit-readable but cannot authorize new publication. |
| CAB-I-10 | Dashboard and other observers remain instruction_capable=false. |
| CAB-I-11 | R0 and R1 states and evidence can never be collapsed. |
| CAB-I-12 | A degraded Human exception is bounded to one exact commit and never inherited. |

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

## 9. Contract objects

### 9.1 ClaimsAuthorityDescriptor

Required fields:

- schema and authority_id;
- authority_mode: cooperative-r0 or adversarial-r1;
- canonical repository;
- broker transport;
- store identity;
- policy path, revision and blob;
- accepted clone identity schemas;
- v1 compatibility mode: readonly;
- descriptor digest.

The descriptor is policy input. It does not itself issue a claim.

### 9.2 ClaimMutationEnvelope

Required fields:

- operation and idempotency request_id;
- actor_id and delivery_attempt_id;
- canonical repository, clone root and exact branch;
- clone identity, manifest and readiness digests;
- frozen base and current HEAD;
- BET ID or explicit unbound authority;
- WorkPacket digest and accepted Spec binding;
- affected-graph digest and requested path digest;
- expected claim version.

The broker independently rereads every security-relevant field. Self-declared
envelope values are not proof.

### 9.3 ClaimsAuthorityReceipt v2

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

Clone-local run/claim material contains:

- canonical receipt reference and digest;
- observed broker sequence;
- projection timestamp and freshness;
- no authority secret or signing material.

Deleting the projection cannot delete the claim. Editing or copying it cannot
change the claim.

## 10. State machines

### 10.1 Claim

    proposed -> active -> closed
                    +--> expired
                    +--> taken_over

Every transition increments claim_version or lease_epoch. A stale expected
version is rejected.

### 10.2 Publication

    requested -> issued -> consumed -> settled
          |         |          |
          +-> rejected          +-> unknown
                    +-> expired

Only issued can be consumed, and exactly once. Unknown is resolved by querying
the same intent and remote ref; automatic retry is prohibited.

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
| closed, expired or taken-over claim reuses token | RED |
| token replay or second consumption | RED |
| remote expected OID changes | RED |
| broker is unavailable or authority reads disagree | fail closed |
| v1 receipt authorizes a new publication | RED |
| v1 record is copied or promoted into v2 | RED |
| store sequence rolls back or is truncated | RED |
| R0 receipt is labeled adversarial proof | RED |
| projection disagrees with authority | rebuild projection; never reverse authority |
| valid clone, claim, exact HEAD and one-shot token | GREEN |

## 12. Delivery WorkPackets

### WP0 — Contract and binding

- Accept this Spec only after all open design questions are resolved.
- Bind one collision-safe candidate BET.
- Initial matrix:
  engineering=NOT_STARTED, operational/value=NOT_PROVEN,
  overall=evaluating, value_indicator_policy=false.
- No implementation or host changes.

### WP1 — Broker shadow

- Add v2 schema and canonical broker shadow receipts.
- Keep v1 as the effective gate.
- Compare v1/v2 decisions against the same fixtures.
- Report disagreement as UNPROVABLE.
- Dashboard may observe shadow state but cannot display admitted.

### WP2 — R0 cooperative enforcement

- Make the canonical broker the managed-clone claims authority.
- Reduce clone-local state to projection.
- Verify changesets through v2 receipts.
- Issue and settle one-shot PublishIntent tokens.
- Run a real managed-clone canary without degraded publication.

### WP3 — R1 adversarial design and host transaction

- Select protected broker identity/store.
- Define signing, rotation, recovery and compromise response.
- Use separate repository and host-operation authorization.
- Do not block R0 personal use, but do not overclaim its security.

## 13. Candidate implementation surfaces

These are design candidates, not authorized write surfaces.

OMO child-first:

    projects/omo/src/omo/workflow/claims_authority.py
    projects/omo/src/omo/workflow/core.py
    projects/omo/src/omo/workflow/lifecycle.py
    projects/omo/tests/test_workflow_claims_authority_bridge.py
    projects/omo

The projects/omo gitlink is a separate root-last transaction.

Root adapter/verifier:

    bin/agent-workflow.py
    bin/gac/agent-clone.py
    bin/gac/coordination_store.py
    tests/test_agent_workflow.py
    tests/test_clone_lifecycle.py
    .omo/_truth/registry/swarm-coordination.yaml

coordination_store.py may contribute WAL, BEGIN IMMEDIATE, CAS and fencing
primitives. Its environment-selectable database and in-process direct writes
cannot be promoted unchanged into production authority.

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

## 15. Rollback

1. Disable v2 enforcement and stop issuing new PublishIntent tokens.
2. Allow issued tokens to expire or settle; never mint replacements.
3. Return to v1 readonly observation plus exact Human degraded authorization.
4. Preserve all v2 receipts; never rewrite them as v1.
5. Rebuild or delete projections without changing canonical store.
6. Revert child and root code in separate PRs.
7. Never roll back to external-root authority.

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

## 17. Open decisions before acceptance

1. Exact R0 canonical store identity and non-environment-selectable resolution.
2. Whether broker transport is a canonical subprocess entry or protected UDS.
3. Exact v1 readonly migration window and cutover failure mode.
4. Exact policy ownership for ClaimsAuthorityDescriptor.
5. Exact separation between broker storage and coordination_store test backend.
6. R1 security choice: code-signing/Keychain or service account/LaunchDaemon.

WP1 may begin only after decisions 1–5 are resolved in an accepted version.
WP3 requires a separate acceptance of decision 6.

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
| Work decomposition | One parent BET, three staged WorkPackets | One portfolio truth with independent stop points. |

## 19. Stop conditions

Stop if implementation would:

- trust an external or clone-local root directly;
- allow caller-selected production authority/store;
- create simultaneous v1 and v2 effective authorities;
- authorize from projection bytes;
- omit WorkPacket/path/change/remote-OID fencing;
- introduce an automatic publish retry;
- modify historical receipts;
- claim R1 security from R0 evidence;
- require host mutation inside a repository PR;
- mark any BET complete or write value evidence.
