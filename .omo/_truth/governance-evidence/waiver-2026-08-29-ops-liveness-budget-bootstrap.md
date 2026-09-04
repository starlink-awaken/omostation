---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: BET-Y1Q3-T10-50 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-50 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-29T01:00:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来"
scope:
- docs/superpowers/specs/2026-08-29-ops-liveness-budget-design.md
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-50
- .omo/_truth/governance-evidence/waiver-2026-08-29-ops-liveness-budget-bootstrap.md
- .omo/_knowledge/retros/BET-Y1Q3-T10-50.md
reason: The Service Gateway health views synchronously probe hundreds of
  services and exceed the command timeout; a dedicated accepted Spec and BET
  are required before changing the shared read-only scan path.
risk: No host service, plist, registry semantics, runtime state, or process is
  in scope; only bounded read-only aggregation and regression tests will change.
residual: Service startup and production Agora canary remain separate
  operational activities.
gate_bypass: 1
no-run-id: true
