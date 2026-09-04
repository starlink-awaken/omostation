---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-38
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Workspace watcher owner design

Move the minute-level Documents `watch-dispatch.py` execution boundary into
Workspace. Preserve its four watch groups and change only the action owners:

- domain manifest changes call the existing read-only domain-index owner;
- Workspace state changes call bridge preflight;
- inbox changes call the canonical Workspace brief generator;
- weekly verdict changes produce a pending/observed receipt until a Workspace
  verdict owner exists, rather than writing Documents.

The watcher may read Documents content and write Workspace stamps/evidence, but
must never import or execute a Documents script. It is a relocated implementation
of the existing watcher, not a second dispatcher or control plane. The old file
remains for rollback and content/archive evidence.

Acceptance requires deterministic watch classification, no subprocess command
path under Documents, Workspace-only stamps, and an exact crontab rollback proof.
