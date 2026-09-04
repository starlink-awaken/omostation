---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-89
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# ZCode native Documents config reconciliation

## Decision

Use the existing Workspace-owned `documents-zcode-config.py install` path to
repair only the managed Cockpit MCP entry in `~/.zcode/cli/config.json`.
Preserve all unrelated ZCode servers, provider/model settings, and the active
Documents client state; do not restart ZCode or move its SQLite state in this
bet.

## Exact scope

- Managed surface: `~/.zcode/cli/config.json`, Cockpit server entry only.
- Contract source: `.omo/_truth/registry/documents-domain-projects.yaml` plus
  `Documents/@公共/_control/L4-DOMAIN-REGISTRY.yaml`.
- Operation: preflight snapshot, atomic Workspace-owned install, check, and
  postflight preservation audit.
- The native config must remain mode `0600`; unrelated server keys must be
  structurally identical before and after.

## Acceptance criteria

1. Preflight proves current drift and records the unrelated-settings digest.
2. Install makes the existing checker return `ok` without deleting unrelated
   servers or changing model/provider settings.
3. Postflight proves mode `0600`, managed Cockpit parity, unchanged unrelated
   settings, and no Documents client-state mutation.
4. Client-state relocation remains explicitly pending while ZCode holds the
   Documents SQLite/WAL/SHM files open.

## Non-goals

No Documents state movement, SQLite/WAL/SHM change, credential/log/checkpoint
mutation, ZCode restart, provider change, server deletion, or client-profile
redesign.
