---
schema: workflow-waiver/v1
status: accepted
lifecycle: evidence
owner: xiamingxing
created: 2026-08-28
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
reason: A new P0 defect has no existing BET; the accepted spec and ledger entry
must exist before the mandatory `start --bet` can bind a WorkPacket.
risk: No workflow run, claim, or lock exists for these three bootstrap files.
residual: All implementation changes must use the newly registered BET workflow.
gate_bypass: 1
no-run-id: true
