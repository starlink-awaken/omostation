---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# SharedBrain Phase 11 decision

> Scope: `projects/SharedBrain/`
> Phase 11 task: T2.4
> Decision posture: long-term optimal
> This is a historical decision record. It preserves the decision rationale and retained-core policy at that time, but it is not the live source for current project topology, active migration scope, or present-day governance status.

## Executive decision

SharedBrain should follow **selective extraction + layered contraction**, not whole-repo retention and not immediate full rewrite.

This means:

1. keep the highest-value runtime and governance surfaces as the long-term retained core
2. keep compatibility seams only where they protect existing contracts or migration safety
3. actively downgrade historical demos, thin stubs, and duplicated compatibility topology to archive/reference status
4. treat future rewrites as **targeted replacements behind stable contracts**, not as a repo-reset event

## Why this is the long-term optimum

### Why not retain everything

Whole-repo retention would preserve today’s useful runtime knowledge, but it would also preserve:

- alias / compatibility topology drift
- historical demo and milestone residue
- mixed documentation truth surfaces
- large low-signal maintenance area that does not justify equal investment

That would slow every future testing, refactoring, and architecture-governance wave.

### Why not full rewrite now

An immediate rewrite would produce the cleanest conceptual story, but it would discard too much embedded value:

- existing domain/runtime semantics
- already-proven tests and operational commands
- governance patterns already codified in docs and contracts
- high-signal organ domains with real code mass and meaningful test coverage

It would maximize theoretical cleanliness while maximizing delivery risk.

### Why selective extraction wins

Wave 1 inventory shows a clear center of gravity:

- `D_Execution`
- `D_Gateway`
- `D_Governance`
- `D_Memory`
- `D_Harvest`
- `Z-Microkernel`
- `Z-Spore`

These are the surfaces most worth preserving, testing, and simplifying. The right move is therefore to **narrow the supported architecture around the proven core**, while steadily removing or demoting low-value residue.

## Four-layer classification

### 1. Retained core

These areas should be treated as the strategic long-term SharedBrain substrate:

- `nucleus/Z-Microkernel/`
- `nucleus/Z-Spore/`
- `nucleus/Z-Core/` within existing law/intent boundaries
- `organs/D_Execution/`
- `organs/D_Gateway/`
- `organs/D_Governance/`
- `organs/D_Memory/`
- `organs/D_Harvest/`
- contract-bearing tests and docs that define these surfaces

Rules:

1. new tests should prioritize these domains first
2. architectural cleanup should prefer contract-preserving internal simplification
3. path/configuration hardening and model unification should land here before anywhere else

### 2. Compatibility layer

These areas may remain temporarily, but only as migration or interoperability seams:

- alias directory forms (`D-*`, `D_*`, `Z_*`, `Z-*`) where compatibility is still needed
- CLI/process wrappers that should eventually route through stable protocol/service contracts
- transitional import bridges and compatibility docs

Rules:

1. no new product ownership should accumulate here
2. compatibility surfaces must be explicitly marked and regression-tested
3. every new change should reduce, not expand, the compatibility footprint

### 3. Archive / reference layer

These areas should be preserved mainly for auditability, historical reference, or demos:

- superseded milestone/demo material
- historical cleanup archives already under `docs/archive/`
- legacy examples that are useful as reference but not part of the live supported runtime

Rules:

1. do not route new runtime ownership here
2. keep links/documentation accurate, but minimize active maintenance
3. only retain what still provides governance, migration, or product-reference value

### 4. Rewrite-later candidates

These are areas where long-term cleanup should happen by replacement behind stable boundaries rather than incremental patching:

- thin or stub domains with low code/test value (for example `D_Window`)
- duplicated/overlapping capability seams where one stable contract should replace many local variants
- legacy CLI-first adapters that should become service-contract-first adapters

Rules:

1. do not rewrite them speculatively
2. first define the contract that survives the rewrite
3. then swap implementation behind that contract with focused tests guarding behavior

## Immediate Wave 2 implications

### T2.5 — SharedBrain tests

SharedBrain test investment should target the **retained core first**. The first Wave 2 test slice should therefore cover a retained-core module, not a historical or demo-only surface.

### T2.6 — eidos interactive CLI

If eidos is promoted, it should be treated as a retained user-facing contract. The CLI flag should be added as a stable command surface, not as an ad-hoc one-off script behavior.

### T2.7 — KOS ruff reduction

Lint reduction should prioritize modules that are either:

1. retained-core dependencies, or
2. on the path to becoming retained-core contracts

The goal is not cosmetic repo-wide cleanup; the goal is reduced maintenance drag on the strategic core.

### T2.8 — hardcoded paths

Absolute-path removal is a retained-core governance requirement. Path handling should converge on shared configuration / BOS-aware boundaries, not file-local ad-hoc fixes.

### T2.9-T2.11 — model unification

Model unification is consistent with this decision only if the unified types become the contract layer for the retained core, with adapters absorbing old local shapes until callers migrate.

## Recommended operating policy after this decision

1. **Preserve and strengthen the core**: keep the core runtime/governance surfaces healthy, tested, and contract-first.
2. **Shrink compatibility deliberately**: compatibility is temporary and should have an explicit burn-down path.
3. **Archive aggressively but safely**: historical value stays discoverable without pretending it is live runtime ownership.
4. **Rewrite only behind contracts**: never reset the whole repo when a bounded seam can be replaced safely.

## Exit judgment

**Recommendation adopted:** SharedBrain is neither a full-keep repo nor a rewrite-from-zero repo. It is a **core-preservation, boundary-tightening, residue-reduction program**.
