---
status: active
lifecycle: history
owner: family-hub
created: 2026-09-02
last-reviewed: 2026-09-02
title: Family dashboard Phase B runtime and HITL evidence
type: doc
bet_id: BET-Y1Q3-T10-122
---

# Family dashboard Phase B runtime and HITL evidence

## Verdict

The family dashboard now has a verified Workspace-owned runtime state beneath
`runtime/family-hub/dashboard`. Two isolated, macOS-sandboxed builds consumed
Documents as a read-only source, produced equal normalized products, and
atomically promoted the resulting state. The canonical receipt remains
verified after a read-only service health canary.

This is a non-terminal Phase B evidence report, not the Task 12 final closeout.
No approved Documents write canary has run, so the HITL operational transaction,
final retrospective, ledger completion, Phase C cutover, user value, legacy
retirement, and Documents-wide physical purity remain unproven.

## Authority and engineering lineage

- Accepted specification: `docs/superpowers/specs/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b-design.md`, version `1.1.0`, digest `sha256:0a82d770edcca8d6a21b6b32e1798270b34c1c0b8e72a2518f2baa8ce0e7c809`.
- Implementation plan: `docs/superpowers/plans/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b.md`.
- Derived parity child PR: `starlink-awaken/omostation-family-hub#10`, merged at `04c74474ca9d64268169e3abf976473c6334d75a`.
- Real-input hardening child PR: `starlink-awaken/omostation-family-hub#11`, merged at `68134975ea047ecaebc74011fda935232d73fc6e`.
- Live-source verifier child PR: `starlink-awaken/omostation-family-hub#12`, merged at authoritative child main `1991fdda184770c459ef879a4cae90ee435e964d`.
- Root pointer PRs `#2896`, `#2899`, and `#2900` separately admitted those child-main advances. Root `main` at observation is `643b32597633e9db4a6844c1c64fa2a639dbe2cc`; its family-hub gitlink is exactly `1991fdda184770c459ef879a4cae90ee435e964d`.
- Every named child PR passed build, dashboard, dashboard E2E, lint, and Python CI. Every named root pointer PR passed required `bet-done-transition`, `gac-gate`, and `phase-gate`, plus the full root governance suite.

## Runtime materialization evidence

The canonical runtime layout is private-mode, non-symlink state outside both
Git and Documents. The final receipt reports:

| Assertion | Observed evidence |
| --- | --- |
| Receipt schema/status | `family-dashboard-runtime-receipt/v1` / `verified` |
| Manifests / generated products | `6` / `17` |
| Input closure | `2972` files; digest `sha256:79f951317d719647a1a52d40d0417e3373193be56a2f3b2e3e0cf490a78bbc41` |
| Source fingerprint | `sha256:a8e2f11c48b1c7793b28eae01632d9b271a68ad6749a98abff737068bfb77034` |
| Fresh-build parity | `equal` |
| Legacy delta | `observed`, count `12` |
| Cache seed count | `0` |
| Documents writes | `false` |
| Runtime hygiene | zero symlinks and zero `.dashboard.staging-*` siblings; directories `0700`, files `0600` |

The current canonical artifact digests are:

- `migration/plan.json`: `sha256:0ec564392038b093631be51b3ee818eff38a3125681e4354e9067c764377ea31`.
- `migration/receipt.json`: `sha256:97510525f11df32f8af6afc0967db030249547934ebea82a17996393aff95c7b`.
- `migration/parity.json`: `sha256:866e1890ed8ab31f9ee0d935f4749976730c2814f1fa4464795f8e82e5dc13e5`.
- Workflow run `20260901T095453Z-bet-execution-81135886` plan evidence:
  `sha256:3737503abb8e97b0c276f97ddc739a119fecb9b2b5c66f14f22b93377c1772c1`.
- Its apply and final verify evidence both digest to
  `sha256:76345eb60a5268dab22fe079b11da6ef6359417f0aaa00f572d0ab2362f0e3d8`.

The underlying plan, apply, and verify evidence is pathless JSON: no raw
Documents path or document body is stored in the report-facing artifacts.

## Read-only operational checks

- The four path/generated-data validators passed against canonical state.
- A temporary localhost server was built without re-running data generation,
  started with the canonical state roots, and returned a successful
  `/api/health` response. Its log is private-mode runtime evidence, not a
  persistent service registration.
- The post-canary `verify-runtime` replay stayed `verified`, with unchanged
  closure/source fingerprints and parity.
- The Documents consumer audit found `207` active consumers,
  `forbidden_executors=0`, `unmatched=0`, and no Documents writer introduced
  by this delivery.
- The content-plane migration check found all sampled migration families uniquely
  classified with zero errors. The family-dashboard-app family remains
  explicitly non-terminal.

## Architecture boundary now in force

Documents remains the household source/content plane. Workspace owns runtime
state, generated products, cache, migration receipts, and temporary operational
logs. The dashboard build subprocesses are sandboxed so Documents cannot be
written during runtime materialization. The approved mutation path remains a
separate, proposal-mediated capability: Cockpit supplies the human action, OMO
owns durable proposal/receipt truth, Agora provides the declarative internal
BOS route, and family-hub owns the CAS transaction.

This report proves the read-only half of that boundary and its engineering
integration. It does not prove an approved mutation transaction in the live
Documents plane.

## Real-data hardening learned during materialization

The first production attempts failed before promotion and left the canonical
target absent. Each failure became a regression-tested child fix before a new
root pointer was accepted:

1. Legacy generated JSON contained unpaired Unicode surrogates; canonical
   product hashing now uses deterministic ASCII escapes.
2. The input closure initially over-included builder-ignored control metadata
   and archived dependency nodes; it now matches actual builder inputs while
   still rejecting symlinks in genuine inputs.
3. The summary verifier contained a stale source-date assertion and build logs
   could contaminate CLI JSON stdout; it now derives expectations from current
   control documents and sends sandboxed build logs to stderr.

These repairs are bounded to deterministic read-only materialization. They do
not relax the mutation approval, CAS, rollback, or path-containment contracts.

## Completion matrix at this checkpoint

| Axis | Status | Basis |
| --- | --- | --- |
| Child/root engineering authority | `VERIFIED` | Merged child and root PR chain with required CI |
| Read-only runtime materialization | `PROVEN` | Canonical receipts, parity, modes, validators, and health canary |
| Live HITL Documents write and rollback | `NOT_PROVEN` | No exact approval artifact or write canary |
| Full Phase B operational delivery | `NOT_PROVEN` | Requires the approved create-and-rollback transaction |
| Phase C entry cutover and legacy retirement | `NOT_PROVEN` | Explicit non-goals |
| Principal-bound value | `NOT_PROVEN` | No user-value evidence |
| Documents-wide physical purity | `NOT_PROVEN` | Outside this bounded migration |

## Remaining human gate

Task 11 requires a separate explicit approval for the exact dedicated,
non-private canary target. That transaction must create, verify, roll back to
absence, and preserve immutable OMO/family-hub receipts. Until that approval is
recorded and the real rollback is verified, do not create the approval file,
do not update the ledger to `done`, and do not write the final six-question
retro.
