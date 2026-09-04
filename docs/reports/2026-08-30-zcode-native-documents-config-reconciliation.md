---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-89
---

# ZCode native Documents config reconciliation — implementation evidence

## Scope and commands

- Managed surface: `~/.zcode/cli/config.json`, Cockpit MCP entry only.
- Contract source: Workspace `documents-domain-projects.yaml` and the
  Documents `L4-DOMAIN-REGISTRY.yaml`.
- Commands: `documents-zcode-config render`, `check`, and `install` with
  explicit Workspace/Documents registry paths.
- Postflight observed at: `2026-08-29T21:24:42Z`.

## Preflight

- Checker result: `status=drift`; only
  `mcp.servers.cockpit does not match the Workspace contract` was reported.
- Config mode was already `0600`; 18 MCP server keys were present.
- Stable unrelated-settings digest (all config except managed Cockpit entry):
  `sha256:9b4cac87ea87b56e54f074799d1d8271758a4c1f5a3314df0c5bad07208418d1`.
- A protected rollback copy was created at
  `runtime/quarantine/zcode-config-20260830/previous-config.json` with
  SHA-256 `49440bc6e1eca659be74c785987b6569ca7ef3c120a4873851a195d839f0e3b6`.

## Transaction

`documents-zcode-config.py install` atomically replaced only the managed
Cockpit projection. The resulting command is
`/Users/xiamingxing/Workspace/projects/cockpit/.venv/bin/cockpit-mcp` with
`WORKSPACE_ROOT=/Users/xiamingxing/Workspace` and
`L4_DOCUMENTS_ROOT=/Users/xiamingxing/Documents`.

## Independent postflight

- Checker result: `status=ok`, `ok=true`; config mode remains `0600`.
- All 18 server names remain present. The unrelated-settings digest is still
  `sha256:9b4cac87ea87b56e54f074799d1d8271758a4c1f5a3314df0c5bad07208418d1`.
- Documents client state was not changed: `tasks-index.sqlite`, its WAL, and
  SHM retain their preflight hashes and remain open by the running ZCode
  process. No restart was performed.

## Boundary

This repairs the Workspace-owned ZCode configuration projection only. It does
not migrate `Documents/ZCode/.zcode` state; that remains pending until ZCode is
quiesced and the complete state set (database sidecars, config, credentials,
logs, checkpoints, and certificates) has an accepted migration plan.
