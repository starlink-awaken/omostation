---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# ADR — Phase 11 Wave 2 — Minerva Relation MetaRelationType

> Historical ADR reference. It records the decision made in that wave; current runtime status and current implementation ownership must be verified from the codebase and current SSOT surfaces.

## Context

`minerva.knowledge.store.Relation` normalized `predicate`, but exposed no explicit `meta_relation` contract aligned with the canonical Eidos relation taxonomy.

## Decision

Add an additive field:

- `Relation.meta_relation: str = "struct"`

Normalize it with the existing local relation normalizer while preserving `predicate` as the operational field used by the current store.

## Consequences

1. Minerva relation objects now carry a canonical relation-type contract without breaking current persistence behavior.
2. Existing graph/store code can migrate incrementally because `predicate` remains intact.
3. Future adapter-level propagation can be added later without reopening the Wave 2 data-model change.
