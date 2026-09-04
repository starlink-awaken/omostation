---
title: agora_route_drift_audit
type: doc
---

# Agora Route Drift Audit

> Scope: `/Users/xiamingxing/Workspace/projects/agora`
> Perspective: impact on `kairon` topology and operator truth
> Snapshot date: 2026-06-07

## Summary

Agora has already started routing legacy LLM gateway traffic toward `aetherforge-gateway`, and the legacy persona bridge surface is now being collapsed onto a single compatibility backend name: `sot-bridge-persona`.

The problem is not just stale naming. The route table currently mixes three states:

1. live target
2. compatibility alias
3. dead or semantically under-specified target

That makes the registry a weak truth source for architecture and planning work.

## High-Signal Findings

| Route key | Current target | Status | Why it matters |
|---|---|---|---|
| `llm-gateway-kernel_default` | `aetherforge-gateway` | compatibility alias | migration is happening |
| `llm-gateway_default` | `aetherforge-gateway` | compatibility alias | legacy name points to new system |
| `llm_generate` | `llm-gateway` | stale | disagrees with the alias migration above |
| `engine-core_default` | `engine-core` | dead target | no live `engine-core` package in current `kairon` tree |
| `protocols-layer_default` | `protocols-layer` | dead target | no live package in current `kairon` tree |
| `sharedbrain-bridge_default` | `sot-bridge-persona` | compatibility bridge | legacy name now folds to one canonical backend |
| `circuit_execute` | `sot-bridge-persona` | compatibility bridge | operator-visible route now resolves to one canonical backend |
| `health_check` | `sot-bridge-persona` | compatibility bridge | same issue as above |
| `identity_verify` | `sot-bridge-persona` | compatibility bridge | same issue as above |
| `ssot_default` | `ssot` | dead target | no live `ssot` package in current `kairon` tree |
| `sot-bridge_default` | `sot-bridge` | dead target | retained as historical alias only |

## Service Registry Findings

### Clearly converging

- `aetherforge-gateway`
  - description already says it replaces `llm-gateway-kernel`
  - service registry and override YAML are aligned on this direction

### Semantically stale

- `sot-bridge-persona`
  - now acts as the single canonical legacy backend for persona bridge compatibility
  - current `kairon` tree still has no corresponding live installable package

- `sharedbrain-bridge` / `sot-bridge`
  - now treated as compatibility aliases only
  - neither corresponds to a live installable `kairon` package

## Interpretation

The current live architecture is closer to:

`agora -> aetherforge-gateway` for model/gateway traffic

and

`agora -> sot-bridge-persona` for the remaining legacy SharedBrain/SSOT compatibility surface.

So the registry is usable as a transport layer, but not yet trustworthy as a topology map.

## Priority

### P0

- Align `llm_generate` with the `aetherforge-gateway` migration path
- Remove or explicitly deprecate route keys that resolve to missing packages: `engine-core`, `protocols-layer`, `ssot`

### P1

- Re-express bridge and SSOT capabilities in terms of live sibling projects, not removed package names
- Mark compatibility aliases as compatibility aliases in generated docs

### P2

- Generate route inventory from live registrable services instead of allowing handwritten drift to accumulate
