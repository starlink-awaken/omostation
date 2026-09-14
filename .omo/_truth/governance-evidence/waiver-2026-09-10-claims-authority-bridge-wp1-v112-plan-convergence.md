---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.1.2 plan convergence
type: doc
---

# Claims Authority Bridge WP1 1.1.2 Plan Convergence

## Delegated authority and exact scope

Current delegated Human authority, verbatim:

> 授权窗口，继续延长吧，延到9月15日24点之前。

The delegation is interpreted in Asia/Shanghai and expires at
`2026-09-16T00:00:00+08:00`. The control Agent records this reversible,
repository-only, operation-specific decision because the accepted 1.1.2 binding
requires a separate plan-convergence transaction before Wave A may restart.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260910T162841Z-governance-state-mutation-41e25360`. Claim, edit,
verification, Git, CI and closeout use default policy. The first claim attempt was
rejected before acquiring a path lock because the affected-graph receipt had not yet
been generated. The controller then generated the canonical receipt and claimed only
the two paths below; no force-lock or repeated workflow was used.

The only tracked paths are:

1. `docs/superpowers/plans/2026-09-10-claims-authority-bridge-wp1-shadow.md`
2. this waiver

No accepted Spec, Ledger/BET, WorkPacket, completion/value evidence,
implementation, test, registry, gitlink, hook, CI workflow, branch protection,
service, database, timer, runtime or user configuration may change. This transaction
does not initialize or activate Claims Authority, does not implement Wave A, and does
not count as engineering, operational, graduation or value evidence.

## Fixed predecessor truth

The transaction starts from root main
`da1ef9756b0c3f1bc370d808bfb461d11f3ad630`, the exact squash merge of PR #3515.
The source and merge trees are both
`94354073b941b43e93f47d0365064725de82cce1`. PR checks had 23 successes, zero
failures and zero pending checks; post-merge Governance Check run `34499694086`
succeeded. Binding run
`20260910T150555Z-governance-state-mutation-3354a087` closed `ok`, released all
six locks and its managed clone retired with a complete external proof,
delete-intent and settlement chain.

The immutable current inputs are:

- accepted Spec version: `1.1.2`;
- Spec SHA-256:
  `bc1de057c28ce91aec5120396bcdedebb3b93b1289fcdc8c81387554efd47192`;
- WorkPacket SHA-256:
  `73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613`;
- write surfaces: exactly the three Wave A child paths;
- BET state: `candidate`, engineering `NOT_STARTED`, operational/value
  `NOT_PROVEN`, overall `evaluating`, `value_indicator_policy=false`.

The plan preimage SHA-256 was
`bdd0de7661cfd36e241e6160e1d89fbf2aa1ff9b7d19acb020c634273a9837ed`.
The first complete convergence candidate has SHA-256
`c7cdea6e9ef63c1da02af7681957e07e1900dabdce18e4bb2eb6bdfe62af6f26`;
fixed-digest review then required the rollback authorization split. The corrected
final review candidate has SHA-256
`9341b117c240799e95d625e38ad893954d20023ebb98bc4234d843ec716f75f4`.
Any later byte change invalidates review and requires a new recorded digest.

## Exact corrections

This transaction only:

1. replaces stale current-1.1.1 plan facts with merged 1.1.2 Spec, digest,
   WorkPacket, closeout and successor prerequisites while preserving 1.1.1 as
   immutable blocked history;
2. freezes the exact auxiliary operator-authorization and stopped-process proof
   schemas, passwd-derived trust root, permissions, time/target/process binding,
   non-authority semantics, production fail-closed verifier boundary and
   `test:<uuid>`-only positive mechanics;
3. adds complete descriptor closure and integration-root WorkPacket recomputation
   tasks, including per-entry/double-read/source-drift REDs and the read-only
   committed-request replay exception;
4. adds unique settlement request identity and separate lost-before-commit,
   lost-after-commit and still-unavailable tests, forbidding repeated v1/Git effects
   and fabricated unknown/operator markers;
5. makes Wave A restart use a fresh child-main successor that replays only the
   reviewed three-path patch, leaving the old implementation clone immutable;
6. requires a fresh non-union `implementation_authorized=false` stop/freeze binding
   before rollback, then a distinct `implementation_authorized=true` binding with
   exact paths and a new WorkPacket for each actual rollback partition, followed by a
   new freeze or next rollback binding; it rejects historical hashes and never
   restores 1.1.1 as current authority; and
7. corrects two non-existent or invalid future verification commands to the current
   script-registry validator and separate rewind/range plus require-main reachability
   gates.

These corrections add no implementation path and do not change the accepted
WorkPacket.

## Clone, receipts and delivery boundary

- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-wp1-v112-plan-convergence-20260911-01/ws`
- Frozen root: `da1ef9756b0c3f1bc370d808bfb461d11f3ad630`
- Provenance: `ready /
  32a326d0011b54d5901cd6a7ae6f2796aa1d31e76eea7f5ba4f458b4ed996242`
- Readiness: `ready /
  f56aa49f2d0b543aa22065700d4222b05cbab9c729b5cc8b7425786dafecaad5`
- Manifest:
  `c56bef487fefc95a4e43ea8b0ac73736a059796c9ba6039cbb135ad0ed43daa9`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

The final diff must contain exactly the plan and this waiver. Default workflow
verify/compliance, documentation and full GaC checks, plus two fixed-digest read-only
reviews, must pass before commit. Publication first attempts effective v1. If v1
rejects solely because of the fixed claims-authority root, a still-live delegated
decision must be recorded outside the repository and bound to the exact commit, tag,
branch and one non-force attempt; the PR must disclose
`changeset_claims_unverified`. Such bootstrap delivery is not v2, graduation or value
evidence. Required checks and post-merge Governance Check must pass before source/
merge object comparison, `ok` closeout, zero-lock proof and clone retirement.

Any scope expansion, stale base, changed Spec/Ledger/WorkPacket, implementation or
runtime mutation, failed gate, unknown remote result, duplicate publication, false
completion/value claim or attempt to restart the old implementation run stops this
transaction. Rollback is an ordinary reviewed successor restoring the prior plan
bytes only; it cannot roll back the accepted 1.1.2 binding or erase preserved review
findings.
