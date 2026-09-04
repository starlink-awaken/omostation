---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
---

# T10-46 BET bootstrap waiver

waiver: user-explicit
when: 2026-08-28T16:00:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来。"
scope: docs/superpowers/specs/2026-08-28-owner-release-root-convergence-design.md; docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-46; this waiver evidence file
reason: Multiple already-installed Workspace owner entries use mixed accepted release roots; a bounded convergence BET is needed before the remaining family parity waves.
risk: Bootstrap changes only the accepted Spec, candidate BET, and waiver evidence; no crontab or Documents mutation occurs in bootstrap.
residual: The actual multi-line crontab update must use a formal governance-state-mutation run with exact line inventory, complete backup, bytewise comparison, smoke, and rollback.
gate_bypass: 1
no_run_id: true
