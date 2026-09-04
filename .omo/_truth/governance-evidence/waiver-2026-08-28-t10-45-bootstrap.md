---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
---

# T10-45 BET bootstrap waiver

waiver: user-explicit
when: 2026-08-28T15:00:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来。"
scope: docs/superpowers/specs/2026-08-28-domain-index-release-root-reconciliation-design.md; docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-45; this waiver evidence file
reason: The installed domain-index owner line has a stale accepted release root, but the original migration BET remains blocked by missing historical backup evidence; a distinct reconciliation BET is needed.
risk: Bootstrap changes only the accepted Spec, candidate BET, and waiver evidence; it does not mutate the crontab or Documents.
residual: The actual one-line host mutation must use a formal governance-state-mutation run with exact backup, claim, bytewise comparison, smoke, and rollback evidence.
gate_bypass: 1
no_run_id: true
