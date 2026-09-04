---
schema_version: governance-waiver/v1
lifecycle: history
type: requirement-iteration-waiver
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-90
---

# T10-90 BET bootstrap waiver

The user explicitly authorized continued Documents-to-Workspace convergence.
This waiver records the bootstrap exception for registering the state-sync BET
before its accepted specification can be bound: the current main clone has
known missing-submodule health inputs, and the existing state projection is
already stale against the tracked task directory.

The exception permits only this BET/spec registration. The actual projection
mutation must use the OMO state-sync broker after the run starts.
