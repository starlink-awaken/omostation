# ADR-0390: Scene System v3 Architecture

> Status: accepted | Date: 2026-09-07 | Author: governance-team

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
Scene lifecycle transitions are OMO tasks (`task_type: scene_lifecycle`), reusing the existing task gate model (`candidate → pending → in_progress → review → done`).

### 2. BOS-Driven Execution
Scene `capability_refs` are BOS URIs resolved through Agora's `bos_router.resolve()` → `resolve_bos_uri()`. This avoids building a new dispatch layer.

### 3. Three-Layer Orchestration
- **Scene Graph (DAG)**: Inter-scene routing
- **Journey State Machine**: Intra-scene execution
- **Intent Executor**: Atomic operations with Saga compensation

### 4. Calibration Engine
Sliding-window trust scoring (30-day window) with three cycles:
- Realtime: metric update after each execution
- Daily: score computation + gate checks
- Weekly: trend analysis + evolution proposals

### 5. Anti-Corruption Layer
`scene-v3-guardrail.py` validates:
- JSON Schema compliance
- lifecycle/activation consistency
- capability_refs BOS URI reachability
- topology reference integrity
- quality metric weights sum to 1.0

## Consequences

**Positive:**
- No new infrastructure — reuses OMO/Cockpit/Agora
- Gradual migration path (v1/v2 → v3)
- Automated quality enforcement

**Negative:**
- BOS URI resolution depends on Agora availability
- Scene graph complexity grows with scene count

## References
- ADR-0365: Scenario-first architecture
- `.omo/standards/scene-card-lifecycle.yaml`
- `bin/ssot/journey-engine.py`
