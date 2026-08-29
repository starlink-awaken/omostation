---
schema_version: specification/v1
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-62
spec_version: 1.0.0
title: OMO ingress write-boundary and schema gate recovery
---

# T10-62: OMO ingress write-boundary and schema gate recovery

## Context

The root governance interface is blocked by an OMO child revision that still
reports 17 direct sensitive writes in
`omo_ingress_task_execution.py` and six dead imports in `omo_audit.py`. The
write calls are the existing broker-owned task execution lifecycle, but the
P110 extraction introduced a new module name that was not added to the
existing authorized ingress exemption set. The dead-import repair already
exists on child `origin/main` as `18bc886`, while the root gitlink still points
to `d01675a`.

## Decision

1. Add `omo_ingress_task_execution.py` to the existing
   `_SENSITIVE_WRITE_EXEMPT_FILES` ingress-broker allowlist, with a regression
   test that proves the real module is exempt while synthetic direct writes
   remain rejected.
2. Advance the root `projects/omo` gitlink to the child commit containing the
   exemption and the existing dead-import repair.

The sensitive-write detector, schema detector, runtime behavior, and broker
authority remain unchanged.

## Non-goals

- No change to task execution behavior, receipt shape, broker routing, or
  schema semantics.
- No weakening of synthetic negative tests or deletion of a governance gate.
- No Documents content, host schedule, runtime state, capability, or
  dispatcher change.
- No root pointer update for any child other than `projects/omo`.

## Acceptance

1. OMO's direct-sensitive-write and schema lint commands pass on the child
   revision.
2. The child regression suite proves the authorized ingress boundary and
   keeps a synthetic direct write rejected.
3. The root gitlink points to the verified child commit and the clean CI
   governance interface no longer fails on these OMO findings.
4. No functional OMO behavior changes beyond the static allowlist and the
   already-reviewed dead-import removal.

## Rollback

Revert the child OMO commit and restore the root `projects/omo` gitlink to its
previous revision. No runtime or host rollback is needed.
