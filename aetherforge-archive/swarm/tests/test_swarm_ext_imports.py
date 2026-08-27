"""Smoke tests for migrated aetherforge-swarm-ext modules."""

import pytest

MODULES = [
    "swarm_engine.ext.archetype_distiller",
    "swarm_engine.ext.cluster",
    "swarm_engine.ext.cognitive_bus",
    "swarm_engine.ext.compute_harvester",
    "swarm_engine.ext.compute_pool",
    "swarm_engine.ext.compute_pool_shard",
    "swarm_engine.ext.ego_dispatch_loop",
    "swarm_engine.ext.hifi_query",
    "swarm_engine.ext.knowledge_enhancement_mixin",
    "swarm_engine.ext.local_worker",
    "swarm_engine.ext.ooda_loop",
    "swarm_engine.ext.swarm_emergence",
    "swarm_engine.ext.swarm_optimizer",
]


@pytest.mark.parametrize("module", MODULES)
def test_swarm_ext_module_imports(module: str) -> None:
    __import__(module)
