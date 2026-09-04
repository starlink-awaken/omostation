---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-09-03
last_updated: 2026-09-03
value_indicator_policy: false
title: Squash-successor clone retirement accepted binding waiver
type: doc
---

# Squash-Successor Clone Retirement Accepted Binding Waiver

## Principal authorization

> 批准推荐授权包第1—4节原文。

The response approves the recommended authorization package Sections 1
through 4 in full. Section 3 is the operation-specific authorization for this
accepted-binding bootstrap. Sections 1, 2, and 4 authorize separate bounded
operations and do not widen this repository change.

## Canonical workflow waiver evidence

waiver: user-explicit

when: 2026-09-03T01:40:57Z

who: xiamingxing

quote: "批准推荐授权包第1—4节原文。"

scope:

- `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`
- `docs/plans/3y-bet-ledger.yaml::BET-Y1Q4-T1-02`
- `.omo/_truth/governance-evidence/waiver-2026-09-03-squash-successor-retirement-binding.md`

reason: The reviewed draft Spec is accepted, but no startable BET exists until
  the Spec and its initial candidate binding are created atomically.

risk: No workflow run, claim, or lock represents this self-binding commit; the
  exact three-path scope, immutable Spec digest, candidate completion matrix,
  isolated clone, diff review, and PR checks are the compensating controls.

residual: Merge only this accepted binding. Writing-plans, implementation,
  runtime operation, receipt creation, and clone retirement require the later
  phases and their own fresh workflow or operation-specific authorization.

gate_bypass: 1

no-run-id: true

## Approved Section 3 contract

The approved package permits `AGCP_REQUIREMENT_ITERATION_GATE=0` only for this
accepted-binding bootstrap and only for the three paths listed above. It
authorizes:

1. transitioning the reviewed Spec from `0.1.0/draft/unbound` to
   `1.0.0/accepted/BET-Y1Q4-T1-02` and setting
   `last-reviewed: 2026-09-03`;
2. adding exactly one candidate BET, `BET-Y1Q4-T1-02`, with exactly one
   four-key `accepted_specifications` binding to the accepted Spec;
3. initializing engineering as `NOT_STARTED`, operational and value as
   `NOT_PROVEN`, overall as `evaluating`, and
   `value_indicator_policy=false`; and
4. recording this waiver, delivering from the latest main through one unique
   PR, and merging only after the required checks pass.

The ledger keeps repository `write_surfaces` workspace-relative and records
the exact external proof path under
`evidence.future_external_operation_surface`. That path is not claimable by a
repository workflow; Phase 4 requires a separate operation-specific principal
authorization before it may be created or changed.

At the observed base, the canonical instruction pack
`docs/operations/blueprint-agent-instruction-pack-v1.md` is absent. The new BET
records this as a pre-existing baseline blocker; accepted binding does not
claim that Phase 2 is currently startable.

The accepted Spec bytes have SHA-256
`328581a3578c8d780acf39638e5fa0cb2e616a03b5ec73195112ae11c9099ae9`.

## Exact exclusions

This authorization does not permit:

- an implementation plan, implementation code, tests, CLI behavior, registry,
  CI, branch-protection, gitlink, runtime, service, process, lock, or user
  configuration mutation;
- external proof, delete-intent, settlement, provenance, identity, readiness,
  completion, or value evidence mutation;
- quarantine, deletion, retirement, rebasing, reset, or mutation of the
  retained motivating clone;
- any change to another BET, another accepted binding, or any status beyond
  the new candidate's initial matrix;
- marking `BET-Y1Q4-T1-02` or any other BET done, or recording personal value.

## Delivery boundary and rollback

The delivery uses the independent clone
`/Users/xiamingxing/agents/blueprint-retirement-binding/attempts/squash-successor-retirement-binding-20260903-01/ws`
from observed main `dfb4f755dbc45d2947d9d9a10d9a02755a4f0fee`. Before
delivery, mutable main is re-read and any non-equivalent successor requires a
fresh scope and conflict review.

Before merge, close the unique PR if the diff exceeds the exact three paths or
any required check fails. After merge, a failure caused by this binding must be
handled by a separate exact-scope revert PR. Neither path permits code, runtime,
receipt, or retained-clone mutation.
