---
type: operations
status: active
lifecycle: entry
owner: governance-agent
created: 2026-09-25
last-reviewed: 2026-09-25
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record

**Date**: 2026-09-25  
**Agent**: governance-agent  
**Scope**: OMLXC placement runtime recovery and AetherForge transient no-capacity handling

## Reason

ADR-0203 requires a requirement-iteration run to bind an existing startable BET. The current
3Y-BET-LEDGER has no `pending`, `candidate`, or `in_progress` BET, and the closest OMLXC BET
(`BET-Y2Q3-T10-OMLXC-01`) is already `done`. The workflow runner therefore rejects every
attempt to start the required code-change run.

The user explicitly approved creating a new BET after the runner rejected the completed BET:
"先创建新 BET"; after the circular dependency was explained, the user explicitly authorized
"一次 workflow waiver" so the new BET and its bound workflow can be created without silently
bypassing the requirement-iteration gate.

## Authorized Work

- Add `BET-Y2Q3-T10-OMLXC-02` to `docs/plans/3y-bet-ledger.yaml`.
- Create and review the design specification for the approved runtime-recovery slice.
- Modify only the claimed OMLXC and AetherForge source/test surfaces in that BET.
- Run targeted tests, live readiness/inference canaries, workflow verification, and closeout.

## Boundary

- No cost/quota routing implementation in this tranche.
- No model-file, credential, launchd, or remote-runtime mutation.
- No commit, push, merge, or submodule-pointer update without explicit user authorization.
