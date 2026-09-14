---
id: ADR-0365
title: Adopt a scenario-first architecture strategy and Workflow Mesh as the sole execution spine
status: ACCEPTED
date: 2026-08-04
owner: architecture-governance
lifecycle: spec
last-reviewed: 2026-08-04
type: ssot
---

# ADR-0365: Adopt a scenario-first architecture strategy and Workflow Mesh as the sole execution spine

## Context

The workspace now has mature engineering foundations across OMO, ECOS, Runtime, AetherForge, Agora, Cockpit, Kairon/KOS and the External Connection Fabric. The remaining risk is not a missing generic capability; it is uncontrolled expansion without a repeated real business outcome. A second risk is allowing product scenarios, external providers or model experiments to create parallel task, knowledge or runtime truths.

## Decision

1. Product expansion is scenario-first. A new capability must attach to a real scene, journey and outcome metric before it is treated as a product capability.
2. Workflow Mesh is the sole execution spine for governed work. New automations must use its run identity, admission, dispatch, evidence, verification and closeout contracts.
3. OMO remains the authority for governance and execution state; Kairon/KOS remains the authority for normalized knowledge and evaluation data; External Connection Fabric remains the authority for external resource descriptors and lifecycle only.
4. External resources, method packs, prompts and models use proposal, sandbox, shadow and human-approved promotion states. Discovery and refresh never activate a resource or create a workflow run.
5. The first real validation target is a low-risk decision inbox journey. Forecasting and automatic business mutation remain blocked until real labels, repeated shadow evidence and explicit approval exist.

## Consequences

Positive:

- Product value is measured by completed, verified journeys rather than capability inventory.
- Cross-project boundaries remain explicit and new providers can be added through descriptors and packs.
- Model and external-resource evolution becomes reversible and evidence-based.

Cost:

- Early scenarios require more binding, evidence and human review.
- Some attractive integrations remain proposal-only until a real owner and outcome metric exist.
- Engineering work must sometimes stop and gather real operational evidence instead of adding another abstraction.

## Rejected alternatives

- A universal autonomous agent that directly mutates every business system.
- A second workflow engine inside a product module.
- Automatic provider or model activation based only on static discovery or offline benchmark results.

## Acceptance evidence

- `docs/ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md`
- `docs/WORKFLOW-MESH-IMPLEMENTATION.md`
- `.omo/_truth/registry/external-connection-fabric.yaml`
- KEMS repeated shadow promotion gate and its tests.
