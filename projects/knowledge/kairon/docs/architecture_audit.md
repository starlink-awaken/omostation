---
title: architecture_audit
type: doc
---

# Kairon Architecture Audit v3

> Scope: `/Users/xiamingxing/Workspace/projects/kairon`
> Audit date: 2026-06-07
> Method: live directory scan, `pyproject.toml` parsing, route/service registry cross-check

## Executive Summary

`kairon` has changed shape again.

The current repo is no longer the 25-package monorepo described in earlier audit documents, and it is not the 19-package state still described by workspace-level guidance either. The live truth on 2026-06-07 is:

- **16 live installable packages** in `projects/kairon/packages/*/pyproject.toml`
- gateway responsibilities are converging into **`projects/aetherforge`**
- several historical package names still survive only as **Agora route aliases**

The main architecture risk is no longer missing features. It is **topology drift between live code, route registry, and documentation**.

## 1. Live Repo Shape

### 1.1 Installable package count

Live scan result: **16**

See [live_inventory.md](./live_inventory.md) for the full table.

### 1.2 What `kairon` actually contains now

The current repo clusters into three bands:

| Band | Packages |
|---|---|
| Foundations | `core-models`, `health-profile`, `kairon-lib-events`, `kairon-observability`, `kairon-pipeline`, `kairon-plugin-sdk`, `kairon-utils` |
| Knowledge engines | `codeanalyze`, `eidos`, `iris`, `kos`, `kronos`, `minerva`, `ontoderive`, `sophia` |
| Outward-facing capability | `forge` |

That is a narrower and cleaner role than older docs claim. `kairon` is now mostly a knowledge-engine repo, not a complete runtime and bridge stack.

## 2. What Left the Repo

These names are still heavily referenced in docs and route registries, but they are not live installable packages in the current tree:

- `engine-core`
- `sharedbrain-bridge`
- `ssot`
- `symphony-protocol`
- `llm-gateway`
- `protocols-layer`
- `sot-bridge`

This matters because older architecture narratives still treat them as if they were current repo members.

## 3. Cross-Project Convergence

### 3.1 LLM gateway convergence

`llm-gateway` is effectively being replaced by `aetherforge-gateway`.

Evidence:

- `projects/aetherforge/` now exists as a dedicated repo
- `projects/runtime/pyproject.toml` depends on `aetherforge-gateway`
- Agora registry already points `llm-gateway-kernel_default` and `llm-gateway_default` to `aetherforge-gateway`

### 3.2 Operator and control-plane split

The repo-level responsibilities are now distributed more clearly:

- `cockpit`: user/operator entry
- `agora`: routing and registry
- `kairon`: knowledge engines and supporting primitives
- `metaos`: orchestration logic
- `runtime`: execution substrate
- `ecos`: L0 model and workflow truth

That is healthier than the previous "everything half-lives in kairon" state, but the docs have not caught up.

## 4. Route-Level Drift

Agora still exposes historical aliases that imply capabilities no longer backed by live `kairon` packages.

See [agora_route_drift_audit.md](./agora_route_drift_audit.md).

Most important examples:

- `llm_generate -> llm-gateway` is stale against the ongoing `aetherforge-gateway` migration
- `sharedbrain-bridge`, `engine-core`, `protocols-layer`, `ssot`, and `sot-bridge` still appear as route targets despite not being live `kairon` packages

## 5. Documentation Drift

The current drift is structural, not cosmetic:

- workspace [AGENTS.md](../../../AGENTS.md) previously described `kairon` as a 19-package repo and needed the same truth reset
- repo [AGENTS.md](../../AGENTS.md) still says `kairon` has 25 packages
- earlier audit docs still analyze `sharedbrain-bridge`, `ssot`, `llm-gateway`, and `engine-core` as live repo members

When those docs are used as planning input, the planning process starts from a false topology.

## 6. Risk Grading

### P0

- package inventory truth is stale in root and repo docs
- route registry still points some operator-visible capability names at missing packages
- `llm_generate` route is inconsistent with the `aetherforge-gateway` migration

### P1

- workspace config still carries compatibility debris in `tool.uv.workspace.exclude`
- legacy SharedBrain/SSOT narratives still exist in multiple places

### P2

- current docs do not yet distinguish clearly between live targets and compatibility aliases

## 7. Recommended Direction

1. treat `projects/kairon/packages/*/pyproject.toml` as the only installable-package truth source
2. treat Agora aliases as transport compatibility, not architecture truth
3. continue moving gateway responsibilities toward `aetherforge`
4. rewrite bridge and SSOT narratives around live sibling projects, not deleted package names

## 8. Related Docs

- [live_inventory.md](./live_inventory.md)
- [agora_route_drift_audit.md](./agora_route_drift_audit.md)
- [cross_project_boundary_audit.md](./cross_project_boundary_audit.md)
