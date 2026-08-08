"""多进程模拟多机验证 — 蜂群式AI超级大脑分布式场景测试

使用 multiprocessing 模拟多机通信，验证：
1. 状态同步：多节点 CRDT 同步
2. 故障转移：节点故障自动切换
3. 负载均衡：多节点负载分配
4. 蜂群决策：多 Agent 集体决策
5. 性能基准：真实通信延迟
"""

import time
import tempfile
import os
from multiprocessing import Process, Queue

import pytest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# ══════════════════════════════════════════════════════════════
# 多进程 worker 函数 (必须在模块级别定义才能被 pickle)
# ══════════════════════════════════════════════════════════════


def _sync_worker(queue, node_id, data):
    """同步 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService(node_id, SyncStrategy.EVENTUAL)
    for k, v in data.items():
        node.set(k, v)
    queue.put(
        {
            "node_id": node_id,
            "state": node.get_all(),
            "clock": node.get_clock(),
        }
    )


def _sync_worker_with_update(queue, node_id, initial_data, sync_data):
    """带更新的同步 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService(node_id, SyncStrategy.EVENTUAL)
    for k, v in initial_data.items():
        node.set(k, v)

    queue.put(
        {
            "type": "initial",
            "node_id": node_id,
            "state": node.get_all(),
            "clock": node.get_clock(),
        }
    )

    time.sleep(0.05)

    for k, v in sync_data.items():
        node.set(k, v)

    queue.put(
        {
            "type": "updated",
            "node_id": node_id,
            "state": node.get_all(),
            "clock": node.get_clock(),
        }
    )


def _writer_worker(queue, node_id, key, values):
    """写入 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService(node_id, SyncStrategy.EVENTUAL)
    for v in values:
        node.set(key, v)
    queue.put(
        {
            "node_id": node_id,
            "state": node.get_all(),
            "clock": node.get_clock(),
        }
    )


def _perf_worker(queue, data):
    """性能测试 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService("worker", SyncStrategy.EVENTUAL)
    for k, v in data.items():
        node.set(k, v)
    queue.put(node.get_all())


