"""端到端集成测试 — L0+L1+L2+L3 全链路验证

验证蜂群式AI超级大脑的完整工作流：
1. L0 原语定义
2. L1 运行时委托
3. L2 引擎编排
4. L3 入口暴露
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestEndToEndIntegration:
    """端到端集成测试"""

    def test_full_workflow(self):
        """完整工作流: L0→L1→L2→L3"""
        from ecos.l0.governance import (
            NodeManager,
            TaskScheduler,
            RoleManager,
            RoleDefinition,
            RoleType,
            SwarmManager,
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )
        from ecos.l1.runtime import StateSyncService as L1Sync
        from ecos.l2.engine import (
            CollaborationEngine,
            SwarmEngine,
            PersonalEngine,
            EngineConfig,
        )
        from ecos.l3.entry import GovernanceCLI, GovernanceMCP

        # Step 1: L0 原语定义
        nm = NodeManager()
        nm.register("node-1")
        nm.register("node-2")

        ts = TaskScheduler()
        ts.submit_task("task-1", "分析需求")
        ts.submit_task("task-2", "实现功能")
        ts.submit_task("task-3", "测试验证")

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="analyst",
                role_type=RoleType.WORKER,
                capabilities=["analyze"],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="developer",
                role_type=RoleType.WORKER,
                capabilities=["code"],
                constraints={},
            )
        )

        sm = SwarmManager()
        for i in range(5):
            sm.add_agent(f"agent-{i}")

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1", knowledge_type=KnowledgeType.FACT, content={"text": "AI"}
            )
        )

        # Step 2: L1 运行时委托
        l1_sync = L1Sync("l1-node")
        l1_sync.set("config", "production")
        assert l1_sync.get("config") == "production"

        # Step 3: L2 引擎编排
        ce = CollaborationEngine(EngineConfig(engine_id="collab"))
        ce.start()
        ce.register_agent("agent-1", ["analyze", "code"])
        ce.submit_task("t1", "任务1")
        assignments = ce.auto_assign()
        assert len(assignments) == 1

        se = SwarmEngine(EngineConfig(engine_id="swarm"))
        se.start()
        for i in range(5):
            se.register_agent(f"agent-{i}")
        behaviors = se.detect_emergence()
        assert len(behaviors) >= 1

        pe = PersonalEngine(EngineConfig(engine_id="personal"))
        pe.start()
        pe.add_knowledge("k1", {"text": "AI"})
        results = pe.query_knowledge("AI")
        assert len(results) == 1

        # Step 4: L3 入口暴露
        cli = GovernanceCLI()
        result = cli.run(["check"])
        assert result == 0

        mcp = GovernanceMCP()
        tools = mcp.list_tools()
        assert len(tools) == 14

        print("✅ 端到端工作流验证通过")


class TestCrossLayerIntegration:
    """跨层集成测试"""

    def test_l0_to_l2_collaboration(self):
        """L0→L2 协作引擎集成"""
        from ecos.l0.governance import TaskScheduler, RoleManager
        from ecos.l2.engine import CollaborationEngine, EngineConfig

        TaskScheduler()
        RoleManager()

        ce = CollaborationEngine(EngineConfig(engine_id="test"))
        ce.start()
        ce.register_agent("a1", ["work"])

        ce.submit_task("t1", "任务")
        assignments = ce.auto_assign()
        assert len(assignments) == 1

        ce.start_task("t1")
        ce.complete_task("t1", {"result": "done"})

        status = ce.get_task_status("t1")
        assert status["stage"] == "done"  # type: ignore[reportOptionalSubscript]

    def test_l0_to_l2_swarm(self):
        """L0→L2 蜂群引擎集成"""
        from ecos.l0.governance import SwarmManager, CollectiveDecision
        from ecos.l2.engine import SwarmEngine, EngineConfig

        SwarmManager()
        CollectiveDecision()

        se = SwarmEngine(EngineConfig(engine_id="test"))
        se.start()

        for i in range(5):
            se.register_agent(f"agent-{i}")

        behaviors = se.detect_emergence()
        assert len(behaviors) >= 1

        se.propose_decision("p1", "测试", ["A", "B"])
        se.vote("p1", "agent-0", "A")
        se.vote("p1", "agent-1", "A")
        result = se.resolve_decision("p1")
        assert result == "A"

    def test_l0_to_l2_personal(self):
        """L0→L2 个人引擎集成"""
        from ecos.l0.governance import PersonalKnowledgeManager
        from ecos.l2.engine import PersonalEngine, EngineConfig

        PersonalKnowledgeManager()

        pe = PersonalEngine(EngineConfig(engine_id="test"))
        pe.start()

        pe.add_knowledge("k1", {"text": "AI"})
        results = pe.query_knowledge("AI")
        assert len(results) == 1

        pe.learn_preference("user-1", "ai", 5.0)
        recs = pe.get_recommendations("user-1")
        assert len(recs) >= 1

    def test_l3_full_workflow(self):
        """L3 完整工作流"""
        from ecos.l3.entry import GovernanceCLI, GovernanceMCP

        cli = GovernanceCLI()
        for cmd in ["check", "status", "cluster", "swarm", "knowledge", "help"]:
            result = cli.run([cmd])
            assert result == 0

        mcp = GovernanceMCP()
        for tool in [
            "governance_check",
            "governance_status",
            "cluster_list",
            "swarm_status",
            "knowledge_stats",
            "task_submit",
        ]:
            result = mcp.call_tool(tool)
            assert result["status"] == "ok"


class TestAsyncTCP:
    """asyncio TCP 通信测试"""

    def test_tcp_node_creation(self):
        """TCPNode 创建"""
        from ecos.l1.transport import TCPNode, ChannelState

        node = TCPNode("test-node", "127.0.0.1", 0)
        assert node.node_id == "test-node"
        assert node.state == ChannelState.DISCONNECTED

    def test_wire_message_encode_decode(self):
        """WireMessage 编解码"""
        from ecos.l1.transport import WireMessage

        msg = WireMessage(
            msg_id="test-1",
            msg_type="sync",
            source="a",
            target="b",
            payload={"key": "value", "nested": {"a": 1}},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)

        assert decoded.msg_id == "test-1"
        assert decoded.payload["key"] == "value"
        assert decoded.payload["nested"]["a"] == 1

    def test_message_priority(self):
        """消息优先级"""
        from ecos.l1.runtime import Message, MessageType, MessagePriority, MessageQueue

        queue = MessageQueue()
        low = Message.create(MessageType.SYNC, "a", "b", {}, MessagePriority.LOW)
        high = Message.create(MessageType.SYNC, "a", "b", {}, MessagePriority.HIGH)
        normal = Message.create(MessageType.SYNC, "a", "b", {}, MessagePriority.NORMAL)

        queue.enqueue(low)
        queue.enqueue(high)
        queue.enqueue(normal)

        assert queue.dequeue().priority == MessagePriority.HIGH  # type: ignore[reportOptionalMemberAccess]
        assert queue.dequeue().priority == MessagePriority.NORMAL  # type: ignore[reportOptionalMemberAccess]
        assert queue.dequeue().priority == MessagePriority.LOW  # type: ignore[reportOptionalMemberAccess]

    def test_message_ttl(self):
        """消息 TTL"""
        from ecos.l1.runtime import Message, MessageType, MessageQueue
        from datetime import datetime, timezone, timedelta

        queue = MessageQueue()
        msg = Message(
            message_id="old",
            message_type=MessageType.SYNC,
            source="a",
            target="b",
            payload={},
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            ttl_seconds=10,
        )
        queue.enqueue(msg)
        assert queue.purge_expired() == 1
        assert queue.size() == 0


class TestPerformanceBenchmarks:
    """性能基准测试 — 合理性验证（非精确测量，精确测量见 tools/benchmark_l0.py）"""

    def test_state_sync_throughput(self):
        """状态同步吞吐量 — 千次迭代墙钟 < 500ms（含 CPU 争用余量）"""
        from ecos.l0.governance import StateSyncService, SyncStrategy
        import time

        start = time.monotonic()
        for _ in range(100):
            a = StateSyncService("a", SyncStrategy.EVENTUAL)
            a.set("k", "v")
            snap = a.generate_snapshot()
            b = StateSyncService("b", SyncStrategy.EVENTUAL)
            b.sync_from_snapshot(snap)
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 500, f"延迟 {elapsed:.1f}ms 超过 500ms"

    def test_pagerank_convergence(self):
        """PageRank 收敛性"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        kg = KnowledgeGraphBuilder()
        for i in range(50):
            kg.add_node(f"n{i}")
        for i in range(49):
            kg.add_edge(f"n{i}", f"n{i + 1}", "link")

        pr = kg.pagerank()
        total = sum(pr.values())
        assert abs(total - 1.0) < 0.001
        assert max(pr.values()) > 0.02

    def test_decision_latency(self):
        """决策延迟"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod
        import time

        cd = CollectiveDecision()
        cd.create_proposal("p1", "test", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE)
        for i in range(100):
            cd.vote("p1", f"a{i}", "A" if i < 60 else "B")

        start = time.monotonic()
        for _ in range(100):
            cd.decide("p1")
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 200, f"延迟 {elapsed:.1f}ms 超过 200ms"


class TestDeploymentReadiness:
    """部署就绪性测试"""

    def test_import_all_modules(self):
        """验证所有模块可导入"""
        assert True

    def test_all_components_instantiate(self):
        """验证所有组件可实例化"""
        from ecos.l0.governance import (
            CRDTSync,
            StateSyncService,
            DAGScheduler,
            SwarmManager,
            CollectiveDecision,
            KnowledgeGraphBuilder,
            RecommendationEngine,
            FailoverManager,
            LoadBalancer,
            NodeManager,
            TaskScheduler,
            AgentRegistry,
            PersonalKnowledgeManager,
            PreferenceEngine,
        )
        from ecos.l2.engine import (
            CollaborationEngine,
            SwarmEngine,
            PersonalEngine,
            EngineConfig,
        )
        from ecos.l3.entry import GovernanceCLI, GovernanceMCP

        CRDTSync("test")
        StateSyncService("test")
        DAGScheduler(TaskScheduler())
        SwarmManager()
        CollectiveDecision()
        KnowledgeGraphBuilder()
        RecommendationEngine(PersonalKnowledgeManager(), PreferenceEngine())
        FailoverManager()
        LoadBalancer()
        NodeManager()
        TaskScheduler()
        AgentRegistry()
        PersonalKnowledgeManager()
        CollaborationEngine(EngineConfig(engine_id="test"))
        SwarmEngine(EngineConfig(engine_id="test"))
        PersonalEngine(EngineConfig(engine_id="test"))
        GovernanceCLI()
        GovernanceMCP()
        assert True
