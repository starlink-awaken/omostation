---
schema: workflow-waiver/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
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
