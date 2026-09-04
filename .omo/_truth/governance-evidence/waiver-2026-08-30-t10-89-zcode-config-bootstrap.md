---
schema_version: governance-waiver/v1
lifecycle: history
type: requirement-iteration-waiver
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-89
---

# T10-89 ZCode config mutation authorization

The user explicitly authorized continued Documents execution-plane convergence.
This waiver authorizes only the Workspace-owned atomic repair of the managed
Cockpit entry in `~/.zcode/cli/config.json`.

All unrelated ZCode servers and provider/model settings must be preserved.
Documents/ZCode SQLite, WAL/SHM, credentials, logs, checkpoints, and app
processes are out of scope. Any unexpected diff, mode failure, or config-check
failure must stop and restore the prior config.
