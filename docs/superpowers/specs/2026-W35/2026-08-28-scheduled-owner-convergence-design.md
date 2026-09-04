---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-37
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Scheduled owner convergence design

The `monday-vault-health` Scheduled skill must stop instructing agents to
execute Documents `_control/controller.py` and `@公共/_runtime/check-convergence.py`.
Those instructions form a live execution consumer even when the Scheduled
runner is human/agent initiated.

Replace them with Workspace owner instructions:

1. read the accepted Workspace `controller-preflight` evidence for the Weijian
   control loop;
2. read the accepted Workspace `convergence-preflight` evidence for the
   convergence audit;
3. preserve the same phase/weekly reporting intent, but do not write Documents
   history, reports, or control state.

The edit is limited to the one Scheduled skill. The file is backed up before
mutation, and a before/after SHA plus exact diff is recorded. No cron,
LaunchAgent, or business content is modified in this BET.
