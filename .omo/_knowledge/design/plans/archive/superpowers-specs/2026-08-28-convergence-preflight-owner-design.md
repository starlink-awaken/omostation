---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-32
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Convergence preflight owner design

## Contract

Replace the Monday 06:30 Documents `check-convergence.py` writer with a
Workspace-owned, read-only owner invoked through the existing
`documents-domain-owner-job.py` entrypoint. The owner emits
`documents.convergence-preflight.v1` and preserves truthful exit semantics:

- `0`: all checks pass;
- `1`: checks ran and findings exist;
- `2`: the owner could not run safely or its required inputs are unavailable.

The implementation must not import or execute the legacy Documents script. It
may read the Documents content root and the Workspace domain registry, but all
report, history, and evidence writes must stay under the Workspace runtime
state root supplied by the caller.

## Preserved semantics

The preflight covers the legacy convergence audit's ten declared concerns:
required gateway/control documents, domain/index presence, registry and
gateway references, layer/M1 alignment, broken references, and entity-format
consistency. It reports structured findings rather than mutating Documents.

The old script remains in place during observation and is the rollback/parity
reference. The schedule cutover may replace only the Monday 06:30 line after an
accepted release is deployed and a dry-run proves the evidence path is outside
Documents.

## Acceptance

The owner test suite proves: no Documents writes, deterministic exit mapping,
missing-root fail-closed behavior, Workspace evidence placement, and stable
schema output. Cutover evidence records before/after crontab hashes, exact
old/new counts, unrelated-line byte identity, and a post-cutover smoke.
