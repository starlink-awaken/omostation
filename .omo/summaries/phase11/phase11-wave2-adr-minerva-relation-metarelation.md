# ADR — Phase 11 Wave 2 — Minerva Relation MetaRelationType

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
