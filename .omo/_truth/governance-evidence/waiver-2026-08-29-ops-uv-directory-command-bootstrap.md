---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: BET-Y1Q3-T10-49 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-49 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-29T00:30:00Z
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来"
scope:
- docs/superpowers/specs/2026-08-29-ops-uv-directory-command-repair-design.md
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-49
- .omo/_truth/governance-evidence/waiver-2026-08-29-ops-uv-directory-command-bootstrap.md
- .omo/_knowledge/retros/BET-Y1Q3-T10-49.md
reason: The canonical service registry exposes a directory-based uv entrypoint,
  but the Service Gateway currently emits an invalid argv shape; a dedicated
  accepted Spec and BET are required before code repair.
risk: No host plist, launchd state, runtime data, or service process is in
  scope; only command compilation and regression evidence will change.
residual: Actual mcp.agora startup and gateway canary remain a separate
  operational activity after this code contract is repaired.
gate_bypass: 1
no-run-id: true
