---
type: ssot
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-25
last_updated: 2026-09-25
bet_id: BET-Y2Q3-T10-OMLXC-02
spec_version: 1.0.0
schema_version: specification/v1
---

# OMLXC Placement Runtime Recovery Design

## Problem

A backend probe failure currently marks its placements stale and unavailable. When the
backend recovers, a later successful probe refreshes the backend catalog but does not
recompute the affected placement state. The control plane therefore continues reporting
`available=false` and routes fail with insufficient capacity until an external restart or
reconciliation path happens to rebuild state.

AetherForge adds a second failure mode: it classifies `no_capacity` as permanent. A
transient OMLXC placement outage therefore becomes an in-process blacklist that survives
backend recovery until the gateway restarts.

## Goal

Make backend recovery self-healing across the existing OMLXC composition and AetherForge
gateway boundaries, without introducing a second registry or changing routing policy.

## Non-goals

- Cost, quota, provider, or model-quality routing.
- Model file cleanup, credentials, launchd changes, or remote-node mutation.
- New health registries, background retry services, or a broad config migration.
- Treating a genuinely missing model or placement as transient forever.

## Invariants

1. A successful backend probe is authoritative for that backend's current catalog and
   readiness; placement state must be derived from it in the same refresh operation.
2. A failed probe may decay existing placement state but must not erase configuration.
3. A transient gateway failure may retry after the existing bounded TTL; permanent
   configuration failures remain non-decaying.
4. No request path may perform an unbounded synchronous retry.
5. Existing placement identity, routing precedence, and response schemas remain unchanged.

## Design

### OMLXC successful probe

In `omlxc.daemon.composition`, retain the current backend discovery/listing flow and make
its successful apply path recompute every configured placement bound to that backend. The
recomputed state must update the existing fields (`available`, `fresh`, `loaded`,
`ready`, and capacity/concurrency metadata) through the same state owner used by the
current `_fail_stale` path. The operation is idempotent and scoped to the probed backend;
other backends retain their current state.

The implementation must not infer readiness from catalog membership alone. It must preserve
the existing adapter-specific readiness/load checks and only clear stale state when the
backend probe supplies enough information to do so.

### AetherForge transient no-capacity

Remove the unconditional permanent classification for `no_capacity`. Treat that failure
as the existing transient health-failure class with the configured threshold and 60-second
TTL. On a successful request, reuse the existing reset path. Keep truly deterministic
missing-model/configuration errors permanent by their existing typed error classification;
do not broaden retries to all 4xx responses.

### Boundary behavior

A backend that remains unreachable continues to decay/stale placements as today. A backend
that recovers becomes routable on the next successful probe, without daemon or gateway
restart. A gateway process that saw transient no-capacity can retry after TTL and recover
on a later successful request.

## Verification

### Regression tests

- OMLXC integration coverage starts with a stale placement, supplies a successful backend
  probe, and asserts the placement becomes available/ready with current catalog state.
- AetherForge health-decay coverage asserts `no_capacity` expires through the existing TTL,
  while a typed permanent missing-model failure does not decay.

### Live canaries

1. `omlxc models show coding-next --json` reports current availability after a backend
   recovery probe.
2. `omlxc route plan coding-next --json` selects a current placement.
3. An authenticated AetherForge inference succeeds after the transient failure window,
   without restarting the gateway.

If the authenticated canary cannot run because the local runtime key is unavailable, record
that exact blocker; do not substitute an unauthenticated health check as inference proof.

## Risks and rollback

The main risk is falsely reviving a placement from incomplete catalog data. The guard is to
reuse the existing readiness/load predicates and scope updates to the probed backend. If a
regression appears, revert the successful-probe placement refresh and restore the prior
permanent classification only as an emergency rollback; do not widen scope into routing
policy.
