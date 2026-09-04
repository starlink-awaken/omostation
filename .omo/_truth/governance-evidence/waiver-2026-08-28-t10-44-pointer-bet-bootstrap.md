---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
---

# T10-44 pointer recovery BET bootstrap waiver

waiver: user-explicit
when: 2026-08-28T12:20:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来。"
scope: docs/superpowers/specs/2026-08-28-omo-gitlink-reachability-recovery-design.md; docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-44; this waiver evidence file
reason: The inherited root gitlink divergence has no claimable BET, so an accepted Spec and candidate BET must exist before the mandatory start --bet workflow can bind the repair.
risk: This bootstrap writes only the accepted Spec, candidate BET, and waiver evidence; it does not modify the gitlink, child repository, runtime state, host schedules, or user data.
residual: After bootstrap lands, the actual gitlink recovery must use a fresh submodule-pointer-close run with exact claims, child-main reachability, PR, CI, and rollback evidence.
gate_bypass: 1
no_run_id: true