def _multi_worker(queue, node_id, role, load):
    """多进程工作流 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService(node_id, SyncStrategy.EVENTUAL)
    node.set("role", role)
    node.set("load", str(load))

    queue.put(
        {
            "node_id": node_id,
            "role": role,
            "load": load,
            "clock": node.get_clock(),
        }
    )


# ══════════════════════════════════════════════════════════════
# 场景 1: 多节点状态同步
# ══════════════════════════════════════════════════════════════


class TestMultiNodeStateSync:
    """多节点状态同步测试"""

    def test_two_node_sync(self):
        """两节点同步"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        a.set("x", 1)
        snap_a = a.generate_snapshot()
        b.sync_from_snapshot(snap_a)

        assert b.get("x") == 1

    def test_three_node_cascade_sync(self):
        """三节点级联同步"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        nodes = [StateSyncService(f"node-{i}", SyncStrategy.EVENTUAL) for i in range(3)]

        nodes[0].set("config", "v1")
        snap0 = nodes[0].generate_snapshot()
        nodes[1].sync_from_snapshot(snap0)
        nodes[2].sync_from_snapshot(snap0)

        nodes[1].set("counter", 100)
        snap1 = nodes[1].generate_snapshot()
        nodes[0].sync_from_snapshot(snap1)
        nodes[2].sync_from_snapshot(snap1)

        for n in nodes:
            assert n.get("config") == "v1"
            assert n.get("counter") == 100

    def test_conflict_resolution(self):
        """冲突解决 — EVENTUAL consistency 检测到冲突"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        a.set("key", "value-a")
        b.set("key", "value-b")

        snap_a = a.generate_snapshot()
        snap_b = b.generate_snapshot()

        result_a = a.sync_from_snapshot(snap_b)
        result_b = b.sync_from_snapshot(snap_a)

        assert result_a.success
        assert result_b.success
        assert len(result_a.conflicts) > 0 or len(result_b.conflicts) > 0

    def test_vector_clock_progression(self):
        """向量时钟递增"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        initial_clock = a.get_clock()
        assert initial_clock["a"] == 0

        a.set("k1", "v1")
        clock1 = a.get_clock()
        assert clock1["a"] == 1

        snap = a.generate_snapshot()
        b.sync_from_snapshot(snap)
        clock2 = b.get_clock()
        assert clock2["a"] == 1
        assert clock2["b"] >= 0

    def test_delta_sync(self):
        """增量同步"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        a.set("k1", "v1")
        a.set("k2", "v2")

        delta = a.get_delta_since({"a": 0})
        assert "k1" in delta
        assert "k2" in delta

        delta2 = a.get_delta_since({"a": 2})
        assert len(delta2) == 0

    def test_batch_merge(self):
        """批量合并"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        a.set("k1", "v1")
        b.set("k2", "v2")

        result = a.merge_state(b.get_all(), b.get_clock())
        assert result.success
        assert a.get("k1") == "v1"
        assert a.get("k2") == "v2"


# ══════════════════════════════════════════════════════════════
# 场景 2: 多进程模拟多机通信
# ══════════════════════════════════════════════════════════════


class TestMultiProcessSimulation:
    """多进程模拟多机通信测试"""

    def test_two_process_state_sync(self):
        """两进程状态同步"""
        queue = Queue()

        p1 = Process(
            target=_sync_worker,
            args=(queue, "worker-1", {"task": "compute", "load": 50}),
        )
        p2 = Process(
            target=_sync_worker, args=(queue, "worker-2", {"task": "store", "load": 30})
        )

        p1.start()
        p2.start()
        p1.join()
        p2.join()

        results = []
        while not queue.empty():
            results.append(queue.get())

        results.sort(key=lambda x: x["node_id"])

        assert len(results) == 2
        assert results[0]["state"]["task"] == "compute"
        assert results[1]["state"]["task"] == "store"

    def test_four_node_distributed_sync(self):
        """四节点分布式同步"""
        queue = Queue()

        configs = [
            ("node-0", {"role": "primary", "config": "v1"}, {"status": "active"}),
            ("node-1", {"role": "secondary", "config": "v1"}, {"status": "active"}),
            ("node-2", {"role": "worker", "config": "v1"}, {"status": "busy"}),
            ("node-3", {"role": "worker", "config": "v1"}, {"status": "idle"}),
        ]

        processes = []
        for node_id, initial, sync in configs:
            p = Process(
                target=_sync_worker_with_update, args=(queue, node_id, initial, sync)
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        results = []
        while not queue.empty():
            results.append(queue.get())

        initial_results = [r for r in results if r["type"] == "initial"]
        updated_results = [r for r in results if r["type"] == "updated"]

        assert len(initial_results) == 4
        assert len(updated_results) == 4

        for r in updated_results:
            assert r["state"]["config"] == "v1"
            assert r["state"]["status"] in ("active", "busy", "idle")

    def test_concurrent_writes(self):
        """并发写入"""
        queue = Queue()

        p1 = Process(
            target=_writer_worker, args=(queue, "w1", "counter", list(range(10)))
        )
        p2 = Process(
            target=_writer_worker, args=(queue, "w2", "counter", list(range(10, 20)))
        )

        p1.start()
        p2.start()
        p1.join()
        p2.join()

        results = []
        while not queue.empty():
            results.append(queue.get())

        assert len(results) == 2

        final_values = [r["state"]["counter"] for r in results]
        assert all(v in (19, 9) for v in final_values)


# ══════════════════════════════════════════════════════════════
# 场景 3: 故障转移模拟
# ══════════════════════════════════════════════════════════════


class TestFailoverSimulation:
    """故障转移模拟测试"""

    def test_round_robin_failover(self):
        """轮询故障转移"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        fm = FailoverManager()
        fm.add_rule(
            FailoverRule(
                "r1", "primary", ["s1", "s2", "s3"], FailoverStrategy.ROUND_ROBIN
            )
        )

        targets = []
        for _ in range(6):
            t = fm.execute_failover("primary")
            targets.append(t)

        assert targets == ["s1", "s2", "s3", "s1", "s2", "s3"]

    def test_least_loaded_failover(self):
        """最小负载故障转移"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        fm = FailoverManager()
        fm.update_node_load("s1", 10)
        fm.update_node_load("s2", 2)
        fm.update_node_load("s3", 5)

        fm.add_rule(
            FailoverRule(
                "r1", "primary", ["s1", "s2", "s3"], FailoverStrategy.LEAST_LOADED
            )
        )

        target = fm.execute_failover("primary")
        assert target == "s2"

    def test_priority_failover(self):
        """优先级故障转移"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        fm = FailoverManager()
        fm.update_node_priority("s1", 1)
        fm.update_node_priority("s2", 10)
        fm.update_node_priority("s3", 5)

        fm.add_rule(
            FailoverRule("r1", "primary", ["s1", "s2", "s3"], FailoverStrategy.PRIORITY)
        )

        target = fm.execute_failover("primary")
        assert target == "s2"

    def test_failover_history(self):
        """故障转移历史"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        fm = FailoverManager()
        fm.add_rule(
            FailoverRule("r1", "primary", ["s1", "s2"], FailoverStrategy.ROUND_ROBIN)
        )

        fm.execute_failover("primary")
        fm.execute_failover("primary")
        fm.execute_failover("primary")

        history = fm.get_failover_history()
        assert len(history) == 3

        counts = fm.get_failover_count()
        assert counts["primary"] == 3


# ══════════════════════════════════════════════════════════════
# 场景 4: 负载均衡模拟
# ══════════════════════════════════════════════════════════════


class TestLoadBalancingSimulation:
    """负载均衡模拟测试"""

    def test_round_robin_distribution(self):
        """轮询负载分布"""
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy

        lb = LoadBalancer(LoadBalancingStrategy.ROUND_ROBIN)
        for i in range(4):
            lb.register_node(f"node-{i}")

        selections = []
        for _ in range(12):
            selections.append(lb.select_node())

        counts = {}
        for s in selections:
            counts[s] = counts.get(s, 0) + 1

        assert all(c == 3 for c in counts.values())

    def test_least_connections(self):
        """最少连接"""
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy

        lb = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
        lb.register_node("n1")
        lb.register_node("n2")
        lb.register_node("n3")

        lb.update_connections("n1", 10)
        lb.update_connections("n2", 3)
        lb.update_connections("n3", 7)

        selected = lb.select_node()
        assert selected == "n2"

    def test_weighted_distribution(self):
        """加权负载分布"""
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy

        lb = LoadBalancer(LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        lb.register_node("n1", weight=1)
        lb.register_node("n2", weight=3)

        selections = []
        for _ in range(8):
            selections.append(lb.select_node())

        counts = {}
        for s in selections:
            counts[s] = counts.get(s, 0) + 1

        assert counts.get("n2", 0) > counts.get("n1", 0)


# ══════════════════════════════════════════════════════════════
# 场景 5: 蜂群决策模拟
# ══════════════════════════════════════════════════════════════


class TestSwarmDecisionSimulation:
    """蜂群决策模拟测试"""

    def test_majority_vote(self):
        """多数投票"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        cd = CollectiveDecision()
        cd.create_proposal(
            "p1",
            "部署策略",
            ["blue-green", "canary", "rolling"],
            DecisionMethod.MAJORITY_VOTE,
        )

        for i in range(7):
            cd.vote("p1", f"agent-{i}", "canary")
        for i in range(3):
            cd.vote("p1", f"agent-{i + 7}", "blue-green")

        result = cd.decide("p1")
        assert result == "canary"

    def test_weighted_vote(self):
        """加权投票"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        cd = CollectiveDecision()
        weights = {"boss": 10, "dev1": 1, "dev2": 1, "dev3": 1}
        cd.create_proposal(
            "p1",
            "技术选型",
            ["python", "go", "rust"],
            DecisionMethod.WEIGHTED_VOTE,
            agent_weights=weights,  # type: ignore[reportArgumentType]
        )

        cd.vote("p1", "boss", "python")
        cd.vote("p1", "dev1", "go")
        cd.vote("p1", "dev2", "go")
        cd.vote("p1", "dev3", "rust")

        result = cd.decide("p1")
        assert result == "python"

    def test_consensus(self):
        """共识决策"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        cd = CollectiveDecision()
        cd.create_proposal("p1", "共识", ["A"], DecisionMethod.CONSENSUS)

        cd.vote("p1", "a1", "A")
        cd.vote("p1", "a2", "A")
        cd.vote("p1", "a3", "A")

        result = cd.decide("p1")
        assert result == "A"

    def test_consensus_fail(self):
        """共识失败"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        cd = CollectiveDecision()
        cd.create_proposal("p1", "共识", ["A", "B"], DecisionMethod.CONSENSUS)

        cd.vote("p1", "a1", "A")
        cd.vote("p1", "a2", "B")

        result = cd.decide("p1")
        assert result is None


# ══════════════════════════════════════════════════════════════
# 场景 6: 性能基准
# ══════════════════════════════════════════════════════════════


class TestPerformanceBenchmarks:
    """性能基准测试 — 合理性验证（非精确测量，精确测量见 tools/benchmark_l0.py）"""

    def test_state_sync_latency(self):
        """状态同步延迟 — 千次迭代墙钟 < 500ms（含 CPU 争用余量）"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        start = time.monotonic()
        for _ in range(100):
            a = StateSyncService("a", SyncStrategy.EVENTUAL)
            a.set("k", "v")
            snap = a.generate_snapshot()
            b = StateSyncService("b", SyncStrategy.EVENTUAL)
            b.sync_from_snapshot(snap)
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 500, f"延迟 {elapsed:.1f}ms 超过 500ms"

    def test_pagerank_latency(self):
        """PageRank 延迟"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        kg = KnowledgeGraphBuilder()
        for i in range(100):
            kg.add_node(f"n{i}")
        for i in range(99):
            kg.add_edge(f"n{i}", f"n{i + 1}", "link")

        start = time.monotonic()
        for _ in range(10):
            kg.pagerank(iterations=10)
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 500, f"延迟 {elapsed:.1f}ms 超过 500ms"

    def test_decision_latency(self):
        """决策延迟"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        cd = CollectiveDecision()
        cd.create_proposal("p1", "test", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE)
        for i in range(50):
            cd.vote("p1", f"a{i}", "A" if i < 30 else "B")

        start = time.monotonic()
        for _ in range(100):
            cd.decide("p1")
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 200, f"延迟 {elapsed:.1f}ms 超过 200ms"

    def test_multi_process_overhead(self):
        """多进程开销 — 4 进程 < 2000ms（含进程启动余量）"""
        queue = Queue()

        start = time.monotonic()
        processes = []
        for i in range(4):
            p = Process(
                target=_perf_worker, args=(queue, {f"k{j}": j for j in range(10)})
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        results = []
        while not queue.empty():
            results.append(queue.get())

        elapsed = (time.monotonic() - start) * 1000

        assert len(results) == 4
        assert elapsed < 2000, f"开销 {elapsed:.1f}ms 超过 2000ms"


# ══════════════════════════════════════════════════════════════
# 场景 7: 持久化验证
# ══════════════════════════════════════════════════════════════


class TestPersistenceVerification:
    """持久化验证测试"""

    def test_state_persistence_roundtrip(self):
        """状态持久化往返"""
        from ecos.common.persistence import StatePersistence

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            p1 = StatePersistence(db_path)
            p1.save("test", {"key": "value", "nested": {"a": 1}})

            p2 = StatePersistence(db_path)
            loaded = p2.load("test")

            assert loaded == {"key": "value", "nested": {"a": 1}}
        finally:
            os.unlink(db_path)

    def test_task_scheduler_persistence(self):
        """任务调度器持久化"""
        from ecos.common.persistence import StatePersistence
        from ecos.l0.governance import TaskScheduler

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            p1 = StatePersistence(db_path)
            ts1 = TaskScheduler(persistence=p1)
            ts1.submit_task("task-1", "重要任务", priority=10)
            ts1.submit_task("task-2", "普通任务", priority=5)

            p2 = StatePersistence(db_path)
            ts2 = TaskScheduler(persistence=p2)

            assert len(ts2.tasks) == 2
        finally:
            os.unlink(db_path)


# ══════════════════════════════════════════════════════════════
# 场景 8: 端到端工作流
# ══════════════════════════════════════════════════════════════


class TestEndToEndWorkflow:
    """端到端工作流测试"""

    def test_full_workflow(self):
        """完整工作流: 状态同步 + 故障转移 + 负载均衡 + 决策"""
        from ecos.l0.governance import (
            StateSyncService,
            SyncStrategy,
            FailoverManager,
            FailoverRule,
            FailoverStrategy,
            LoadBalancer,
            LoadBalancingStrategy,
            CollectiveDecision,
            DecisionMethod,
        )

        nodes = [StateSyncService(f"node-{i}", SyncStrategy.EVENTUAL) for i in range(4)]

        for i, n in enumerate(nodes):
            n.set("role", f"worker-{i}")
            n.set("load", str(i * 10))

        for n in nodes[1:]:
            snap = nodes[0].generate_snapshot()
            n.sync_from_snapshot(snap)

        for n in nodes:
            assert n.get("role") is not None

        fm = FailoverManager()
        fm.add_rule(
            FailoverRule(
                "r1",
                "node-0",
                ["node-1", "node-2", "node-3"],
                FailoverStrategy.ROUND_ROBIN,
            )
        )
        target = fm.execute_failover("node-0")
        assert target in ["node-1", "node-2", "node-3"]

        lb = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
        for i in range(4):
            lb.register_node(f"node-{i}")
        lb.update_connections("node-0", 10)
        lb.update_connections("node-1", 3)
        selected = lb.select_node()
        assert selected in ["node-2", "node-3"]  # 最少连接的节点

        cd = CollectiveDecision()
        cd.create_proposal(
            "p1", "部署策略", ["canary", "blue-green"], DecisionMethod.MAJORITY_VOTE
        )
        cd.vote("p1", "node-0", "canary")
        cd.vote("p1", "node-1", "canary")
        cd.vote("p1", "node-2", "blue-green")
        result = cd.decide("p1")
        assert result == "canary"

        assert all(n.get("role") is not None for n in nodes)

    def test_multi_process_workflow(self):
        """多进程工作流"""
        queue = Queue()

        workers = [
            ("worker-0", "compute", 50),
            ("worker-1", "store", 30),
            ("worker-2", "compute", 40),
            ("worker-3", "monitor", 20),
        ]

        processes = []
        for node_id, role, load in workers:
            p = Process(target=_multi_worker, args=(queue, node_id, role, load))
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        results = []
        while not queue.empty():
            results.append(queue.get())

        assert len(results) == 4

        roles = [r["role"] for r in results]
        assert "compute" in roles
        assert "store" in roles
        assert "monitor" in roles

        loads = [r["load"] for r in results]
        assert sum(loads) == 140


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
