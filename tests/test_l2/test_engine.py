"""L2 引擎面测试"""

from ecos.l2.engine import (
    CollaborationEngine,
    SwarmEngine,
    PersonalEngine,
    EngineConfig,
    EngineStatus,
    TaskStage,
)


class TestCollaborationEngine:
    """协作引擎测试"""

    def test_start_stop(self):
        config = EngineConfig(engine_id="engine-1")
        engine = CollaborationEngine(config)

        assert engine.start()
        assert engine.status == EngineStatus.RUNNING

        assert engine.stop()
        assert engine.status == EngineStatus.STOPPED

    def test_submit_task(self):
        config = EngineConfig(engine_id="engine-1")
        engine = CollaborationEngine(config)
        engine.start()

        task = engine.submit_task("task-1", "测试任务")
        assert task.task_id == "task-1"
        assert task.stage == TaskStage.PENDING
        status = engine.get_task_status("task-1")
        assert status is not None
        assert status["task_id"] == "task-1"

    def test_auto_assign(self):
        config = EngineConfig(engine_id="engine-1")
        engine = CollaborationEngine(config)
        engine.start()

        engine.register_agent("agent-1", ["compute", "task"])
        engine.submit_task("task-1", "任务1", required_capabilities=["task"])

        assignments = engine.auto_assign()
        assert len(assignments) == 1
        assert assignments[0][0] == "task-1"
        assert assignments[0][1] == "agent-1"

    def test_task_lifecycle(self):
        config = EngineConfig(engine_id="engine-1")
        engine = CollaborationEngine(config)
        engine.start()

        engine.register_agent("a1", ["work"])
        engine.submit_task("t1", "任务")
        engine.auto_assign()
        engine.start_task("t1")
        engine.complete_task("t1", result="done")

        status = engine.get_task_status("t1")
        assert status["stage"] == TaskStage.DONE.value  # type: ignore[reportOptionalSubscript]

    def test_task_retry(self):
        config = EngineConfig(engine_id="e1", retry_count=2)
        engine = CollaborationEngine(config)
        engine.start()

        engine.register_agent("a1", [])
        engine.submit_task("t1", "任务")
        engine.auto_assign()
        engine.start_task("t1")

        engine.fail_task("t1", "error")
        status = engine.get_task_status("t1")
        assert status["stage"] == TaskStage.PENDING.value  # type: ignore[reportOptionalSubscript]

    def test_dependency(self):
        config = EngineConfig(engine_id="e1")
        engine = CollaborationEngine(config)
        engine.start()

        engine.register_agent("a1", [])
        engine.submit_task("t1", "前置")
        engine.submit_task("t2", "后续")
        engine.set_dependency("t2", "t1")

        assignments = engine.auto_assign()
        assigned_ids = [a[0] for a in assignments]
        assert "t1" in assigned_ids
        assert "t2" not in assigned_ids

    def test_pipeline_status(self):
        config = EngineConfig(engine_id="e1")
        engine = CollaborationEngine(config)
        engine.start()
        engine.submit_task("t1", "任务")

        status = engine.get_pipeline_status()
        assert status["total_tasks"] == 1
        assert status["engine_status"] == "running"


class TestSwarmEngine:
    """蜂群引擎测试"""

    def test_start_stop(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)

        assert engine.start()
        assert engine.status == EngineStatus.RUNNING

        assert engine.stop()
        assert engine.status == EngineStatus.STOPPED

    def test_register_agent(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()

        assert engine.register_agent("agent-1")
        status = engine.get_swarm_status()
        assert status["agent_count"] == 1

    def test_detect_emergence(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()

        for i in range(3):
            engine.register_agent(f"agent-{i + 1}")

        emergence = engine.detect_emergence()
        assert len(emergence) >= 1
        assert emergence[0]["pattern"] == "clustering"

    def test_collective_decision(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()

        engine.register_agent("a1")
        engine.register_agent("a2")
        engine.register_agent("a3")

        engine.propose_decision("p1", "选择方案", ["A", "B"])
        engine.vote("p1", "a1", "A")
        engine.vote("p1", "a2", "A")
        engine.vote("p1", "a3", "B")

        result = engine.resolve_decision("p1")
        assert result == "A"

    def test_consensus_decision(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()

        engine.propose_decision("p1", "共识决策", ["X"], method="consensus")
        engine.vote("p1", "a1", "X")
        engine.vote("p1", "a2", "X")

        result = engine.resolve_decision("p1")
        assert result == "X"

    def test_swarm_status(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()
        engine.register_agent("a1")

        status = engine.get_swarm_status()
        assert status["agent_count"] == 1
        assert status["engine_status"] == "running"


class TestPersonalEngine:
    """个人知识引擎测试"""

    def test_start_stop(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)

        assert engine.start()
        assert engine.status == EngineStatus.RUNNING

        assert engine.stop()
        assert engine.status == EngineStatus.STOPPED

    def test_add_and_query_knowledge(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)
        engine.start()

        assert engine.add_knowledge("AI", {"desc": "artificial intelligence"})
        assert engine.add_knowledge("ML", {"desc": "machine learning"})

        results = engine.query_knowledge("AI")
        assert len(results) == 1
        assert results[0]["key"] == "AI"

    def test_knowledge_relations(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)
        engine.start()

        engine.add_knowledge("k1", {"desc": "A"}, relations=["k2"])
        engine.add_knowledge("k2", {"desc": "B"})

        related = engine.get_related_knowledge("k1")
        related_keys = [r if isinstance(r, str) else r.node_id for r in related]
        assert "k2" in related_keys

    def test_preference_and_recommendation(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)
        engine.start()

        engine.add_knowledge("AI", {"desc": "artificial intelligence"})
        engine.add_knowledge("Cooking", {"desc": "cooking"})

        engine.learn_preference("user-1", "artificial", 1.0)
        recs = engine.get_recommendations("user-1")
        assert len(recs) >= 1

    def test_access_tracking(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)
        engine.start()

        engine.add_knowledge("k1", {"desc": "test"})
        engine.record_access("k1")
        stats = engine.get_stats()
        assert stats["knowledge_count"] == 1

    def test_stats(self):
        config = EngineConfig(engine_id="personal-1")
        engine = PersonalEngine(config)
        engine.start()
        engine.add_knowledge("k1", {"desc": "test"})

        stats = engine.get_stats()
        assert stats["knowledge_count"] == 1
