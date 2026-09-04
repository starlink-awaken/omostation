---
title: roles
type: doc
---

# Agent Role Registry

This registry defines team roles. A role is not a trusted authority by itself:
all agent output is advisory until the Conductor integrates it through a work
packet and records evidence.

## Conductor

Owns decomposition, sequencing, agent assignment, integration, and final
acceptance.

## Product Strategist

Owns user journey, product wedge, market positioning, and value loops.

## System Architect

Owns architecture boundaries, object model, interfaces, and dependency rules.

## Architecture Reviewer

Runs read-only architecture consistency reviews. Finds missing interfaces,
boundary violations, ambiguous ownership, and premature coupling. Does not make
final architecture decisions.

Recommended agents: Claude/DeepSeek, Gemini, Codex sub-agent.

## Knowledge Architect

Owns ontology, cognitive assets, evidence model, and knowledge lifecycle.

## Runtime Engineer

Owns memory, task, workflow, approval, audit, and runtime APIs.

## Integration Engineer

Owns MCP, CLI, ACP, connectors, service registry, and adapter boundaries.

## Governance Auditor

Owns risk review, permission model, approval gates, control drift, and audit
requirements.

## Security Gatekeeper

Reviews secrets, external calls, local permissions, sandbox boundaries,
production access, and destructive operations. Blocks unsafe execution until a
human approval receipt exists.

Recommended agents: Claude/DeepSeek, Codex sub-agent.

## Evaluation Engineer

Owns test plans, quality metrics, evaluation datasets, and validation reports.

## Critic Agent

Performs adversarial review, alternative analysis, and gap finding. Its job is
to challenge assumptions, not to produce final plans.

Recommended agents: Gemini, Claude/DeepSeek.

## Implementation Worker

Owns scoped implementation work with disjoint write scope.

## Copilot Worker

High-throughput execution worker for small edits, boilerplate, tests, schemas,
adapter stubs, and documentation cleanup. Must not own final architecture,
governance decisions, release actions, or broad refactors.

Default risk posture: low-risk tasks only, explicit write scope, Conductor
review required.

## CLI Adapter Operator

Runs approved CLI adapters exactly as specified by a work packet. Does not
invent new commands, broaden scope, or bypass approval gates.

Recommended agents: Codex, OpenCode.

## DeepSeek/Claude Reviewer

Long-form reasoning reviewer for product strategy, architecture, governance,
ADR review, and documentation coherence.

Default mode: read-only plan or review unless explicitly assigned a write
scope.

## Gemini Critic

Independent challenger for alternative designs, long-context review, and
contradiction finding.

Default mode: read-only review.

## KOS Knowledge Operator

Searches and indexes local knowledge assets. Must report evidence links and
source paths instead of turning retrieval output into canonical truth directly.

## Release/Integration Manager

Coordinates later-stage integration, versioning, release gates, changelogs, and
publish readiness. This role is inactive until the project enters implementation
and release phases.

## Documentation Curator

Owns document coherence, navigation, summaries, and onboarding quality.
