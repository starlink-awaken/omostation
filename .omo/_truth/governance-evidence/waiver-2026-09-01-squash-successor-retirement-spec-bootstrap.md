---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-09-01
last_updated: 2026-09-01
value_indicator_policy: false
title: Squash-successor clone retirement draft Spec bootstrap waiver
type: doc
---

# Squash-Successor Clone Retirement Draft Spec Bootstrap Waiver

## Principal authorization

> 批准采用方案 A；本次 squash-successor clone retirement draft Spec 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限 `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md` 以 `status: draft`、`bet_id: unbound` 写入，以及 `.omo/_truth/governance-evidence/waiver-2026-09-01-squash-successor-retirement-spec-bootstrap.md` 记录本句；不得修改 ledger、BET、实现代码、测试、现有 provenance/identity receipt、运行态或保留 clone；书面 Spec 经我复核前不得转 accepted、建立 binding、实施或删除 clone。

## Canonical workflow waiver evidence

waiver: user-explicit

when: 2026-09-01T07:11:40Z

who: xiamingxing

quote: "批准采用方案 A；本次 squash-successor clone retirement draft Spec 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限 `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md` 以 `status: draft`、`bet_id: unbound` 写入，以及 `.omo/_truth/governance-evidence/waiver-2026-09-01-squash-successor-retirement-spec-bootstrap.md` 记录本句；不得修改 ledger、BET、实现代码、测试、现有 provenance/identity receipt、运行态或保留 clone；书面 Spec 经我复核前不得转 accepted、建立 binding、实施或删除 clone。"

scope:

- `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`
- `.omo/_truth/governance-evidence/waiver-2026-09-01-squash-successor-retirement-spec-bootstrap.md`

reason: The new retirement topology has no existing candidate BET and requires a reviewable draft before accepted binding.

risk: No workflow run, claim, or lock represents this draft bootstrap; the exact path scope, explicit lane set, waiver, diff, and PR checks are the compensating evidence.

residual: Merge only the draft bootstrap, obtain principal review of the written Spec, and require a separate accepted-binding authorization before any ledger, plan, code, test, receipt, runtime, or clone mutation.

gate_bypass: 1

no-run-id: true

## Bootstrap identity

- Workflow run: none; the principal explicitly authorized this exact
  workflow-start waiver.
- Requirement gate override:
  `AGCP_REQUIREMENT_ITERATION_GATE=0`, limited to the exact two repository
  paths below and their delivery commit.
- Actor:
  `blueprint-governance-spec-bootstrap`.
- Delivery attempt:
  `squash-successor-retirement-spec-bootstrap-20260901-01`.
- Initial pinned clone base:
  `f6a1e0bc5f04d219dfd347d2e1272fed87343c60`.
- Final delivery base:
  `9916abe7403ca3280370921b9e7bc1172912773b`.
- Successor admission: both authorized paths remained absent at the final
  delivery base, the draft Spec bytes/digest remained unchanged, and no open PR
  occupied either path. The bootstrap branch contains exactly one delivery
  commit above that base.
- Clone topology: independent governance-profile clone with ready provenance
  and readiness receipts; no workflow run or lock was created.
- The previously retained architecture-perception delivery clone is a
  read-only evidence source and is not modified by this bootstrap.

## Exact authorized write scope

1. `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`
   with `status: draft`, `spec_version: 0.1.0`, and
   `bet_id: unbound`;
2. this waiver evidence file.

No other repository or external path is authorized.

## Explicit prohibitions

This bootstrap does not authorize:

- any ledger or BET mutation;
- accepted status, accepted-specification binding, decision binding, or
  writing-plans;
- implementation code, tests, CLI behavior, registry, warning budget, CI, or
  branch-protection changes;
- existing clone identity, provenance, readiness, baseline, changeset, or
  completion/value evidence mutation;
- runtime, service, process, lock, user configuration, or external receipt
  mutation;
- deletion, quarantine, retirement, rebase, reset, or branch manipulation of
  the retained motivating clone;
- marking any BET done or recording personal value.

## Purpose and review boundary

The bootstrap records the already approved design as a reviewable repository
draft. It does not accept the design for implementation. After the bootstrap PR
is merged, the principal must review the written Spec. Only a later,
separately authorized accepted binding may add a candidate BET and permit
writing-plans.

## Draft and validation evidence

- Draft Spec SHA-256:
  `222106b0f3f0f24c35901b44f1cab3004e257c9f9a3cbbf655daf2b528c44f5a`.
- Self-review found no placeholder, unresolved implementation instruction,
  scope expansion, or contradictory accepted/binding state.
- Both files passed the single-file documentation SSOT lint.
- File-scoped document governance returned zero errors and zero warnings.
- Agent-workflow lint passed; the optional uninstalled `gstack` adapter
  remained an explicit non-blocking warning.
- The first change-lane classification is `docs + governance_state`.
  The principal authorized one exact two-file bootstrap commit, so the
  registered explicit-lane contract was supplied process-locally as
  `AGENT_WORKFLOW_ALLOWED_LANES=docs,governance_state`. No advisory mode,
  workflow policy, profile, registry, or gate code was changed.
- File-scoped GaC completed 56 checks with zero hard failures. The unrelated
  current-main soft warnings `governance-semantic-gate` and
  `command-discovery` remained visible and are not represented as repaired.
- The retained motivating clone remained clean and unchanged.

## Independent review and correction

- Orca Run / Task / Dispatch:
  `run_99a704beb1ce` /
  `task_e4b0b793bfe6` /
  `ctx_959489b60f76`.
- First review outcome: `NEEDS_CHANGES`.
- Finding 1: a pre-delete proof plus absent destination could not distinguish
  canonical deletion from a quarantine crash or manual deletion.
- Correction 1: the draft now requires an immutable digest chain of proof,
  post-quarantine delete-intent, and post-delete settlement receipts. It
  defines exact recovery for crash-after-quarantine and
  crash-after-delete-before-settlement, rejects proof-only absence and
  unexpected quarantines, and does not report success until settlement is
  durable.
- Finding 2: Phase 1 could be read as allowing accepted binding merely after
  review.
- Correction 2: Phase 1 now requires a new, separate, operation-specific
  principal authorization before accepted binding.
- The reviewer was strict read-only, modified no file, and its settled terminal
  was released and acknowledged.

- Second review Task / Dispatch:
  `task_5120367dc7ce` /
  `ctx_050ea5df94ca`.
- Second review outcome: `NEEDS_CHANGES`.
- Finding 3: the waiver lacked the canonical workflow-waiver evidence fields.
- Correction 3: this waiver now contains literal
  `waiver/when/who/quote/scope/reason/risk/residual` fields plus
  `gate_bypass: 1` and `no-run-id: true`.
- Finding 4: the CLI example used unresolved path placeholders.
- Correction 4: the example now names the exact retained motivating clone and
  its exact external proof path.
- Finding 5: settlement durability and the pre-delete restore boundary were
  ambiguous.
- Correction 5: settlement now explicitly inherits no-follow, exclusive
  create, file/parent fsync, and exact-match replay. The Spec distinguishes
  live pre-delete restoration, preserved unrecorded crash quarantine, and
  post-delete settlement recovery.

## Rollback

- Before merge: close the unique PR; keep the branch/tag for inspection.
- After merge: if these two files cause a required or exact-SHA post-merge
  failure, create a new two-file revert PR.
- Never repair ledger, implementation, tests, runtime, receipts, or retained
  clone state inside this bootstrap or its revert.
