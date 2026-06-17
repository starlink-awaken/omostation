# ADR — Phase 11 Wave 2 — OntoDerive Inference MetaType

> Historical ADR reference. It records the decision made in that wave; current runtime status and current implementation ownership must be verified from the codebase and current SSOT surfaces.

## Context

`ontoderive.engine.foundation.models.Inference` carried no explicit `meta_type`, while Eidos already defines the canonical lowercase `MetaType` contract.

## Decision

Add an additive field:

- `Inference.meta_type: str = "inference"`

Normalize it through the local lowercase type normalizer instead of adding a new package dependency on `eidos.meta`.

## Consequences

1. OntoDerive inference objects now expose the same semantic type family as the Eidos SSOT.
2. Existing callers remain compatible because no old field was removed or renamed.
3. A future deeper taxonomy collapse can still happen later without blocking Wave 2.
