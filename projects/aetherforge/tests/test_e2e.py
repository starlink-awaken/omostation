"""AetherForge E2E integration test suite.

Tests every layer of the stack end-to-end:
  1. Config loading
  2. Gateway: providers, policies, rate limiter
  3. Mesh: topology, pool, scheduler (with queue), worker
  4. Swarm: hierarchical process
  5. Cross-layer integration
  6. Edge cases
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback

# Ensure packages are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "mesh", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "swarm", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Test runner ────────────────────────────────────────────────────────────

passed = 0
failed = 0
errors: list[str] = []


def test(name: str):
    """Decorator to register a test function."""
    def decorator(fn):
        def wrapper():
            global passed, failed
            try:
                fn()
                passed += 1
                print(f"  ✅ {name}")
            except Exception as e:
                failed += 1
                errors.append(f"❌ {name}: {e}\n{traceback.format_exc()}")
                print(f"  ❌ {name}: {e}")
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════
# 1. Config
# ══════════════════════════════════════════════════════════════════════════

@test("Config: load defaults")
def test_config_defaults():
    from aetherforge.config import load_config
    cfg = load_config()
    assert cfg.gateway.enabled is True
    assert cfg.rate_limiter.enabled is True
    assert cfg.topology.health_check_interval == 60
    assert cfg.pool.auto_scale is True
    print(f"    gateway.enabled={cfg.gateway.enabled} rate_limiter.enabled={cfg.rate_limiter.enabled}")


@test("Config: write and reload")
def test_config_write():
    from aetherforge.config import write_default_config, load_config
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "aetherforge.yaml")
    write_default_config(path)
    cfg = load_config(path)
    assert cfg.gateway.enabled is True
    print(f"    loaded from {path}")


# ══════════════════════════════════════════════════════════════════════════
# 2. Gateway
# ══════════════════════════════════════════════════════════════════════════

@test("Gateway: 6 providers importable")
def test_gateway_providers():
    from llm_gateway.providers import (
        ollama_provider, openai_provider, anthropic_provider,
        gemini_provider, deepseek_provider, hitl_provider,
    )
    # Instantiate all
    p_ollama = ollama_provider.OllamaProvider()
    p_hitl = hitl_provider.HitlLLMProvider()
    assert p_ollama.provider_name == "ollama"
    assert p_hitl.provider_name == "hitl"
    print(f"    ollama={p_ollama.provider_name} hitl={p_hitl.provider_name}")


@test("Gateway: RateLimiter tpm/rpm")
def test_gateway_rate_limiter():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("test", tpm=100, rpm=5)
    assert rl.acquire("test", 60) is True
    assert rl.acquire("test", 40) is True  # total = 100
    assert rl.acquire("test", 1) is False  # would exceed 100 tpm
    stats = rl.get_status()
    assert "test" in stats
    print(f"    tpm_usage={stats['test']['tpm']['usage_pct']}% limited_models={rl.total_limited_models}")


@test("Gateway: RouterPipeline Filter/Score")
def test_gateway_pipeline():
    from llm_gateway.policies import (
        RouterPipeline, OnlineFilter, CostScore, CapabilityFilter,
        BudgetFilter, SpeedScore, BalancedScore,
    )
    from llm_gateway.types import ModelDescriptor, ModelRequest

    models = [
        ModelDescriptor(id="a", provider="p1", capabilities=["chat"], is_available=True,
                        cost_per_1k_tokens={"input": 0.01, "output": 0.02}, context_window=4096),
        ModelDescriptor(id="b", provider="p2", capabilities=["chat", "vision"], is_available=True,
                        cost_per_1k_tokens={"input": 0.03, "output": 0.06}, context_window=8192),
        ModelDescriptor(id="c", provider="p3", capabilities=["chat"], is_available=False,
                        cost_per_1k_tokens={"input": 0.005, "output": 0.005}, context_window=2048),
    ]
    req = ModelRequest(task="test", required_capabilities=["chat"])

    # Pipeline
    pipeline = RouterPipeline()
    pipeline.add_filter(OnlineFilter())
    pipeline.add_filter(CapabilityFilter())
    pipeline.add_score(CostScore())
    pipeline.add_score(BalancedScore())

    ranked = pipeline.select(models, req)
    assert len(ranked) == 2  # offline filtered
    assert ranked[0].model.id == "a" or ranked[0].score >= ranked[1].score
    print(f"    candidates={len(ranked)} top={ranked[0].model.id} score={ranked[0].score:.2f}")


@test("Gateway: MetricsCollector")
def test_gateway_metrics():
    from llm_gateway.metrics import MetricsCollector
    mc = MetricsCollector()
    mc.record_latency("gpt-4", 100.0)
    mc.record_cost("gpt-4", 0.01, tokens=100)
    mc.record_error("gpt-4", "timeout")
    mc.record_rate_limit("gpt-4")
    mc.record_latency("gpt-4", 200.0)
    r = mc.report()
    m = r["models"]["gpt-4"]
    assert m["requests"] == 2
    assert m["errors"] == 1
    assert m["rate_limits"] == 1
    assert m["total_cost"] == 0.01
    assert r["total_requests"] == 2
    print(f"    requests={r['total_requests']} errors={r['total_errors']} rate_limits={r['total_rate_limits']}")


@test("Gateway: FallbackRule")
def test_gateway_fallback():
    from llm_gateway.types import FallbackRule, ModelRoutePolicy
    rule = FallbackRule(model="gpt-4", strategy="speed-first", timeout_ms=10000, cooldown_ms=5000)
    policy = ModelRoutePolicy(strategy="balanced", fallback_chain=[rule])
    assert len(policy.fallback_chain) == 1
    assert policy.fallback_chain[0].model == "gpt-4"
    assert policy.fallback_chain[0].strategy == "speed-first"
    print(f"    fallback={policy.fallback_chain[0].model} strategy={policy.fallback_chain[0].strategy}")


# ══════════════════════════════════════════════════════════════════════════
# 3. Mesh
# ══════════════════════════════════════════════════════════════════════════

@test("Mesh: TopologyLabels 4-layer")
def test_mesh_topology():
    from compute_mesh.topology import TopologyLabels
    tl = TopologyLabels(region="us-east-1", zone="us-east-1a", rack="r01", host="gpu-01")
    assert tl.affinity_score(TopologyLabels(zone="us-east-1a")) == 0.25
    assert tl.affinity_score(TopologyLabels(zone="us-east-1b")) == 0.0
    assert tl.affinity_score(tl) == 1.0
    assert tl.matches(TopologyLabels(zone="us-east-1a")) is True
    assert tl.matches(TopologyLabels(zone="us-east-1b")) is False
    d = tl.to_dict()
    assert d["region"] == "us-east-1"
    print(f"    affinity(zone)={tl.affinity_score(TopologyLabels(zone='us-east-1a')):.2f} dict={d}")


@test("Mesh: ComputeNode with topology")
def test_mesh_compute_node():
    from compute_mesh.topology import ComputeNode, TopologyLabels, NodeEngineType
    node = ComputeNode(
        node_id="test",
        engine_type=NodeEngineType.LOCAL_DAEMON,
        topology=TopologyLabels(host="mini.local"),
    )
    assert node.network_zone == "local"  # derived from host
    d = node.to_dict()
    assert d["topology"]["host"] == "mini.local"

    cloud_node = ComputeNode(
        node_id="cloud",
        engine_type=NodeEngineType.CLOUD_API,
        topology=TopologyLabels(region="us-east-1"),
    )
    assert cloud_node.network_zone == "cloud"
    print(f"    local.zone={node.network_zone} cloud.zone={cloud_node.network_zone}")


@test("Mesh: NodeRegistry CRUD")
def test_mesh_registry():
    from compute_mesh.topology import NodeRegistry, ComputeNode
    reg = NodeRegistry()
    n1 = ComputeNode(node_id="n1")
    n2 = ComputeNode(node_id="n2")
    assert reg.register(n1) is True
    assert reg.register(n1) is False  # already registered
    assert reg.register(n2) is True
    assert reg.count() == 2
    assert reg.get("n1") is not None
    assert reg.get("n3") is None
    assert reg.unregister("n1") is True
    assert reg.count() == 1
    print(f"    count={reg.count()} after add/remove")


@test("Mesh: TopologyScanner discovery")
def test_mesh_scanner():
    from compute_mesh.topology import TopologyScanner
    scanner = TopologyScanner()
    nodes = scanner.scan_all()
    # Should find at least Ollama (if running) + cloud providers
    assert len(nodes) >= 1
    print(f"    discovered {len(nodes)} nodes")


@test("Mesh: ComputePool health + best node")
def test_mesh_pool():
    from compute_mesh.pool import ComputePool
    pool = ComputePool()
    pool.scan()
    pool.health_check_all()
    summary = pool.get_summary()
    assert summary["total"] >= 1
    best = pool.get_best_node()
    if best:
        print(f"    {summary['total']} nodes: {summary['online']} online, best={best.node_id}")
    else:
        print(f"    {summary['total']} nodes: {summary['online']} online (no best)")


@test("Mesh: CostTracker SQLite dual write")
def test_mesh_cost():
    from compute_mesh.pool import CostTracker, CostDB
    from compute_mesh.topology import NodeRegistry
    import tempfile

    tmp = tempfile.mkdtemp()
    db = CostDB(db_path=os.path.join(tmp, "test.db"), jsonl_path=os.path.join(tmp, "test.jsonl"))
    db.record("node-a", "gpt-4", 100, 50, 0.005)
    db.record("node-b", "claude", 200, 100, 0.010)
    report = db.get_report()
    assert report["total_requests"] == 2
    assert report["total_cost"] == 0.015
    assert os.path.exists(os.path.join(tmp, "test.db"))

    reg = NodeRegistry()
    tracker = CostTracker(reg)
    tracker.record("node-a", prompt_tokens=50, completion_tokens=25)
    r = tracker.get_report()
    assert r["session"]["total_requests"] >= 1
    print(f"    sqlite=2 records cost=0.015 session={r['session']['total_requests']}")


@test("Mesh: WorkerRegistry + TaskDispatcher")
def test_mesh_worker():
    from compute_mesh.worker import WorkerRegistry, TaskDispatcher, MeshWorker
    from compute_mesh.pool import ComputePool

    pool = ComputePool()
    pool.scan()
    reg = WorkerRegistry()
    dispatcher = TaskDispatcher(pool, reg)

    # Provision workers
    workers = dispatcher.provision_all(workers_per_node=2)
    assert len(workers) >= 1

    stats = reg.get_stats()
    assert stats["total"] >= 1
    assert stats["idle"] >= 1

    # Heartbeat
    assert reg.heartbeat(workers[0].worker_id) is True
    print(f"    workers={stats['total']} idle={stats['idle']}")


@test("Mesh: WorkerMessageBus")
def test_mesh_message_bus():
    from compute_mesh.worker.message_bus import WorkerMessageBus
    bus = WorkerMessageBus()

    # Direct message
    bus.send("w1", {"msg": "hello"}, sender="manager")
    msgs = bus.receive("w1")
    assert len(msgs) == 1
    assert msgs[0].payload["msg"] == "hello"

    # Broadcast
    bus.send("*", {"broadcast": True})
    msgs_b = bus.receive("w2")
    assert len(msgs_b) == 1

    # Subscribe
    received = []
    bus.subscribe("w3", lambda m: received.append(m))
    bus.send("w3", {"push": True})
    assert len(received) == 1

    stats = bus.get_stats()
    print(f"    delivered={len(msgs)} broadcast={len(msgs_b)} push={len(received)}")


@test("Mesh: Queue in MeshScheduler")
def test_mesh_queue():
    from compute_mesh.scheduler import MeshScheduler
    from compute_mesh.pool import ComputePool
    from llm_gateway.types import ModelRequest

    pool = ComputePool()
    mesh_sched = MeshScheduler(pool, None, max_queue_size=10)

    req = ModelRequest(task="test")
    assert mesh_sched.enqueue_request(req) is True

    stats = mesh_sched.get_queue_stats()
    assert stats["queued"] == 1
    assert stats["max_size"] == 10

    ready = mesh_sched.dequeue_ready()
    # May be empty if no nodes are online
    stats2 = mesh_sched.get_queue_stats()
    print(f"    queued={stats['queued']} max={stats['max_size']} dequeued={len(ready)}")


@test("Mesh: Auto-scale workers")
def test_mesh_auto_scale():
    from compute_mesh.pool import ComputePool
    from compute_mesh.worker import WorkerRegistry

    pool = ComputePool()
    pool.scan()
    pool.health_check_all()
    reg = WorkerRegistry()

    result = pool.auto_scale_workers(reg, min_workers=2, max_workers=10)
    assert result["total"] >= 1
    print(f"    workers={result['total']} reason={result['reason']}")


# ══════════════════════════════════════════════════════════════════════════
# 4. Swarm
# ══════════════════════════════════════════════════════════════════════════

@test("Swarm: GatewaySynapse")
def test_swarm_synapse():
    from swarm_engine import GatewaySynapse
    synapse = GatewaySynapse()
    health = synapse.health()
    assert health["status"] == "active"
    models = synapse.discover_models()
    assert isinstance(models, list)
    print(f"    active providers={health['total_available']} models={len(models)}")


@test("Swarm: HierarchicalProcess parse")
def test_swarm_hp_parse():
    from swarm_engine.hierarchical_process import HierarchicalProcess, SubTask
    hp = HierarchicalProcess()
    # Test JSON parsing
    subtasks = hp._parse_subtasks('[{"id":"s1","description":"Research","agent_role":"researcher","depends_on":[]}]')
    assert len(subtasks) == 1
    assert subtasks[0].id == "s1"
    assert subtasks[0].agent_role == "researcher"

    # Test with code fences
    subtasks2 = hp._parse_subtasks('```\n[{"id":"t1","description":"Write","agent_role":"writer","depends_on":[]}]\n```')
    assert len(subtasks2) == 1
    assert subtasks2[0].id == "t1"
    print(f"    parse_json={len(subtasks)} parse_fence={len(subtasks2)}")


@test("Swarm: HierarchicalProcess DAG")
def test_swarm_hp_dag():
    from swarm_engine.hierarchical_process import SubTask
    subtasks = [
        SubTask(id="a", agent_role="w"),
        SubTask(id="b", agent_role="w", depends_on=["a"]),
        SubTask(id="c", agent_role="w", depends_on=["a"]),
        SubTask(id="d", agent_role="w", depends_on=["b", "c"]),
    ]
    executed = []
    remaining = {s.id for s in subtasks}
    for _ in range(10):
        for s in subtasks:
            if s.id not in remaining:
                continue
            if all(dep in executed for dep in s.depends_on):
                executed.append(s.id)
                remaining.discard(s.id)
    assert len(executed) == 4
    assert "a" == executed[0]
    assert "d" == executed[-1]
    print(f"    order={executed}")


# ══════════════════════════════════════════════════════════════════════════
# 5. Cross-layer
# ══════════════════════════════════════════════════════════════════════════

@test("Cross-layer: Gateway → Mesh integration")
def test_cross_gateway_mesh():
    from compute_mesh.pool import ComputePool
    from compute_mesh.scheduler import MeshScheduler
    from compute_mesh.topology import TopologyScanner
    from llm_gateway.registry import ModelRegistry
    from llm_gateway.scheduler import ModelScheduler as GatewayScheduler

    pool = ComputePool()
    pool.scan()

    reg = ModelRegistry()
    gateway = GatewayScheduler(reg)
    mesh_sched = MeshScheduler(pool, gateway)

    status = mesh_sched.get_scheduler_status()
    assert "provider_node_map" in status
    assert "queue" in status
    print(f"    providers_mapped={len(status['provider_node_map'])} online={len(status['online_nodes'])}")


@test("Cross-layer: Config → RateLimiter integration")
def test_cross_config_limiter():
    from aetherforge.config import load_config
    from llm_gateway.rate_limiter import RateLimiter

    cfg = load_config()
    limiter = RateLimiter()
    cfg.apply_to_rate_limiter(limiter)
    # With defaults (0 = unlimited), everything should pass
    assert limiter.acquire("any-model", 1000000) is True
    print(f"    rate_limiter applied from config (default_tpm={cfg.rate_limiter.default_tpm})")


# ══════════════════════════════════════════════════════════════════════════
# 6. Edge cases
# ══════════════════════════════════════════════════════════════════════════

@test("Edge: Empty topology scan")
def test_edge_empty_scan():
    from compute_mesh.topology import TopologyScanner
    scanner = TopologyScanner()
    nodes = scanner.scan_all()
    # Should not crash, should return a list
    assert isinstance(nodes, list)
    print(f"    scanned {len(nodes)} nodes (no crash)")


@test("Edge: RateLimiter unlimited")
def test_edge_unlimited():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()  # no limits set
    assert rl.acquire("anything", 1_000_000) is True
    assert rl.total_limited_models == 0
    print(f"    unlimited=True limited_models={rl.total_limited_models}")


@test("Edge: WorkerRegistry heartbeat timeout")
def test_edge_heartbeat():
    from compute_mesh.worker import WorkerRegistry, MeshWorker
    reg = WorkerRegistry(heartbeat_timeout=0.01)  # 10ms timeout
    w = MeshWorker(worker_id="test-w", node_id="test-n")
    reg.register(w)
    import time
    time.sleep(0.02)
    stale = reg.check_stale()
    assert "test-w" in stale
    assert reg.get("test-w").status.value == "error"
    print(f"    stale_detected={stale[0] if stale else 'none'}")


@test("Edge: MessageBus full cycle")
def test_edge_bus_full():
    from compute_mesh.worker.message_bus import WorkerMessageBus
    import tempfile

    tmp = tempfile.mkdtemp()
    bus = WorkerMessageBus(db_path=os.path.join(tmp, "bus.db"))

    # Send 5 messages
    for i in range(5):
        bus.send("worker-1", {"seq": i}, msg_type="data")

    # Receive all
    msgs = bus.receive("worker-1")
    assert len(msgs) == 5
    assert [m.payload["seq"] for m in msgs] == [0, 1, 2, 3, 4]

    # Second receive should be empty
    assert len(bus.receive("worker-1")) == 0

    # History from SQLite
    history = bus.get_history("worker-1")
    assert len(history) >= 5
    print(f"    sent=5 received=5 history={len(history)}")


# ══════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════

def run_all():
    global passed, failed, errors

    print("=" * 60)
    print("  AetherForge E2E Integration Test Suite")
    print("=" * 60)

    # Collect all test functions
    import inspect
    test_fns = []
    for name, fn in inspect.getmembers(sys.modules[__name__]):
        if name.startswith("test_") and callable(fn):
            test_fns.append(fn)

    # Run them
    for fn in sorted(test_fns, key=lambda f: f.__name__):
        fn()

    # Summary
    total = passed + failed
    print()
    print("=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if errors:
        for e in errors:
            print(e)
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
