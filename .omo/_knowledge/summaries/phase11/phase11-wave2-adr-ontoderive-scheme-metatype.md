---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# ADR — Phase 11 Wave 2 — OntoDerive Scheme MetaType

> Historical ADR reference. It records the decision made in that wave; current runtime status and current implementation ownership must be verified from the codebase and current SSOT surfaces.

## Context

`ontoderive.engine.foundation.models.Scheme` had no explicit `meta_type`, even though scheme artifacts function as document-like planning/specification objects.

## Decision

Add an additive field:

- `Scheme.meta_type: str = "document"`

Normalize any incoming variant casing to the lowercase local SSOT-compatible value.

## Consequences

1. Scheme objects now participate in the same model-type contract surface as other knowledge artifacts.
2. Existing scheme fields and file-path behavior stay unchanged.
3. Wave 2 gains a safe bridge toward later OntoDerive/Eidos contract unification without broad refactors.
