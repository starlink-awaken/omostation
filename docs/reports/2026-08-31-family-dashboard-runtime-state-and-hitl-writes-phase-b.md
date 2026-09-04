---
lifecycle: history
owner: family-hub
created: 2026-09-02
last_updated: 2026-09-02
title: Family dashboard Phase B runtime and HITL evidence
type: doc
bet_id: BET-Y1Q3-T10-122
---

# Family dashboard Phase B runtime and HITL evidence

## Verdict

The family dashboard has a verified Workspace-owned runtime state beneath
`runtime/family-hub/dashboard`. After an observed unbound partial target was
recovered, two isolated, macOS-sandboxed builds again consumed Documents as a
read-only source, produced equal normalized products, and atomically promoted
the resulting state. The canonical receipt remains verified after a read-only
service health canary.

This is a non-terminal Phase B evidence report, not the Task 12 final closeout.
No approved Documents write canary has run, so the HITL operational transaction,
final retrospective, ledger completion, Phase C cutover, user value, legacy
retirement, and Documents-wide physical purity remain unproven.

## Authority and engineering lineage

- Accepted specification: `docs/superpowers/specs/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b-design.md`, version `1.2.0`, digest `sha256:46f904e4f299ea02a1491fbfbfee2e271f2999e7c84786632e770de7c1212926`.
- Implementation plan: `docs/superpowers/plans/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b.md`.
- Derived parity child PR: `starlink-awaken/omostation-family-hub#10`, merged at `04c74474ca9d64268169e3abf976473c6334d75a`.
- Real-input hardening child PR: `starlink-awaken/omostation-family-hub#11`, merged at `68134975ea047ecaebc74011fda935232d73fc6e`.
- Live-source verifier child PR: `starlink-awaken/omostation-family-hub#12`, merged at authoritative child main `1991fdda184770c459ef879a4cae90ee435e964d`.
- Partial-runtime recovery child PR: `starlink-awaken/omostation-family-hub#13`, merged at authoritative child main `225a3db598d44a2b89fe708c53f552676435ca87`.
- Root pointer PR `#2916` admitted that recovery owner; root contract PR `#2918` bound the 1.2 recovery surface and protocol. Root `main` at the recovery observation is `db63c4eb7a78f384777de028b01dedc7c63d8409`; its family-hub gitlink is exactly `225a3db598d44a2b89fe708c53f552676435ca87`.
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
- `migration/recovery.json`: `sha256:b53f2a42f5deaee1cf4bc456cb72702e87b9fdd0a2731a142ca8c85c515bf179`.
- Workflow run `20260901T095453Z-bet-execution-81135886` plan evidence:
  `sha256:3737503abb8e97b0c276f97ddc739a119fecb9b2b5c66f14f22b93377c1772c1`.
- Its apply and final verify evidence both digest to
  `sha256:76345eb60a5268dab22fe079b11da6ef6359417f0aaa00f572d0ab2362f0e3d8`.

The underlying plan, apply, and verify evidence is pathless JSON: no raw
Documents path or document body is stored in the report-facing artifacts.

## Partial runtime recovery evidence

At recovery preflight, the canonical target was non-empty but unbound: it
contained only `generated/tasks.json` and a prior private server-canary log;
`migration/plan.json` was absent. This report does not attribute that partial
state to an actor because no authenticated deletion evidence was available.

The 1.2 recovery owner first recomputed the source fingerprint, then atomically
renamed the complete partial target to the retained private sibling
`runtime/family-hub/.dashboard.recovery-a8e2f11c48b1-81ea0430d894`. It rebuilt
the ordinary canonical root and required the preserved and rebuilt task digest
to match exactly:

- partial inventory: `2` regular files, digest
  `sha256:81ea0430d894c78678db111d75dee7ecf925b8d74d3272ed465fa0f5b23ed964`;
- preserved/rebuilt task digest:
  `sha256:b3d52e663fd33fc2e47d6fbd5d6f1278d684fd7b58f4a53db37d4d1f7110b726`;
- recovery workflow run: `20260902T035529Z-bet-execution-bb4fd1de`; and
- recovery result: `family-dashboard-runtime-recovery/v1`, `recovered`, with
  `writes_documents=false`.

The sibling remains private-mode and intentionally retained. It is evidence of
recoverability, not an active runtime root or a cleanup authorization.

A later canary preflight observed a second unbound partial target with the
same task digest but a changed private canary-log digest. Its distinct inventory
digest `sha256:7327248d885f555d897a92de3fae0f66cb681438af2bd9caf93e87e226c26a0e`
therefore produced a second retained sibling:
`runtime/family-hub/.dashboard.recovery-a8e2f11c48b1-7327248d885f`.
The managed recovery was rerun in a persistent session (so interruption could
not be mistaken for a build failure), restored a verified canonical runtime,
and again proved the identical task digest and `writes_documents=false`.

## Read-only operational checks

- The four path/generated-data validators passed against canonical state.
- A temporary localhost server was built without re-running data generation,
  started with the canonical state roots, and returned a successful
  `/api/health` response. Its log is private-mode runtime evidence, not a
  persistent service registration.
- The recovery replay re-ran the validators and health canary. The plan now
  requires `umask 077` for canary logs; the recovery logs were corrected and
  checked as `0600`, and the server PID was stopped after the health response.
- The post-canary `verify-runtime` replay stayed `verified`, with unchanged
  closure/source fingerprints and parity.
- The Documents consumer audit found `218` active consumers,
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
