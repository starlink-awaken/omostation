# ADR — Phase 11 Wave 4 — Eidos Protocol Contract Surface

## Context

`eidos.protocols` already provided runtime `Protocol` interfaces, but Wave 4 still lacked an explicit serialized contract surface that other packages could validate against. That meant interface reuse was implicit at the Python object layer and weak at the payload/API boundary.

## Decision

Treat `eidos.protocols` as a dual contract surface:

1. **runtime protocols** for object-shape compatibility
2. **serialized payload contracts** for cross-package/API validation

Landed pieces:

- `eidos.protocols.contracts.CONTRACT_REGISTRY`
- `validate_contract_payload(...)`
- first pilot contracts:
  - `knowledge-card-v0.3`
  - `fact-v0.3`

The first consumer pilot is KOS ingest preflight, which now validates selected Eidos schema payloads against the shared contract definitions before continuing with local type validation.

## Consequences

1. `eidos/protocols/` now has a concrete v0.3 contract direction instead of remaining only a runtime-typing convenience layer.
2. Cross-package validation can happen without each consumer re-specifying required fields by hand.
3. The first pilot stays intentionally small (two contracts, one consumer) so later expansion can add more contracts without prematurely freezing every package boundary.
