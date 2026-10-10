---
schema: md/v1
status: active
lifecycle: governance-evidence
owner: dashboard-convergence
created: 2026-10-08
type: workflow-waiver
value_indicator_policy: false
---

# Dashboard DCP-20 BET/Spec bootstrap waiver

## Principal authorization

> 给你充分授权，选择合适的流程和方式，进行全面落地，针对已有的阻塞点，可以适当推进修复或者处理。

This authorization is applied narrowly to bootstrap one accepted DCP-20 P0 Spec and its BET Ledger entry, because `agent-workflow start` requires the BET and accepted Spec before the workflow can be created. It does not authorize cleanup or takeover of any existing Run or Lock.

## Exact waiver boundary

- `docs/superpowers/specs/2026-10-08-dashboard-dcp20-get-method-safety.md`
- `docs/plans/3y-bet-ledger.yaml::BET-Y2Q4-T10-236`
- This evidence record

The waiver does not permit implementation edits, host synchronization, service restart, projection publication, G0/M0 bypass, or any other Ledger/Run/Lock mutation before the accepted Spec and BET are registered and a standard `bet-execution` run is started with exact path claims.

## Workflow evidence

- workflow: `bet-execution`
- profile: `engineering-agent`
- requirement: establish the accepted BET/Spec that the required workflow resolves before `start` can create its run.
- `AGCP_REQUIREMENT_ITERATION_GATE=0` is not exported globally; if required for the bootstrap command, it is scoped to that command only.
- after bootstrap: standard `bootstrap → status → start → claim → edit/test → verify → closeout` lifecycle applies.

