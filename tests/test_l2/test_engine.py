"""L2 引擎面测试"""

from ecos.l2.engine import (
    CollaborationEngine,
    SwarmEngine,
    PersonalEngine,
    EngineConfig,
    EngineStatus,
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
        
        result = engine.submit_task("task-1", {"name": "测试任务"})
        assert result is True
        assert "task-1" in engine.tasks


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
        assert "agent-1" in engine.agents
    
    def test_detect_emergence(self):
        config = EngineConfig(engine_id="swarm-1")
        engine = SwarmEngine(config)
        engine.start()
        
        # 注册 3 个 Agent
        for i in range(3):
            engine.register_agent(f"agent-{i+1}")
        
        emergence = engine.detect_emergence()
        assert len(emergence) == 1
        assert emergence[0]["pattern"] == "clustering"


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
        
        assert engine.add_knowledge("AI", "人工智能")
        assert engine.add_knowledge("ML", "机器学习")
        
        results = engine.query_knowledge("AI")
        assert len(results) == 1
        assert results[0]["key"] == "AI"
