---
type: operations
status: completed
lifecycle: history
owner: governance-agent
created: 2026-09-29
last-reviewed: 2026-09-29
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record — BET-Y2Q4-T10-213 Admission Only

## Reason

ADR-0203 requires a requirement-iteration run to bind a startable BET. The report erratum was
identified after BET-Y2Q4-T10-212 had been accepted and closed, so reusing that BET is rejected
by the workflow source-drift guard. A new BET and its accepted specification must exist before
the normal `project-doc-change` run can start.

The user authorized handling this narrowly scoped report correction, including creating an
independent governance BET and accepted specification. This waiver records the one-time admission
exception needed to resolve that registration/run circular dependency.

## Authorized Registration-Only Actions

- Register `BET-Y2Q4-T10-213` using `bin/gac/ledger-safe-insert.py`.
- Add the accepted specification at
  `docs/superpowers/specs/2026-09-29-bet-213-closeout-chronology-erratum.md` and bind its exact
  digest to the new BET.
- Start and claim the required normal `project-doc-change` workflow bound to BET-213.

## Boundary and Expiry

- This waiver expires as soon as BET-213 and its accepted specification are registered, or if
  registration fails; it does not authorize implementation outside a normally bound workflow.
- It does not authorize changing BET-212 status, completion evidence, retrospective conclusions,
  accepted-specification bytes/digest, or either historical workflow run record.
- The only implementation target is §9 bullet 6 of
  `docs/reports/2026-09-29-projection-plane-phase2-pr3-closeout.md`.
- No other workflow requirement, gate, status, or retrospective conclusion is waived.
