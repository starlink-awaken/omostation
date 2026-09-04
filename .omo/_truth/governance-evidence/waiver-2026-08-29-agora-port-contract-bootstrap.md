---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: BET-Y1Q3-T10-51 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-51 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-29T02:00:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来"
scope:
- docs/superpowers/specs/2026-08-29-agora-port-contract-design.md
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-51
- .omo/_truth/governance-evidence/waiver-2026-08-29-agora-port-contract-bootstrap.md
- .omo/_knowledge/retros/BET-Y1Q3-T10-51.md
reason: The canonical mcp.agora service declares port 7433 while its launched
  Agora SSE process defaults to 7431; a dedicated accepted Spec and BET are
  required before changing the Service Gateway launch environment.
risk: No host process, plist, launchd state, or persistent runtime data is in
  scope; only child-process environment propagation and registry evidence will change.
residual: Actual service startup and production canary remain separate operational work.
gate_bypass: 1
no-run-id: true
