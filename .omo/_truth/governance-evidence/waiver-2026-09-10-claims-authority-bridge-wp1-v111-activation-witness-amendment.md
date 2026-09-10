---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-10
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.1.1 activation-witness amendment
type: doc
---

# Claims Authority Bridge WP1 1.1.1 Activation-Witness Amendment

## Human authority and scope

Current delegated authority, verbatim:

> 授权窗口，继续延长吧，延到9月15日24点之前。

The delegation is interpreted in Asia/Shanghai and expires at
`2026-09-16T00:00:00+08:00`. It authorizes this reversible, repository-only
binding clarification because the missing distinction can permit a lifecycle
mutation after activation when its broker is unreachable. That is a safety
boundary, not architecture polishing.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260910T091550Z-governance-state-mutation-6ab2e46f`. Claims, edits,
verification, Git, CI and closeout use default policy. The official
process-local lanes `docs,docs_data,governance_state` do not add a path or skip
a gate.

The only tracked paths are:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

No implementation, test, plan, child repository, gitlink, runtime, store,
service, database, timer, CI workflow, branch protection or user configuration
is modified.

## Predecessor and exact successor

The 1.1.0 binding merged in PR #3509 with Spec SHA-256
`032957ededf4b7ade8e9543ae38f322083908a99c840d7e8a52f7300dc2e16cf`
and WorkPacket SHA-256
`09395b02d0c917e3aa1bf25809de27b52c0d82e6395552547d613a45fe53f1ab`.
Its status remained `candidate`, engineering `NOT_STARTED`, operational/value
`NOT_PROVEN`, overall `evaluating`, and `value_indicator_policy=false`.

The post-merge local blocker was repaired by PR #3512 at
`ceaa92fdf26a4d8e185267045948a46024c9da72`. A clean full clone then proved
focused timeout tests 2/2, strict GaC 75/75, the 1.1.0 Spec digest and compiled
WorkPacket digest. The degraded publication remained explicitly
`changeset_claims_unverified`; it is not graduation or value evidence.

Before Wave A implementation, a Contract/Verification review and a scoped
tie-breaker found one logical gap: when the integration-root stdio broker is
unavailable, `lifecycle.py` cannot distinguish pristine pre-activation from an
already activated but failed broker. Treating every unavailable response as
`not_activated` could mutate v1 after activation; treating every unavailable
response as active would deadlock bootstrap.

Version 1.1.1 keeps exactly the same three Wave A write surfaces and adds only
the deny-only, account-resolved monotonic activation-witness contract. The
final bindings are:

- Spec version: `1.1.1`
- Spec SHA-256:
  `7a4cdbae6fb4ce5af09b77438cf56c0b57bddc50e94d3db824ad5d79f1104bae`
- WorkPacket:
  `sha256:d844394dcbfb67dcea9e5a770696e12a69b75b36dc88c4fdde2a17140863b4d2`
- Write surfaces:
  - `projects/omo/src/omo/workflow/claims_authority.py`
  - `projects/omo/src/omo/workflow/lifecycle.py`
  - `projects/omo/tests/test_workflow_claims_authority_bridge.py`

The witness may only make behavior more conservative when stdio is unavailable.
Pristine total absence or a verified `unactivated` witness preserves bootstrap;
`prepared`, `shadow-active`, invalid, rollback, unsafe or
missing-after-initialization state rejects before a v1 mutation/effect. It
cannot grant a claim, issue/settle a receipt or fence, authorize Git, select a
store, or replace the broker.

## Clone identity and verification contract

- Frozen root main:
  `ceaa92fdf26a4d8e185267045948a46024c9da72`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-wp1-v111-binding-20260910-01/ws`
- Provenance:
  `ready / d3b3a63f55014f5556bcc183a883c32e2d9497fb569c2cf1da2ec9083bc18e38`
- Readiness:
  `ready / a3b85d045a4744e8ea4990e360cd7e7bed9b23adb6cbe67fb71d13ed2246e812`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

Before publication, Ledger lint, portfolio lint, exact binding/WorkPacket
recomputation, workflow verify/compliance, local GaC and two digest-bound
reviews must pass. Publication is one normal non-force attempt and one unique
PR. Required contexts must pass before squash merge. Post-merge final objects,
the 1.1.1 Spec digest, WorkPacket digest and zero locks must be proven before a
Wave A Writer starts.

Any scope union, plan/implementation/runtime edit, completion/value expansion,
invalid witness grant semantics, failed gate, unknown remote result or stale
base stops this transaction. Rollback is an ordinary reviewed PR restoring the
exact 1.1.0 binding; it does not erase this gap or authorize Wave A under 1.1.0.
