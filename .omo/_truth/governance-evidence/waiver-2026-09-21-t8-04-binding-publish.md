---
id: waiver-2026-09-21-t8-04-binding-publish
scope: BET-Y2Q2-T8-04 accepted specification binding publication
created: '2026-09-21'
owner: governance-team
status: active
lifecycle: history
last-reviewed: '2026-09-21'
type: governance-evidence
---

# T8-04 binding publication waiver

## Authority

The active recovery objective authorizes dashboard and execution-environment
repair. Because the BET is initially a candidate and this transaction only
publishes its accepted binding, canonical Workspace run
`20260921T065130Z-governance-state-mutation-bffb5294` used
`AGCP_REQUIREMENT_ITERATION_GATE=0` once as an unbound start prefix. Claims,
changeset verification, publication, PR checks, merge, closeout, and clone
retirement use default gates.

## Boundary

Only add the canonical accepted specification binding for
`BET-Y2Q2-T8-04`, this waiver, and the specification at its recorded digest.
Do not change implementation, tests, value evidence, other BETs, gitlinks,
runtime state, branch protection, or Claims Authority lifecycle.

## Verification and rollback

The spec digest must remain
`sha256:2ffcc58d6ff14a745853a96fbfe61865e171aad558d88c14a50b96ad9955818a`,
ledger lint must pass, and all required PR checks must pass. Rollback is
limited to reverting the binding, waiver, and specification.
