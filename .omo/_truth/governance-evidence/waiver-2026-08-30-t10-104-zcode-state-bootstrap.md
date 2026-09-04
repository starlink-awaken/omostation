---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: BET-Y1Q3-T10-104 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-104 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-30T18:58:00+08:00
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-104
- docs/superpowers/specs/2026-08-30-zcode-workspace-runtime-state-relocation-design.md
- docs/superpowers/plans/2026-08-30-zcode-workspace-runtime-state-relocation.md
- .omo/_truth/governance-evidence/waiver-2026-08-30-t10-104-zcode-state-bootstrap.md
reason: The new BET and accepted specification must exist before `start --bet` can bind the separately authorized ZCode state relocation.
risk: Bootstrap declarations only. No code, ZCode process, settings, Documents state, Workspace runtime target, or migration registry may change under this waiver.
residual: Implementation, quiescence, host transaction, restart, evidence, PR, merge, and closeout require the governed run and circuit breaker.
gate_bypass: 1
no-run-id: true

formal_execution:
  bootstrap_pr: 2733
  entry_scope_pr: 2738
  durable_spec_amendment_pr: 2745
  durable_spec_main_commit: 71176717eff24d23fcf45add5e2287b78cc718b5
  superseded_runs:
  - 20260830T110058Z-bet-execution-7bbee016
  - 20260830T112213Z-bet-execution-3967ee4f
  - 20260830T120055Z-bet-execution-e8fa0e5f
  recovery_run_id: 20260830T123805Z-bet-execution-ae67ed0f
  closeout_run_id: 20260830T132955Z-bet-execution-49139b8d
  implementation_main_commit: 8737b24a14e2de4ca68116a3f5b52f4e2c905c18
  status: verified
  note: The waiver remains bootstrap-only. The durable recovery is governed by accepted Spec 1.0.1, exact claims, and a mainline amendment.
