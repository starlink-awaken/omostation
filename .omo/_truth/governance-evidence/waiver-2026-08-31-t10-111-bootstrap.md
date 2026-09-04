---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: BET-Y1Q3-T10-111 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-111 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-31T03:40:07+08:00
who: xiamingxing
quote: "全面推进吧"
prior_authorization: "我给你授权，按照标准流程推进吧。不行就创建bet来"
delivery_requirement: "记得pr合并提交"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-111
- docs/superpowers/specs/2026-08-31-family-dashboard-owner-migration-phase-a-design.md
- .omo/_truth/governance-evidence/waiver-2026-08-31-t10-111-bootstrap.md
reason: No existing candidate BET covers the approved first phase of moving the mature family dashboard application out of Documents and into the existing family-hub owner. A registered BET with an immutable accepted specification is required before the child implementation workflow can start.
risk: Bootstrap declarations only. This waiver does not authorize importing private household data, changing family-hub or Cockpit code, mutating Documents, moving runtime payloads, cutting over consumers, deleting the old application, or claiming parity, value, or Documents-wide purity.
residual: Merge and replay the bootstrap PR, obtain written specification review, then use formal BET-bound child and root workflows with exact claims, test-first implementation, child-before-root PR ordering, required CI, mainline replay, and separate Phase B and Phase C admission.
gate_bypass: 1
no-run-id: true
