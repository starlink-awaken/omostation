---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 9 program plan

> Status: completed
>
> Theme: turn the workspace plane model into governed operating contracts

## Objective

Phase 9 upgrades the workspace from “clear physical roots exist” to “spaces, identity, rollout, and operations can be governed across those roots without falling back into `.omo`-centric sprawl.”

## Wave structure

### G9.1 / Wave 1 — first migration slice

Goal: create the missing roots and prove the first safe migration can happen physically.

Status:

1. completed as the baseline slice
2. summary: `.omo/summaries/phase9-first-migration-baseline.md`

Packet:

- `P9-W1-FIRST-MIGRATION-SLICE`

### G9.2 / Wave 2 — space registry and ownership manifests

Goal: turn `spaces/` from a placeholder root into a governed workspace boundary.

Status:

1. completed as the first governed space boundary baseline
2. summary: `.omo/summaries/phase9-wave2-closeout.md`

Scope:

1. define a space-manifest contract
2. create a registry of known spaces
3. seed the first workspace/system spaces
4. attach ownership and routing refs from spaces to projects/data/runtime

Packet:

- `P9-W2-SPACE-REGISTRY-FOUNDATION`

### G9.3 / Wave 3 — identity, authorization, and admission contracts

Goal: define who may operate across `.omo`, `projects/*`, `spaces/`, `data/`, and `runtime/`.

Status:

1. completed as the current identity / authorization / admission baseline
2. default anchor: actor + space membership
3. packet: `P9-W3-IDENTITY-ADMISSION-CONTRACT`
4. summary: `.omo/summaries/phase9-wave3-closeout.md`

Packet:

- `.omo/plans/phase9-wave3-execution-plan.md`

Scope:

1. workspace identity model
2. role/capability mapping
3. authorization rules for cross-root actions
4. admission contract for routed work

### G9.4 / Wave 4 — rollout, operations, and closeout governance

Goal: make the new workspace structure operable and promotable.

Status:

1. completed as the rollout / operations / closeout baseline
2. summary: `.omo/summaries/phase9-wave4-closeout.md`
3. retrospective: `.omo/summaries/phase9-closeout-retrospective.md`

Packet:

- `.omo/plans/phase9-wave4-execution-plan.md`

Scope:

1. rollout policy and promotion checks
2. runtime/ops boundary checks
3. first acceptance path using the new roots
4. Phase 9 closeout and review

## Sequencing rule

1. Wave 4 was the only execution-ready packet after Wave 3 closeout
2. Wave 3 used the Wave 2 registry/manifest baseline as its entry gate
3. Wave 4 stayed gated until Wave 3 landed identity/admission contracts
4. active queue never contains more than one execution-ready Phase 9 packet

## Success metrics

1. `spaces/` contains at least one valid registry and one valid system space manifest
2. cross-root ownership language is explicit instead of implied
3. identity/admission policy exists before any broad rollout work starts
4. rollout and operations rules can reference `spaces/`, `data/`, and `runtime/` without `.omo` swallowing them
5. one real rollout path can be accepted without violating runtime ownership boundaries

## Verification baseline

1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 -m pytest .omo/tests -q`
3. wave-specific tests and evidence listed in each execution packet
