---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: BET-Y1Q3-T10-110 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-110 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-31T02:26:48+08:00
who: xiamingxing
quote: "全面推进吧"
prior_authorization: "我给你授权，按照标准流程推进吧。不行就创建bet来"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-110
- docs/superpowers/specs/2026-08-31-documents-runner-log-quarantine-design.md
- .omo/_truth/governance-evidence/waiver-2026-08-31-t10-110-bootstrap.md
reason: No existing candidate BET covers the separately approved exact runner-log quarantine, and a registered BET with an immutable accepted specification is required before a formal implementation and host-mutation workflow can start.
risk: Bootstrap declarations only; no transaction implementation, migration registry, Documents path, Workspace runtime payload, host process, schedule, or completion verdict is authorized by this waiver itself.
residual: Merge and replay the bootstrap PR, obtain written spec review, then use formal BET-bound implementation and host runs with exact claims, RED-to-GREEN tests, capability-before-apply ordering, and a separate closeout PR.
gate_bypass: 1
no-run-id: true
