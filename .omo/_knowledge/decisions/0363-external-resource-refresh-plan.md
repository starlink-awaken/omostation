---
id: ADR-0363
title: External Resource Refresh Plan and Controlled Reachability
status: ACCEPTED
date: 2026-08-04
owner: architecture-governance
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0363: External Resource Refresh Plan and Controlled Reachability

## Context

External Connection Fabric already supports descriptor discovery, read-only health probes, OMO observations, freshness status and a capability
directory. These surfaces answer what a resource is and whether the latest observation is usable, but they do not provide one deterministic
control-plane projection for refresh cadence, recovery priority or human review. Without that projection, a future scheduler could refresh all
providers at the same frequency, or treat a visible resource as ready for invocation.

The project also needs a durable expansion path for external knowledge, data, material, methods, theories, tools, models and channels while real
business scenes remain sparse. The system must be able to keep these capabilities discoverable and reachable without creating production side
effects or a second workflow truth.

## Decision

Introduce `external-resource-refresh-plan/v1`, built by
`bin/ssot/external-resource-catalog.py::build_external_resource_refresh_plan` and exposed through
`GET /api/external-resources/refresh-plan`.

The projection:

1. assigns observation intervals by resource kind;
2. prioritizes unhealthy or stale resources for read-only `health_probe`;
3. routes expired or invalid descriptor deadlines to `human_review`;
4. marks normal resources as due or scheduled for `catalog_refresh`;
5. exposes due counts, priority counts, next due timestamps, reason codes and a stable digest;
6. remains read-only and never schedules work itself.

The refresh plan is a policy projection, not a scheduler. The caller or governed observer decides whether and when to execute an observation.
OMO remains the owner of append-only observation evidence; Agora remains the owner of discovery and routing; Cockpit remains a human visibility
surface. The plan cannot promote lifecycle, invoke provider business methods, create WorkflowRun, mutate admission or store credentials/raw content.

## Boundaries

- Resource visibility does not imply route availability or activation eligibility.
- `health_probe` is allowed only where the provider contract declares a read-only probe.
- `human_review` is mandatory for descriptor deadline problems and is never auto-replaced by a refresh.
- `force` affects only the returned projection and cannot cause execution.
- Actual activation still requires Scene Card, permission, owner, rollback plan, real consumer and outcome evidence.

## Consequences

Positive:

- External capability expansion gains a common cadence and recovery vocabulary across all resource kinds.
- Cost and operational pressure become visible before a scheduler or provider adapter is introduced.
- Cockpit can show the next action without keeping local scheduling state.
- The architecture can add periodic observers later without changing the descriptor, OMO evidence or Workflow Mesh contracts.

Trade-off:

- The first implementation is intentionally a projection; periodic execution and automatic recovery remain deferred until a real low-risk scene
  produces repeated demand and outcome evidence.

## Verification

- Root catalog tests cover scheduled, due, unhealthy and forced projection states.
- Cockpit API tests verify latest OMO observation is read and no scheduling or discovery side effect is performed.
- Registry and documentation point to the same schema and builder.
