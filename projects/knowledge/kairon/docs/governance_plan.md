---
title: governance_plan
type: doc
---

# Kairon Remediation Roadmap

> Based on `docs/architecture_audit.md`
> Status: draft execution route
> Date: 2026-06-04

This is no longer a phase-fiction document. It is a repair plan tied to the live repo.

## P0: Restore Trustworthiness

### 1. Rebuild inventory and fix repo-facing docs

- **Problem**: repo docs and `.omo` inventory still claim 26/31 packages and stale sibling projects
- **Impact**: every architecture discussion starts from false topology
- **Preconditions**: none
- **Verification**:
  - live package count script returns 25
  - `README.md`, `AGENTS.md`, `docs/architecture_audit.md` agree on the same package count and project boundaries
- **Cross-project coordination**: yes, `.omo` inventory sync required after repo docs are corrected

### 2. Clean the `packages/` workspace boundary

- **Problem**: `agora.db`, `agora-audit.db`, `kairon-10pkg-analysis.md` sit inside `packages/`
- **Impact**: UV workspace warnings, poor isolation between source and residue
- **Preconditions**: choose canonical runtime/artifact locations under `data/` or `runtime/`
- **Verification**:
  - `make test-fast` no longer emits "Ignoring non-directory workspace member"
- **Cross-project coordination**: no

### 3. Repair `agora` control-surface contracts

- **Problem**:
  - known service list missing `kronos`
  - semantic router silently degrades to empty hits when embeddings backend is absent
  - event payload shape mismatches test expectations
- **Impact**: core registry, routing, and pipeline event contracts are not trustworthy
- **Preconditions**: none
- **Verification**:
  - failing `agora` tests reproduced and fixed
  - degraded mode returns explicit status instead of silent empty behavior
  - event payload schema is documented and tested
- **Cross-project coordination**: yes, touches MCP and runtime expectations

### 4. Align `agent-runtime` dependency contract

- **Problem**: smoke test fails because runtime code imports `fastapi` without the workspace test environment satisfying that dependency
- **Impact**: package health is overstated; fast smoke run is not a reliable gate
- **Preconditions**: decide whether `fastapi` is required dependency, optional extra, or test-only fixture assumption
- **Verification**:
  - `agent-runtime` tests pass under documented workspace install path
- **Cross-project coordination**: no

### 5. Reconcile migration claims from `agentmesh`

- **Problem**: archived `agentmesh` claims migration to `packages/agent-hub/`, but the target package is absent
- **Impact**: architecture narrative about runtime migration is incomplete
- **Preconditions**: inspect history or prior archive notes
- **Verification**:
  - migration table matches live package tree
  - no docs point to missing package targets
- **Status**: ✅ **已解决 (2026-06-09)** — agentmesh 迁移对照表已更新为当前实际位置 (agora→`projects/agora/`, agent-runtime→`projects/runtime/`+`projects/cockpit/`, llm-gateway→`projects/aetherforge/`, agent-hub 标注为未落地)
- **Cross-project coordination**: yes, archive docs and `.omo` references

## P1: Clarify Architecture

### 6. Choose and document the operator home

- **Problem**: `wksp`, `agora`, `kos`, and package-local CLIs all compete as entry surfaces
- **Impact**: user path and ops path are fragmented
- **Preconditions**: P0 inventory truth and `agora` contract repair
- **Verification**:
  - one documented primary operator path
  - other CLIs described as domain-specific or compatibility surfaces
- **Cross-project coordination**: yes, affects `.omo` capability descriptions

### 7. Re-scope `sharedbrain-bridge`

- **Problem**: bridge name and docs point to a sibling project boundary that is no longer live in `projects/`
- **Impact**: external integration semantics are muddy
- **Preconditions**: confirm whether SharedBrain is external runtime/data only
- **Verification**:
  - package README defines current upstream/downstream contract
  - no docs imply a nonexistent sibling repo
- **Cross-project coordination**: yes

### 8. Decide whether `llm-gateway` is a real convergence layer

- **Problem**: the package exists but does not yet prove architectural unification
- **Impact**: LLM abstraction cleanup risks becoming another thin wrapper instead of a true shared contract
- **Preconditions**: dependency and surface review across `minerva`, `ontoderive`, `ssot`, `agora`
- **Verification**:
  - explicit ownership matrix for provider abstraction
  - removal or deprecation plan for duplicate contracts
- **Cross-project coordination**: limited

### 9. Raise baseline tests for high-leverage packages

- **Packages**: `agora`, `wksp`, `sharedbrain-bridge`, `agent-runtime`
- **Why**: these packages define entry surfaces or system seams, so low-confidence tests create system-level blind spots
- **Verification**:
  - sample package tests cover at least one passing and one degraded-mode path each

## P2: Structural Cleanup

### 10. Rework package taxonomy

- distinguish foundation, runtime, knowledge, connector, and product surfaces clearly
- remove naming that overstates scope or hides actual ownership

### 11. Reconcile git history, archives, and live checkout

- absent-from-tree packages referenced by recent history need explicit disposition:
  - `agent-hub`
  - `eu-pricing`
  - `gc-engine`
  - `observability`
  - `pontus`
  - `sharedbrain-standalone`

### 12. Sync `.omo` after repo truth is stable

- update inventory, capability maps, and standards only after P0-P1 repo fixes land

## Validation Matrix

| Problem | Validation |
|---|---|
| inventory drift | package scan output and docs agree |
| workspace pollution | no UV workspace warnings |
| `agora` regressions | targeted tests pass for registry, routing, event payload |
| `agent-runtime` dependency mismatch | package tests pass from documented workspace setup |
| migration drift | archive/readme references match live tree |
| operator-home ambiguity | one primary entrypoint documented and linked |

