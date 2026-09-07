---
id: ADR-0452
title: Scene System v3 Architecture
status: accepted
date: 2026-09-07
owner: governance-team
last-reviewed: 2026-09-07
tags: [scene, architecture, v3, lifecycle, calibration]
---

# ADR-0452: Scene System v3 Architecture

## Context

The Scene System v1/v2 had structural problems:
- 5-tier lifecycle was aspirational (only 1 scene reached `assisted`)
- No execution engine (scene-daemon.py archived)
- Schema dual-track (v1 + v2 coexisting)
- Calibration mechanism was empty (sample count = 0)
- Scene-to-scene communication was declared but not implemented

## Decision

Design Scene System v3 with deep integration into existing architecture:

### 1. Scene as OMO Task Type
Scene lifecycle transitions are OMO tasks (`task_type: scene_lifecycle`), reusing the existing task gate model.

### 2. BOS-Driven Execution
Scene `capability_refs` are BOS URIs resolved through Agora's `bos_router.resolve()` → `resolve_bos_uri()`.

### 3. Three-Layer Orchestration
- **Scene Graph (DAG)**: Inter-scene routing
- **Journey State Machine**: Intra-scene execution
- **Intent Executor**: Atomic operations with Saga compensation

### 4. Calibration Engine
Sliding-window trust scoring (30-day window) with three cycles: realtime, daily, weekly.

### 5. Anti-Corruption Layer
`scene-v3-guardrail.py` validates schema, consistency, reachability, and integrity.

## Consequences

**Positive:** No new infrastructure, gradual migration, automated quality.
**Negative:** BOS dependency, graph complexity growth.

## References
- ADR-0365: Scenario-first architecture
- `.omo/standards/scene-card-lifecycle.yaml`
- `bin/ssot/journey-engine.py`
