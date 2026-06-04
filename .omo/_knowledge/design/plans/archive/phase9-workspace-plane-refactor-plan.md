# Phase 9 workspace plane refactor plan

> Status: active
> Scope: workspace architecture refactor + first migration slice
> Date: 2026-05-31

---

## 1. Goal

Make the workspace structure match the actual operating model:

1. `.omo` owns governance, control, control-truth, and delivery governance
2. `projects/*` own capability code, domain decision logic, and execution runtimes
3. `spaces/` owns user-space and tenant-space manifests
4. `data/` owns the shared data substrate contract
5. `runtime/` owns ephemeral runtime residue and generated local state

Phase 9 is therefore a **boundary refactor phase**, not another feature-accumulation phase.

---

## 2. Why now

By the end of Phase 8, the repo has a functioning OMO control plane, but the workspace still lacks a stable physical contract for:

1. user and tenant spaces
2. shared data ownership
3. runtime residue
4. cross-root responsibility boundaries

Without this refactor, future identity, authorization, rollout, and user-space work would keep landing into ambiguous homes.

---

## 3. Canonical plane model

| Plane | Physical home | Owner |
|------|---------------|-------|
| Governance | `.omo/` | OMO |
| Control | `.omo/` | OMO |
| Control truth | `.omo/goals`, `.omo/state`, `.omo/tasks` | OMO |
| Capability | `projects/*` | Project owners |
| Domain decision | `projects/*` | Project owners |
| Domain data / user space | `spaces/`, `data/`, project data stores | Project + workspace |
| Delivery governance | `.omo/` | OMO |
| Runtime residue | `runtime/` | Workspace runtime contract |

---

## 4. First migration slice

This phase does **not** attempt a full workspace reshuffle.

It does:

1. create the missing roots
2. formalize their contracts
3. move the first safe responsibility classes into those roots
4. update registry/index/test expectations to recognize the new layout

Initial migration targets:

1. space and tenant manifests -> `spaces/`
2. shared data substrate contract docs -> `data/`
3. runtime residue contract -> `runtime/`

---

## 5. Non-goals

Phase 9 does not:

1. move project code out of `projects/*`
2. turn `.omo` into a data lake
3. perform large-volume user data migration
4. redesign every project internals in one phase

---

## 6. Execution workstreams

### W1. Plane model ratification

1. update `.omo/PROJECTS.yaml`
2. update root `AGENTS.md`
3. register the Phase 9 plan in `.omo/INDEX.md`, `_knowledge/design/INDEX.md`, and `plans/README.md`

### W2. Root structure creation

1. create `spaces/`
2. formalize `data/`
3. create `runtime/`

### W3. Contract normalization

1. document what belongs where
2. document what must not be written into `.omo`
3. document what must remain project-local

### W4. Runtime boundary alignment

1. update OMO-facing docs/tests/scripts so they treat `spaces/`, `data/`, and `runtime/` as explicit homes
2. keep `.omo` limited to control-governance truth

### W5. Validation and closeout

1. add structure/docs tests
2. re-run `.omo` regression
3. publish migration baseline summary

---

## 7. Success criteria

Phase 9 first slice is successful when:

1. every workspace-level responsibility has an explicit home
2. `.omo` no longer reads as the place for all workspace content
3. `projects/*` remain clean capability owners
4. user-space, shared-data, and runtime residue contracts have first-class roots
5. tests enforce the new structure
