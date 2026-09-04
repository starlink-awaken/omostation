---
type: ssot
---

# Swarm-Engine → AetherForge Swarm Merge Notes

## Date

2026-06-16

## Source / Destination

- **Source submodule**: `projects/swarm-engine/src/swarm_engine/`
- **Destination package**: `projects/aetherforge/packages/swarm/src/swarm_engine/`

## What was merged

Copied **50 modules/files** that existed in the source submodule but were missing in the destination package, preserving the original directory structure under `swarm_engine`:

```text
association_engine.py
burndown_engine.py
dispatch/compat.py
engine/a2a_protocol.py
engine/archetype_distiller.py
engine/cognitive_bus.py
engine/compute_harvester.py
engine/compute_pool.py
engine/compute_pool_shard.py
engine/dispatch/compat.py
engine/ego_dispatch_loop.py
engine/hifi_query.py
engine/knowledge_enhancement_mixin.py
engine/lifecycle/cluster.py
engine/local_worker.py
engine/ooda_loop.py
engine/possession_multi_session.py
engine/swarm_emergence.py
engine/swarm_optimizer.py
execution_scheduler.py
hatcher_core.py
hypothesis_pipeline.py
ils_defaults.py
ils_engine.py
ils_plugins.py
ils_types.py
mapping_engine.py
mapping_worker_abstraction.py
mapping_worker_registry.py
mutation_validator.py
nks_task_planner.py
perception_manager.py
perception_validation.py
possession_multi_session.py
primordial_toolkit.py
redis_message_broker.py
refinement_daemon.py
result_aggregator.py
result_summarizer.py
rl_optimizer.py
semantic_index.py
structural_merger.py
synapse_anthropic.py
synapse_github.py
synapse_hub.py
synapse_ollama.py
universal_worker.py
vision_metabolizer.py
worker_dispatcher.py
worker_node.py
```

`__pycache__` directories and compiled `.pyc` files were intentionally skipped.

## Reconciliations

| Source path | Destination path | Decision |
|:------------|:-----------------|:---------|
| `swarm-engine/src/swarm_engine/a2a_protocol.py` | `aetherforge/packages/swarm/src/swarm_engine/a2a_protocol.py` | Files are identical. Kept the destination version as the canonical one. |
| `swarm-engine/src/swarm_engine/dispatch/compat.py` | `aetherforge/packages/swarm/src/swarm_engine/dispatch_compat.py` | Destination `dispatch_compat.py` is the canonical, self-contained helper. Copied the source variant under `dispatch/compat.py` for reference, but it still references legacy `organs.D_Execution` imports. |
| `swarm-engine/src/swarm_engine/engine/dispatch/compat.py` | `aetherforge/packages/swarm/src/swarm_engine/engine/dispatch/compat.py` | Copied as-is. It is a trimmed variant of the same helper and also references legacy `.organs.engine.result_bus`. |
| `swarm-engine/src/swarm_engine/engine/a2a_protocol.py` | `aetherforge/packages/swarm/src/swarm_engine/engine/a2a_protocol.py` | Copied as-is. This is a migration work-in-progress variant of the root `a2a_protocol.py` (it removes the old `spore` message-transport path). Kept for reference; it imports the external `synapse` package at top level. |

## Known unresolved legacy imports

Several copied modules still contain top-level imports pointing to legacy subsystems that no longer exist in the destination package (`organs.*`, `nucleus.Z_Spore.*`, `engine.result_bus`, `cedar`, `proxy_trap`, `synapse`, `workspace_sandbox`). These modules were copied to preserve code but **cannot be imported directly** until those legacy references are reconciled:

- `cost_aware_dispatcher.py`
- `dispatch/compat.py`
- `engine/a2a_protocol.py`
- `engine/dispatch/compat.py`
- `engine/local_worker.py`
- `execution_scheduler.py`
- `hatcher_core.py`
- `ils_engine.py`
- `nks_task_planner.py`
- `synapse_ollama.py`
- `universal_worker.py`
- `vision_metabolizer.py`
- `worker_dispatcher.py`
- `worker_node.py`

## Dependency changes

Added `redis>=8.0.0` to `projects/aetherforge/packages/swarm/pyproject.toml` to match the original `swarm-engine` dependency (needed by `redis_message_broker.py`).

## Import test

Added `tests/test_swarm_engine_imports.py` covering the newly copied modules that are self-contained and load without error.
