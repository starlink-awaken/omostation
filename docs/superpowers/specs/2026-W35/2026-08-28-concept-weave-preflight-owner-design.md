---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-39
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Concept weave preflight owner design

The monthly concept-weave LaunchAgent currently executes a Documents shell
writer that mutates concept notes, Documents logs/history, and sometimes inbox
todo files. Replace only its scheduled execution boundary with a Workspace
preflight that reads the concept corpus and emits orphan/link/decay metrics.

The preflight must not execute `concept-weave.py`, `knowledge-decay.sh`, or any
other Documents script. It may read concept Markdown and the curated bridge
maps, but all evidence and metrics are written under Workspace runtime state.
Write-capable mesh, bridge, exec-bridge, and inbox generation remain explicitly
deferred until a canonical Workspace owner is implemented.

The existing LaunchAgent label and monthly calendar semantics are preserved.
Before/after plist bytes, SHA-256, `plutil -lint`, and `launchctl print` state
are recorded. The legacy script and source content remain intact for rollback.
