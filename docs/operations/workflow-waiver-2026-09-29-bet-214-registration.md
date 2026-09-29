---
type: operations
status: completed
lifecycle: history
owner: governance-agent
created: 2026-09-29
last-reviewed: 2026-09-29
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record — BET-Y2Q4-T10-214 Admission Only

## Reason

ADR-0203 requires a requirement-iteration run to bind a startable BET, and
`bin/agent-workflow.py start` rejects a bound BET whose status is `done`
(`BET_STATUS_NOT_STARTABLE`). The three defects repaired here were introduced into main by the
BET-212 closeout itself (#4544, `3748c6798`), which is closed; `BET-Y2Q4-T10-213` is also `done` and
its declared scope is §9 bullet 6 only. So the repair can only be delivered under a newly registered
BET, and that BET cannot be `start`ed until it exists — the same registration/run circular dependency
that `docs/operations/workflow-waiver-2026-09-29-bet-213-registration.md` recorded earlier the same day.

The principal's standing authorization for this plan covers taking the B5 closeout deliverables
through merge, and names updating operations/infrastructure/agent perception as a required part of
the work. Registering a governance BET is the repo-mandated mechanism for that authorized scope, not
an expansion of it; the precedent shape is T10-213. This record makes the one-time admission exception
auditable rather than silent.

## Authorized Registration-Only Actions

- Register `BET-Y2Q4-T10-214` via `bin/gac/ledger-safe-insert.py` (dry-run first, parsed read-back
  after write, per G3 of the accepted specification).
- Add the accepted specification at
  `docs/superpowers/specs/2026-09-29-bet-214-closeout-evidence-integrity.md` and bind its exact digest.
- Start and claim the normal `project-doc-change` workflow bound to BET-214.

## Boundary and Expiry

- Expires once BET-214 and its accepted specification are registered, or if registration fails; it
  authorizes no implementation outside a normally bound workflow run.
- Does not authorize changing `BET-Y2Q4-T10-212`'s `status`, `done_at`, accepted-spec bytes/digest or
  retrospective, nor `BET-Y2Q4-T10-213`'s completion evidence (registered as follow-up G2).
- Implementation targets are limited to: report §9 bullets 1 and 9, `BET-Y2Q4-T10-212.verify[0]`, and
  the six report receipts in `BET-Y2Q4-T10-212.completion_evidence`.
- No other workflow requirement, gate, status, or retrospective conclusion is waived.
