---
status: accepted
date: 2026-07-14
id: 0182
title: CI / evidence / BOS registry landing after tech-debt stack
---

# ADR-0182 — CI · evidence · BOS registry 常态化落地

## Context

After #347–#350 (bin rationalize, evidence inline/mcp_proxy, 7430, debt-audit,
opc_p6 direct-io), main tip was green but **mechanically fragile**:

1. `gac-gate` push used path filters → non-governance merges left tip without re-run.
2. `evidence-smoke-gate` only fired on agora BOS path changes.
3. `.omo/_knowledge/bos-registry.json` (36 URIs) drifted from live `bos-services.yaml`.
4. `mcp_tool` / `tools` existed in YAML but not on `BosService` (evidence used description fallback).
5. ToolBox wps known-gap was due for re-audit (2026-07-25).

## Decision

1. **gac-gate**: always on `push` to `main` + all PRs (+ workflow_dispatch).
2. **evidence-smoke-gate**: always on `push` to `main` + all PRs; add
   `bin/ssot/sync-bos-registry.py --check` before score gate.
3. **bos-registry.json**: SSOT-derived mirror of classic 5-domain services from
   `bos-services.yaml` (active + unimplemented) via `bin/ssot/sync-bos-registry.py`.
4. **BosService**: project `mcp_tool` and `tools` fields; evidence-smoke prefers them.
5. **KNOWN_GAP wps-***: re-audit 2026-07-14, extend expiry to **2026-08-25**
   (external ToolBox still unbuilt; not in-repo fix).

## Consequences

- Main tip always re-validates GaC + evidence after merge.
- Smoke/integration tests must accept growing registry size (`>=` assertions).
- ToolBox wps still external; if not built by 2026-08-25, promote to real gap or deprecate BOS entries.

## Non-goals (deferred)

- Container executor hard isolation (Phase 5 roadmap, not this PR).
- OS ACL on `.omo` write plane (design only in Scheme C Phase 5).
