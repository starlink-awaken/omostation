---
schema_version: specification/v1
spec_version: 1.0.0
title: North-star recovery and first real Decision Episode proof
bet_id: BET-Y2Q2-T4-01
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-23'
last-reviewed: '2026-09-23'
implementation_authorized: true
value_indicator_policy: true
risk_level: L2
human_gate: true
type: ssot
---

# BET-Y2Q2-T4-01: North-star recovery and first real Decision Episode proof

## Decision and north star

The principal accepts this specification as the minimum governed container for
the active Goal whose only north star is:

> 织星是夏明星一个人的业务操作系统：把外部信号转化为他愿意署名的真实结果，并准确记住每次人工修订。

The three-year strategy remains the primary line. The digital-twin blueprint is
its subordinate target architecture. Mesh remains the only active SFOP `S`
dispatcher and OMO remains the only governance write control plane. This Spec
does not create a second ledger, dispatcher, operating system, ontology, or
top-level project.

## Current factual baseline

- `BET-Y2Q2-T5-03`, `BET-Y1Q4-T10-155`, and `BET-Y1Q4-T10-156` are already
  delivery-accepted and must not be rebuilt.
- Claims Authority is `shadow-active`, authority epoch 1, effective v1, with
  instruction capability disabled.
- The authoritative store tip is sequence 2, receipt
  `sha256:a660e34c55467e631f38d97e17b4d2377281fc5fe73a94b6f33548dbabe1eab7`.
- Lifecycle Operation A is historical and non-repeatable. Operation B is
  protocol-blocked; Operation C has not started.
- The conflicting approval records for the old lifecycle draft are preserved
  as non-authoritative evidence and are not consumable.
- Real v2 qualifying value evidence is 0/30. Engineering or governance work is
  not a substitute for personal business value.

## Concurrent-writer operating contract

Concurrent activity in the canonical Workspace is expected during this BET and
is handled without taking over another writer:

1. `/Users/xiamingxing/Workspace` is a read-only runtime-fact source for this
   writer. No edit, reset, clean, checkout, rebase, commit, or stash is allowed
   there.
2. All repository changes use one isolated managed worktree and one writer.
3. Every commit, push, pull-request update, and merge is fenced by two reads of
   the remote `refs/heads/main` OID.
4. If the remote OID changes, the writer stops the pending external effect,
   verifies the isolated worktree is clean or has a fully enumerated expected
   diff, and replays only that expected diff on the new base. No blind rebase,
   cherry-pick, force push, or automatic retry is allowed.
5. Canonical dirty files and other writers' processes remain untouched. A
   branch-occupancy or path conflict is evidence to reroute or serialize the
   local transaction, not authority to kill or seize the other writer.
6. The principal delegated decisions about ordinary blocking and screening
   conditions through `2026-09-28T00:00:00+08:00`. This delegation does not
   supply the operation-specific fields required for any Claims lifecycle
   operation and does not authorize Restricted-data egress.

## Phase 0: factual and authorization integrity

Required result:

- preserve the sequence 1 and sequence 2 receipt chain byte-for-byte;
- classify the conflicting approval records as non-authoritative evidence;
- prove all effects that occurred and prove zero legacy publication effect;
- mark the abandoned run/lock as stale legacy without inventing success;
- recompute the bound WorkPacket with the canonical ECOS compiler;
- maintain a successor authorization draft bound to authority epoch 1,
  sequence 2, the current receipt digest, current `origin/main`, and the real
  protocol capability.

No new Claims operation is authorized by this Spec.

## Phase 1: one control plane and honest projections

Required result:

- A1 through A9, SFOP, the workflow observer, managed code-root health, and the
  single-control-plane projection are recomputed from one fresh `origin/main`;
- A4 reads scheduler registry and installed runtime facts from the intended
  roots, rather than from a stale canonical checkout;
- A9 consumes a complete ASD five-panel snapshot and a fresh cockpit source
  projection; partial evidence never becomes PASS;
