---
title: live_inventory
type: doc
---

# Kairon Live Inventory

> Scope: the current Kairon checkout
> Snapshot date: 2026-07-27
> Method: `packages/*/pyproject.toml` live scan; package versions and membership remain authoritative in TOML, not this document

## Summary

- Truth source: package directories that currently contain `pyproject.toml` and the root workspace membership.
- This inventory intentionally omits volatile source/test counts; obtain them from the current tree and CI artifacts.
- Recent cleanup removed `kairon-lib-events`; validation-pipeline restoration added no package boundary.

## Installable Packages

| Package dir | Project name | Version | Python | Role |
|---|---|---:|---|---|
| `codeanalyze` | `codeanalyze` | 0.5.0 | `>=3.10` | code and structure analysis |
| `core-models` | `core-models` | 0.5.0 | `>=3.10` | shared base models |
| `eidos` | `eidos` | 0.5.0 | `>=3.10` | schema and contract layer |
| `forge` | `forge` | 1.3.0 | `>=3.10` | tooling and marketplace surface |
| `health-profile` | `health-profile` | 0.1.0 | `>=3.10` | health summarization helpers |
| `iris` | `iris` | 0.3.0 | `>=3.10` | research/connectors support |
| `kairon-observability` | `kairon-observability` | 0.4.0 | `>=3.10` | observability helpers |
| `kairon-pipeline` | `kairon-pipeline` | 0.4.0 | `>=3.10` | pipeline helpers |
| `kairon-plugin-sdk` | `kairon-plugin-sdk` | 0.4.0 | `>=3.10` | plugin integration surface |
| `kairon-utils` | `kairon-utils` | 0.4.0 | `>=3.10` | shared utility layer |
| `kos` | `kos` | 2.0.0 | `>=3.10` | cross-search and retrieval |
| `kronos` | `kronos` | 0.7.0 | `>=3.10` | ingest pipeline |
| `minerva` | `minerva` | 0.15.0 | `>=3.10` | deep research and knowledge pipeline |
| `ontoderive` | `ontoderive` | 3.6.4 | `>=3.10` | ontology derivation, validation, and evolution |
| `sophia` | `sophia` | 1.0.0 | `>=3.10` | symbolic research runtime |

## Workspace Drift

### Historical or missing members still referenced elsewhere

These names are still present in docs, route aliases, or workspace exclude lists, but they are **not live installable packages** in the current tree:

- `engine-core`
- `sharedbrain-bridge`
- `ssot`
- `symphony-protocol`
- `llm-gateway`
- `protocols-layer`
- `sot-bridge`

### `tool.uv.workspace.exclude` drift

`pyproject.toml` still excludes six historical members:

- `packages/sophia`
- `packages/symphony-protocol`
- `packages/ssot`
- `packages/sharedbrain-bridge`
- `packages/llm-gateway`
- `packages/engine-core`

Observed live state:

- `sophia` still exists and is installable
- the other five paths no longer exist as package directories

This means the workspace config is carrying compatibility debris from earlier topology states.

## Current Reading of the Repo

The repo is no longer a broad "all-in-one" runtime surface. It is now mostly:

1. foundational package shards: `core-models`, `kairon-*`, `health-profile`
2. knowledge engines: `eidos`, `kos`, `kronos`, `minerva`, `ontoderive`, `iris`, `sophia`, `codeanalyze`
3. one outward-facing capability surface: `forge`

OntoDerive's package boundary is unchanged. Its validation pipeline depends on the restored `meta_validate`, `meta_evolve`, and compatibility pipeline models documented in [`../packages/ontoderive/README.md`](../packages/ontoderive/README.md).

Everything else that used to represent gateway, bridge, SSOT, or operator-home responsibilities has either moved to sibling projects or survives only as route-level historical aliases.
