---
id: ADR-0364
title: KEMS repeated shadow evaluation and human promotion gate
status: ACCEPTED
date: 2026-08-04
owner: architecture-governance
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0364: KEMS Repeated Shadow Evaluation and Human Promotion Gate

## Context

KEMS already produces a redacted, manifest-bound model acceptance report for one shadow evaluation. A single passing report is insufficient for
production consideration: it may reflect a small sample, a stale or different manifest, an inconsistent metric declaration, or a lucky run.
Automatic model promotion would also create a second authority beside OMO and bypass Workflow Mesh admission.

## Decision

Add `kems.model-promotion-gate.v1`, implemented by
`projects/kairon/packages/kos/src/kos/kems/promotion_gate.py::build_model_promotion_gate` and exposed by
`projects/kairon/scripts/kems_model_promotion_gate.py`.

The gate requires repeated acceptance reports from the same candidate and baseline model, bound to the same dataset identity and evaluation
manifest SHA. It recomputes weighted MAE and relative improvement, checks minimum run and observation thresholds, rejects duplicate reports,
requires every run to be `shadow_pass`, and rejects inconsistent declared improvement values.

The only positive state is `eligible_for_human_approval`. The gate always emits `automatic_promotion=false` and
`promotion=blocked_until_omo_approval`; it never mutates a model registry, route, WorkflowRun, admission state or provider.

## Consequences

- Model evaluation becomes repeatable and comparable before human review.
- Stale, mixed, duplicated or tampered reports fail closed with explicit reason codes.
- Human/OMO approval remains the single promotion authority and can later bind canary and rollback evidence.
- Real business accuracy is still not claimed until a real consumer produces a sufficient, adjudicated manifest.

## Verification

- Kairon KEMS promotion-gate, model-acceptance and forecast tests pass.
- Ruff passes on the new module, exports, tests and CLI.
