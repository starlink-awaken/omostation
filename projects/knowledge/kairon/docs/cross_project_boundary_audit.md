---
title: cross_project_boundary_audit
type: doc
---

# Kairon Cross-Project Boundary Audit

> Scope: `kairon` as the center, covering `agora`, `aetherforge`, `agentmesh`, `SharedBrain`, and workspace governance docs
> Audit date: 2026-06-07

## 1. `kairon <-> agora`

### Live evidence

- Agora route table still exposes historical names such as `engine-core`, `sharedbrain-bridge`, `protocols-layer`, `ssot`, and `sot-bridge`
- current compatibility routing now collapses the bridge side onto one backend name: `sot-bridge-persona`
- current `kairon` tree has no live installable packages for those names
- route aliases for `llm-gateway` already point toward `aetherforge-gateway`, but `llm_generate` still points at `llm-gateway`

### Finding

Agora is carrying both live convergence and a partially normalized compatibility topology at the same time.

### Risk

**P0**: users and planners can infer a false service topology from the registry.

## 2. `kairon <-> aetherforge`

### Live evidence

- `projects/aetherforge/` now exists as a first-class repo
- service registry describes `aetherforge-gateway` as the replacement for `llm-gateway-kernel`
- `projects/runtime/pyproject.toml` now depends on `aetherforge-gateway`

### Finding

LLM gateway responsibilities are no longer meaningfully inside `kairon`. They are converging into a sibling project.

### Risk

**P0** if docs keep treating `llm-gateway` as a live `kairon` capability surface.

## 3. `kairon <-> agentmesh`

### Live evidence

- archived `agentmesh` documentation still claims 100% migration into `kairon`
- the current `kairon` tree no longer contains several historical migration targets that older narratives depend on

### Finding

The migration story is historical, not current topology truth. It should not be used as an architecture source without revalidation. **2026-06-09**: migration map in `_archived/agentmesh-shell-2026-06-05/README.md` has been updated to reflect current project locations.

### Risk

~~**P1**: migration docs overstate how much of the old mesh/runtime surface still lives inside `kairon`.~~ **已解决** — 迁移文档已更新。

## 4. `kairon <-> SharedBrain`

### Live evidence

- current workspace no longer contains a live `SharedBrain` repo under `projects/`
- route and service narratives still use `sharedbrain-bridge` and `sot-bridge` names
- current `kairon` tree has no live `sharedbrain-bridge` package

### Finding

SharedBrain is now a conceptual or data boundary, not a live sibling package boundary inside `kairon`. 原始代码归档于 `projects/_archived/SharedBrain-original/` 和 `projects/_archived/SharedBrain-code/`。

### Risk

**P1**: stale bridge language makes the system look more integrated than it is.

## 5. `kairon <-> workspace governance docs`

### Live evidence

- workspace [AGENTS.md](../../../AGENTS.md) previously carried the same stale package-count drift and needed a truth reset
- repo [AGENTS.md](../../AGENTS.md) still said 25 before this audit refresh
- earlier audit docs still reason from deleted package names

### Finding

Governance and onboarding docs were using stale topology as if it were live fact.

### Risk

**P0**: bad planning input, bad routing assumptions, and false confidence in repo capabilities.

## 6. Boundary Summary

| Seam | Status | Main issue |
|---|---|---|
| `kairon <-> agora` | unstable | route aliases outlive live package topology |
| `kairon <-> aetherforge` | converging | gateway truth moved faster than docs |
| `kairon <-> agentmesh` | historical only | migration map is no longer a live architecture source |
| `kairon <-> SharedBrain` | under-specified | bridge naming survives after package boundary disappeared |
| `kairon <-> workspace governance docs` | stale | package counts and capability map drifted |

## 7. Required Actions

### P0

- refresh all package-count claims to 16 live installable packages
- stop treating deleted package names as live architecture anchors
- align Agora LLM routes with `aetherforge-gateway`

### P1

- rewrite SharedBrain and SSOT language around current sibling-project boundaries
- tag compatibility aliases as compatibility aliases in route docs

### P2

- generate boundary inventories from live repos and registries instead of hand-maintained prose