- Mesh is the only `S` holder, OMO is the only governance writer, resident is a
  projection, north-star components only meter outcomes, and MOS only governs
  memory;
- active and stale locks are attributed to a live process or explicitly
  preserved as legacy.

Read-only external checks may be re-run only as a new deliberate observation;
no unknown external-effect outcome may be automatically retried.

## Phase 2: strategy-to-runtime convergence

The following chain must map one-to-one across strategy, architecture, runtime,
and the BET ledger:

`Vision → Role responsibility → Decision Episode → Mandate → Action → Evidence → Outcome → Human adjudication → Memory/Evolution`.

MOF may act only as a Control Compiler. Every promoted model needs a named
consumer, compiled artifact, test, accountable owner, M0 use evidence, and an
exit or rollback path. Dynamic counts and health facts remain projections and
must not be copied into strategy documents.

## Phase 3: first real Golden Scenario

The first Golden Scenario begins with a real personal work signal, not a
governance task or engineering pull request:

`SignalObserved → RoleContextAssigned → ResponsibilityLinked → DecisionProposed → HumanAdjudication → MandateGranted → Action/Evidence → OutcomeObserved → AdjudicationRecorded → MemoryCandidate → EpisodeClosed`.

Acceptance requires all of the following:

- Cockpit is the only human entry point.
- Every external action is covered by a valid, revocable Mandate.
- Accept, edit, reject, and ignore decisions retain the original signal,
  concrete human revision diff, outcome, cost, and time burden.
- `decision_outcome` is the common fact for evaluation, delegation, memory, and
  evolution.
- At least 30 qualifying v2 real records exist.
- Four consecutive weeks each contain at least three principal-accepted,
  verifiable delegated results.
- Human approval and correction time is less than system time saved; otherwise
  the scenario is degraded or stopped.

No fixture, backfill, gate result, test, code volume, commit, or agent count can
qualify as value evidence.

## Phase 4: controlled evolution

Only after the Golden Scenario establishes a real outcome baseline may Policy,
Skill, Prompt, Model Route, Journey, Connector, or Agent Cell changes become
evolution candidates. Every candidate requires historical Episode replay,
sandbox, shadow, limited canary, human adjudication, and rollback. Family,
organization, physical multi-host, and generic-agent-platform expansion remain
out of scope.

## Claims boundary

This Spec does not authorize `observe-claim`, `begin-claim-mutation`,
`settle-claim-mutation`, legacy fence issuance, publication, instruction
capability, or promotion above shadow. Each future Claims operation requires a
fresh successor draft plus the principal's exact operation list,
`principal_decision_id`, `decision_timestamp_utc`,
`decision_expires_at_utc`, and verbatim authorization text.

The blocked v1-allow versus managed-clone-v2 fence design may change only
through an accepted Spec addendum with success, failure, unknown-outcome,
replay, and rollback tests plus a newly compiled WorkPacket.

## Completion evidence

The BET remains non-terminal until every axis is independently proven:

- Engineering: target tests, integration gates, failure/recovery paths,
  required checks, and a reachable merged commit.
- Operational: fresh replay, live canary, cleanup, receipts, and reconstructible
  projections from authoritative sources.
- Value: 30 qualifying real records, four consecutive qualifying weeks, signed
  principal adjudications, revision diffs, rejection evidence, and time-burden
  evidence.

If any axis is missing, it must remain `NOT_PROVEN`, `PARTIAL`, `BLOCKED`, or
`UNPROVABLE`; delivery status cannot substitute for value.

## Rollback and stop conditions

Repository changes are reverted by ordinary non-force PR rollback. Runtime
projections are regenerated from their sources. Historical Claims receipts and
human records are never rewritten.

Stop the pending effect on any unauthorized external action, receipt/hash
anomaly, unknown remote outcome, unexplained origin drift, Restricted-data
egress, unbound Claims request, missing real-value provenance, or human burden
greater than benefit. Preserve evidence and continue only through an applicable
principal decision or already-delegated bounded concurrency policy.
