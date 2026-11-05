---
type: operations
status: active
lifecycle: workflow-requirement-iteration-waiver
owner: governance-team
created: 2026-10-16
last-reviewed: 2026-10-16
scope: BET-Y2Q4-T10-254-registration-only
---
# Workflow Waiver Record — BET-Y2Q4-T10-254 Registration Only

## Reason

ADR-0203 requires a registered, startable BET before a requirement-iteration workflow can start. The user authorized completion of the Magpie/LifeOS optimization plan and separately authorized BET registration. The MP-008 route-contract work needs a new BET because the existing LifeOS skill-link BET has a different scope.

## Authorized registration actions

- Add the accepted specification `docs/superpowers/specs/2026-10-16-aetherforge-magpie-local-only-route-contract.md`.
- Register BET-Y2Q4-T10-254 using `bin/gac/ledger-safe-insert.py` after a successful dry run and parsed readback.
- Start and claim the normal `project-code-change` workflow for that BET.

## Boundary and expiry

- This waiver covers registration and normal workflow admission only. It does not waive implementation, review, verification, deployment, or rollback requirements.
- Implementation is limited to the accepted specification and its listed write surfaces.
- It expires once BET-254 and its accepted specification are registered and the normal workflow is started and claimed, or if registration fails.
- It authorizes no commit, push, publication, unrelated client changes, credential changes, or LifeOS core/USER/MEMORY changes.
