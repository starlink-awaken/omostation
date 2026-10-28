---
type: operations
status: active
lifecycle: workflow-requirement-iteration-waiver
owner: governance-team
created: 2026-10-15
last-reviewed: 2026-10-15
scope: BET-Y2Q4-T10-253-registration-only
---
# Workflow Waiver Record — BET-Y2Q4-T10-253 Admission Only

## Reason

ADR-0203 requires requirement delivery to start with a registered, startable BET. The user explicitly authorized registering a BET on 2026-10-15 after the normal workflow rejected the initial start because no BET ID was supplied. This record captures the one-time registration exception; it does not waive the normal implementation workflow.

## Authorized Registration-Only Actions

- Add the accepted specification `docs/superpowers/specs/2026-10-15-lifeos-magpie-shared-skill-link-repair.md` bound to BET-Y2Q4-T10-253.
- Register BET-Y2Q4-T10-253 with `bin/gac/ledger-safe-insert.py` after a successful dry-run.
- Claim the BET and start/claim the required `external-adapter-sync` workflow.

## Boundary and Expiry

- This waiver expires when the BET and accepted specification are registered and the normal workflow is started and claimed, or if registration fails.
- It authorizes no implementation outside the bound workflow and no commit or push.
- Implementation scope is only the eight skill links and audit/rollback evidence defined by BET-Y2Q4-T10-253.
- It does not authorize changes to LifeOS core, USER/MEMORY, credentials, unrelated client configuration, or unresolved MCP/skill mappings.
