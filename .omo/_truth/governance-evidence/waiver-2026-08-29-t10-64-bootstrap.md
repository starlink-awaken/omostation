---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: BET-Y1Q3-T10-58 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-58 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-29T07:40:00Z
who: xiamingxing
quote: "依次解决吧，按照标准流程执行，注意，如果是机制方案更新，需要做好治理规范和agent感知相关工作"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-58
- .omo/_truth/governance-evidence/waiver-2026-08-29-t10-58-bootstrap.md
- .omo/_knowledge/retros/BET-Y1Q3-T10-58.md
- projects/omo/src/omo/resident/decision.py
- .githooks/commit-msg
- AGENTS.md
reason: The 2026-08-29 unattended god-module extraction wave left committed but
  non-importable code in the local omo child branch (workflow CLI red line
  broken since 09:35), plus recurring resident decision-inbox noise and a
  chore(state) commit-reset churn on local main. No open bet covers
  projects/omo fallout repair; T4-02's work packet rejects those paths and
  T10-54 (the prior instance of this disease) is delivery_accepted.
risk: Hook change only rejects a narrow commit genre (chore(state) on local
  main) that branch protection already refuses to push; resident guard only
  suppresses drafts that carry no trace/event provenance and are unreadable
  placeholders. No runtime, host plist, or launchd state changes.
residual: Reconciliation of the diverged local omo child branch (rebase onto
  origin/main, push, pointer transaction) stays a documented follow-up while
  the unattended extraction session remains active.
gate_bypass: 1
no-run-id: true
