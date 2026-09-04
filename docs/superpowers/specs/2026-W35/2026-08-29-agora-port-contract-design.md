---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-51
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Canonical Agora MCP port contract

## Objective

Make the registered `mcp.agora` Service Gateway command honor its SSOT port
(`7433`) while preserving Agora's standalone default SSE port (`7431`) and
the existing service registry semantics.

## Contract

- `mcp.agora` declares `AGORA_MCP_SSE_PORT=7433` through the existing service
  `environment` field.
- Service Gateway merges declared environment values over the inherited process
  environment only for the launched child process.
- Dry-run output remains deterministic and exposes the canonical argv; secrets
  are not printed or persisted.
- No default port change, old daemon activation, plist mutation, or second
  service registry is allowed.

## Acceptance

- Regression tests prove environment inheritance/override and the mcp.agora
  7433 declaration.
- The generated command and launch environment are consistent with the SSOT.
- Focused tests, syntax, and GaC pass; no host process or plist is changed.
