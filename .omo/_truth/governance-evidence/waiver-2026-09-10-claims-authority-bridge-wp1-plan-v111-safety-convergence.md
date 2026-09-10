---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-10
value_indicator_policy: false
title: Claims Authority Bridge WP1 plan v1.1.1 safety convergence
type: doc
---

# Claims Authority Bridge WP1 Plan v1.1.1 Safety Convergence

## Delegated authority and exact scope

Current delegated Human authority, verbatim:

> 授权窗口，继续延长吧，延到9月15日24点之前。

The delegation is interpreted in Asia/Shanghai and expires at
`2026-09-16T00:00:00+08:00`. The control Agent records this operation-specific
decision because two digest-bound, independent read-only reviews found that the
implementation plan still carried pre-1.1.1 safety semantics after the accepted
1.1.1 binding merged.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260910T101820Z-governance-state-mutation-08c4fc75`. Claims, edits,
verification, Git, CI, merge and closeout use default policy.

The only tracked paths are:

1. `docs/superpowers/plans/2026-09-10-claims-authority-bridge-wp1-shadow.md`
2. this waiver

No accepted Spec, Ledger/BET, completion/value evidence, implementation, test,
registry, gitlink, hook, CI workflow, branch protection, service, database, timer,
runtime or user configuration may change. This transaction does not initialize or
activate the claims authority and does not count as engineering, operational,
graduation or value evidence.

## Review findings and adjudication

The fixed review inputs are root main
`2b59cdf349ef8a5c0614a62bc8e82be5adedd0fd`, accepted Spec version `1.1.1` with
SHA-256 `7a4cdbae6fb4ce5af09b77438cf56c0b57bddc50e94d3db824ad5d79f1104bae`,
and WorkPacket
`sha256:d844394dcbfb67dcea9e5a770696e12a69b75b36dc88c4fdde2a17140863b4d2`.

The amendment makes only these corrections:

1. Replace stale plan-only 1.0.0/1.1.0 binding facts with the merged 1.1.1
   Spec, digest, WorkPacket, three Wave A paths and 12-day elapsed appetite.
2. Move broker/witness classification before every v1 lifecycle mutation. Only
   pristine total absence or a verified account-resolved `unactivated` witness may
   preserve bootstrap. `prepared`, `shadow-active`, invalid, rollback, unsafe or
   missing-after-initialization state rejects before a v1 write.
3. Add the complete witness-state and activation-crash RED ordering: durable
   `prepared` witness, SQLite activation CAS/receipt, high-water update, then atomic
   `shadow-active` replacement with broker-only reconciliation.
4. Reuse the existing pure SQLite WAL-safety predicate as an admission check. Unsafe
   SQLite fails closed with the frozen `AUTHORITY_STORE_UNSAFE` code before any
   filesystem/DDL mutation; the authority store never downgrades to DELETE and must
   read back actual WAL mode.
5. Keep `lifecycle_locks.py` outside the accepted three-path WorkPacket. In R0 the
   local update lock is best-effort; the canonical run-wide broker CAS, complete
   run/claim and lock-set digests, immediate revalidation and selected-candidate
   deletion provide the durable exclusion. Post-preparation force requests perform
   zero v1 writes. Dedicated RED races cover the legacy 30-second local-lock behavior,
   live-force preservation and prune-candidate drift.
6. Close and hand off the current 1.1.1 Wave A run, never a historical 1.1.0 run.

The WAL and local-lock decisions were independently tie-broken against the accepted
Spec and current code. They require no Spec or write-surface expansion: unsafe WAL
performs zero mutation, while a second process admitted by a best-effort local lock is
rejected by the durable broker CAS before any v1 write.

Audit disclosure: one superseded read-only tie-breaker accidentally invoked
`git write-tree` in this clone. It changed no file, index entry or ref; it may have
created only an unreachable Git tree object. No cleanup, object rewrite or history
mutation was attempted, and the final tracked/index/ref identity was reverified.

## Interrupted Wave A evidence boundary

Wave A attempt
`claims-authority-bridge-wp1-wave-a-20260910-01` stopped before store or lifecycle
implementation. Its first missing-module RED and canonical JSON/digest GREEN are
preserved outside the repository, as is the next missing-API RED. Run
`20260910T095913Z-bet-execution-419b2e45` closed blocked and released all five locks.
No commit, push, PR, root pointer, runtime or value effect occurred. After this plan
amendment merges, a fresh immutable successor must replay only the reviewed child
test/module blobs and continue RED to GREEN under a new 1.1.1 run.

## Delivery and stop conditions

- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-wp1-plan-v111-amend-20260910-02/ws`
- Provenance:
  `ready / c096568f5b0f05dfb2ac815a18d8c197f15b2bda3e349852e3c64e67ed191582`
- Readiness:
  `ready / dfa5f2bc70f613e5115d00f2d86b0cb4169c5010b026ca950aacde1ee9a01d8b`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

The final diff must contain exactly the two paths above. Default workflow
verify/compliance, documentation/GaC checks and two digest-bound read-only reviews
must pass before one normal non-force publication and one unique PR. Required checks
and the full Governance Check must pass before squash merge. Source/merge objects,
the unchanged Spec/WorkPacket, clean post-merge verification and zero locks must be
proved before the Wave A successor starts.

Any scope expansion, Spec/Ledger/implementation/runtime mutation, failed gate, stale
base, remote result unknown, false completion/value claim or attempt to repair the
legacy low-level lock globally stops the transaction. Rollback is an ordinary
reviewed PR restoring the prior plan bytes; it cannot restore the unsafe guidance as
effective execution authority.
