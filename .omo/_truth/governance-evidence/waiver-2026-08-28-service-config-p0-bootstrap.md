---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
title: BET-Y1Q3-T10-43 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-43 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-28T03:13:00Z
who: xiamingxing
quote: "你不行给修复了，我给你授权；不行就创建bet来"
scope:
- docs/superpowers/specs/2026-08-28-service-config-lifecycle-only-repair-design.md
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-43
- .omo/_truth/governance-evidence/waiver-2026-08-28-service-config-p0-bootstrap.md
reason: A new P0 defect had no existing BET; the accepted spec and ledger entry
had to exist before the mandatory `start --bet` could bind a WorkPacket.
risk: No host plist, launchd state, or user configuration is in scope.
residual: Implementation changes use claimed workflow surfaces and remain
separate from host reconciliation.
gate_bypass: 1
no-run-id: true
