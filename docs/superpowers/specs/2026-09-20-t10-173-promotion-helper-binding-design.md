---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: OMO promotion helper standalone binding repair
bet_id: BET-Y1Q4-T10-173
created: '2026-09-20'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# OMO promotion helper standalone binding repair

## Problem

`omo.omo_ingress_task_promotion` calls `_record_trail` and `_record_mutation`
as module globals. Those names are rebound only when `omo.omo_ingress` has
already loaded. Importing the promotion submodule standalone therefore fails
with `NameError` once a promoted task reaches its audit trail.

This reproduces at both OMO pins:

- `022ba3001219e1c7684643e977e46c15b1af54de`
- `20449f40877d302bd40e430a1e371e8020d93997`

## Change

Add two module-level lazy wrappers using the established pattern in
`omo_ingress_registry_writes.py`. Each wrapper imports the canonical function
from `omo.omo_ingress` at call time. This preserves the existing ingress
rebinding behavior while making standalone imports safe.

## Base and verification

- Base: `d7feb927f97f9aca7871a6965e8211ba99c18437`
- Patch: `promotion-helper-binding.patch`
- Patch SHA-256: `07c4941bd7ee0f6a87c7ec576350eb28a8556de3f41291a2d4b04f0f92aaf8fd`
- Formerly failing standalone test: `1 passed`
- Broader `tests/test_workflow_*.py`: `320 passed`

## Acceptance

The standalone failing test must pass. The full workflow regression must be
green. No audit trail, mutation record, ingress registry format, runtime state,
or external effect semantics may change.

## Rollback

Revert the single promotion source patch. It has no data migration or runtime
configuration effect.

## Non-goals

This does not authorize a root gitlink bump, Claims lifecycle execution,
business-value evidence, external admission expansion, or runtime restart.
