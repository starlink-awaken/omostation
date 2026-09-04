---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: BET-Y1Q3-T10-99 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-99 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-30T12:30:00+08:00
who: xiamingxing
quote: "不行就创建bet来"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-99
- docs/superpowers/specs/2026-08-30-learning-runtime-owner-parity-design.md
- .omo/truth/governance-evidence/waiver-2026-08-30-t10-99-learning-runtime-bootstrap.md
reason: No existing BET covers learning-runtime owner parity; a candidate BET and accepted specification must exist before the mandatory start --bet run can bind the implementation.
risk: This waiver covers only the bootstrap declaration. All implementation, host evidence, and closeout work must use the newly started governed run; no Documents or host runtime mutation is authorized by this bootstrap waiver.
residual: The read-only owner parity, consumer evidence, and later physical quarantine remain governed deliverables of BET-Y1Q3-T10-99 and follow-up BETs.
gate_bypass: 1
no-run-id: true
