"""L0 治理模块测试"""

from datetime import datetime, timezone

from ecos.l0.governance import (
    CheckResult,
    CheckSeverity,
    CheckStatus,
    GovernanceEvent,
    GovernanceEventBus,
    X1AuditChainChecker,
    X2StalenessChecker,
    X3ValueChecker,
    X4ConsistencyChecker,
    AlertSeverity,
    AlertChannel,
    GovernanceAlert,
    AlertRule,
    AlertEngine,
    LogHandler,
    HealthSnapshot,
    TrendAnalysis,
    Prediction,
    SQLiteHistoryStore,
    GovernanceRegistry,
)


class TestCheckResult:
    """CheckResult 测试"""
    
    def test_create_check_result(self):
        result = CheckResult(
            check_id="test-check",
            dimension="X1",
            status=CheckStatus.PASS,
            message="测试通过",
        )
        assert result.check_id == "test-check"
        assert result.dimension == "X1"
        assert result.status == CheckStatus.PASS
    
    def test_to_dict(self):
        result = CheckResult(
            check_id="test-check",
            dimension="X2",
            status=CheckStatus.WARN,
            message="测试警告",
            severity=CheckSeverity.HIGH,
        )
        d = result.to_dict()
        assert d["check_id"] == "test-check"
        assert d["dimension"] == "X2"
        assert d["status"] == "warn"
        assert d["severity"] == "high"
        assert "timestamp" in d


class TestGovernanceEvent:
    """GovernanceEvent 测试"""
    
    def test_create_event(self):
        event = GovernanceEvent(
            event_type="check_started",
            dimension="X1",
            check_id="test-check",
        )
        assert event.event_type == "check_started"
        assert event.dimension == "X1"
    
    def test_to_dict(self):
        event = GovernanceEvent(
            event_type="check_completed",
            dimension="X3",
            check_id="test-check",
        )
        d = event.to_dict()
        assert d["event_type"] == "check_completed"
        assert d["dimension"] == "X3"


class TestGovernanceEventBus:
    """GovernanceEventBus 测试"""
    
    def test_subscribe_and_publish(self):
        bus = GovernanceEventBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe("test_event", handler)
        
        event = GovernanceEvent(
            event_type="test_event",
            dimension="X1",
            check_id="test",
        )
        bus.publish(event)
        
        assert len(received) == 1
        assert received[0] == event
    
    def test_emit_check_started(self):
        bus = GovernanceEventBus()
        received = []
        bus.subscribe("check_started", lambda e: received.append(e))
        
        bus.emit_check_started("x1-test", "X1")
        assert len(received) == 1


class TestX1AuditChainChecker:
    """X1 审计链检查器测试"""
    
    def test_execute(self, tmp_path):
        # 创建必要的文件结构
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "debt-audit.sh").touch()
        (tmp_path / "debt-audit-report.md").touch()
        
        for proj in ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]:
            (tmp_path / "projects" / proj / ".githooks").mkdir(parents=True)
            (tmp_path / "projects" / proj / ".githooks" / "pre-commit").touch()
        
        checker = X1AuditChainChecker(tmp_path)
        result = checker.execute()
        
        assert result.dimension == "X1"
        assert result.status in [CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL]
    
    def test_get_description(self, tmp_path):
        checker = X1AuditChainChecker(tmp_path)
        desc = checker.get_description()
        assert "审计" in desc or "安全" in desc


class TestX2StalenessChecker:
    """X2 抗熵检查器测试"""
    
    def test_execute(self, tmp_path):
        # 创建 system.yaml
        omo_dir = tmp_path / ".omo" / "state"
        omo_dir.mkdir(parents=True)
        (omo_dir / "system.yaml").write_text("debt_weight: 1.0\ndebt_metrics:\n  debt_health: 100.0\n")
        
        checker = X2StalenessChecker(tmp_path)
        result = checker.execute()
        
        assert result.dimension == "X2"
        assert result.status in [CheckStatus.PASS, CheckStatus.FAIL]


class TestX3ValueChecker:
    """X3 价值栈检查器测试"""
    
    def test_execute(self, tmp_path):
        # 创建 sla.md
        gov_dir = tmp_path / ".omo" / "_knowledge" / "governance"
        gov_dir.mkdir(parents=True)
        (gov_dir / "sla.md").write_text("# SLA\n")
        
        checker = X3ValueChecker(tmp_path)
        result = checker.execute()
        
        assert result.dimension == "X3"
        assert result.status in [CheckStatus.PASS, CheckStatus.WARN]


class TestX4ConsistencyChecker:
    """X4 一致性检查器测试"""
    
    def test_execute(self, tmp_path):
        # 创建 CI 和 githooks
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        for i in range(5):
            (tmp_path / ".github" / "workflows" / f"ci-{i}.yml").touch()
        
        for proj in ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]:
            (tmp_path / "projects" / proj / ".githooks").mkdir(parents=True)
        
        checker = X4ConsistencyChecker(tmp_path)
        result = checker.execute()
        
        assert result.dimension == "X4"
        assert result.status == CheckStatus.PASS


# ══════════════════════════════════════════════════════════════
# 优化原语测试
# ══════════════════════════════════════════════════════════════

class TestGovernanceAlert:
    """GovernanceAlert 测试"""
    
    def test_create_alert(self):
        alert = GovernanceAlert(
            alert_id="alert-001",
            severity=AlertSeverity.HIGH,
            dimension="X1",
            check_id="x1-check",
            message="测试告警",
        )
        assert alert.alert_id == "alert-001"
        assert alert.severity == AlertSeverity.HIGH
    
    def test_to_dict(self):
        alert = GovernanceAlert(
            alert_id="alert-001",
            severity=AlertSeverity.CRITICAL,
            dimension="X2",
            check_id="x2-check",
            message="测试告警",
            channels=[AlertChannel.LOG, AlertChannel.WEBHOOK],
        )
        d = alert.to_dict()
        assert d["severity"] == "critical"
        assert "log" in d["channels"]


class TestAlertEngine:
    """AlertEngine 测试"""
    
    def test_evaluate_fail(self):
        engine = AlertEngine()
        engine.rules = [
            AlertRule(
                rule_id="test-rule",
                dimension="X1",
                condition="fail",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG],
            )
        ]
        
        result = CheckResult(
            check_id="x1-test",
            dimension="X1",
            status=CheckStatus.FAIL,
            message="测试失败",
        )
        
        alerts = engine.evaluate([result])
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH
    
    def test_evaluate_pass_no_alert(self):
        engine = AlertEngine()
        engine.rules = [
            AlertRule(
                rule_id="test-rule",
                dimension="X1",
                condition="fail",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG],
            )
        ]
        
        result = CheckResult(
            check_id="x1-test",
            dimension="X1",
            status=CheckStatus.PASS,
            message="测试通过",
        )
        
        alerts = engine.evaluate([result])
        assert len(alerts) == 0


class TestLogHandler:
    """LogHandler 测试"""
    
    def test_handle(self, tmp_path):
        log_path = tmp_path / "test.log"
        handler = LogHandler(log_path)
        
        alert = GovernanceAlert(
            alert_id="alert-001",
            severity=AlertSeverity.HIGH,
            dimension="X1",
            check_id="x1-test",
            message="测试告警",
        )
        
        success = handler.handle(alert)
        assert success
        assert log_path.exists()


class TestHealthSnapshot:
    """HealthSnapshot 测试"""
    
    def test_create_snapshot(self):
        snapshot = HealthSnapshot(
            timestamp=datetime.now(timezone.utc),
            health_score=82.0,
            debt_weight=1.0,
            debt_health=100.0,
            resolved_count=9,
            unresolved_count=0,
        )
        assert snapshot.health_score == 82.0
        assert snapshot.resolved_count == 9
    
    def test_to_dict(self):
        snapshot = HealthSnapshot(
            timestamp=datetime.now(timezone.utc),
            health_score=82.0,
            debt_weight=1.0,
            debt_health=100.0,
            resolved_count=9,
            unresolved_count=0,
        )
        d = snapshot.to_dict()
        assert d["health_score"] == 82.0
        assert "timestamp" in d


class TestSQLiteHistoryStore:
    """SQLiteHistoryStore 测试"""
    
    def test_record_and_query(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = SQLiteHistoryStore(db_path)
        
        snapshot = HealthSnapshot(
            timestamp=datetime.now(timezone.utc),
            health_score=82.0,
            debt_weight=1.0,
            debt_health=100.0,
            resolved_count=9,
            unresolved_count=0,
        )
        
        store.record(snapshot)
        snapshots = store.get_snapshots(days=1)
        
        assert len(snapshots) == 1
        assert snapshots[0].health_score == 82.0
    
    def test_analyze_trend(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = SQLiteHistoryStore(db_path)
        
        # 记录多个快照
        for i in range(5):
            snapshot = HealthSnapshot(
                timestamp=datetime.now(timezone.utc),
                health_score=70.0 + i * 5,
                debt_weight=0.8 + i * 0.05,
                debt_health=80.0 + i * 5,
                resolved_count=9,
                unresolved_count=0,
            )
            store.record(snapshot)
        
        trend = store.analyze_trend("health_score", days=1)
        assert trend.metric == "health_score"
        assert trend.trend == "improving"


class TestTrendAnalysis:
    """TrendAnalysis 测试"""
    
    def test_create_trend(self):
        trend = TrendAnalysis(
            metric="health_score",
            current=82.0,
            previous=75.0,
            change=7.0,
            trend="improving",
        )
        assert trend.trend == "improving"
    
    def test_to_dict(self):
        trend = TrendAnalysis(
            metric="health_score",
            current=82.0,
            previous=75.0,
            change=7.0,
            trend="improving",
        )
        d = trend.to_dict()
        assert d["trend"] == "improving"


class TestPrediction:
    """Prediction 测试"""
    
    def test_create_prediction(self):
        pred = Prediction(
            metric="health_score",
            days=7,
            predicted_value=90.0,
        )
        assert pred.days == 7
    
    def test_to_dict(self):
        pred = Prediction(
            metric="health_score",
            days=7,
            predicted_value=90.0,
        )
        d = pred.to_dict()
        assert d["predicted_value"] == 90.0


class TestGovernanceRegistry:
    """GovernanceRegistry 测试"""
    
    def test_load_and_run(self, tmp_path):
        # 创建注册表文件
        registry_yaml = tmp_path / "registry.yaml"
        registry_yaml.write_text("""
checkers:
  - id: x1-test
    dimension: X1
    name: "测试检查器"
    description: "测试"
    module: "ecos.l0.governance.checkers"
    class: "X1AuditChainChecker"
    enabled: true
""")
        
        # 创建必要的文件结构
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "debt-audit.sh").touch()
        (tmp_path / "debt-audit-report.md").touch()
        for proj in ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]:
            (tmp_path / "projects" / proj / ".githooks").mkdir(parents=True)
            (tmp_path / "projects" / proj / ".githooks" / "pre-commit").touch()
        
        registry = GovernanceRegistry(registry_yaml)
        registry.load()
        
        assert len(registry.checkers) == 1
        assert registry.checkers[0].id == "x1-test"
        
        results = registry.run_all(tmp_path)
        assert len(results) == 1


# ══════════════════════════════════════════════════════════════
# 蜂群式AI超级大脑原语测试
# ══════════════════════════════════════════════════════════════

class TestDistributedPrimitive:
    """分布式原语测试"""
    
    def test_crdt_sync(self):
        from ecos.l0.governance import CRDTSync, StateSnapshot
        
        sync = CRDTSync("node-1")
        snapshot = StateSnapshot(
            node_id="node-2",
            version=1,
            data={"key": "value"},
        )
        
        result = sync.sync(snapshot)
        assert result.success
        assert result.merged_version == 2  # 版本递增
    
    def test_crdt_merge(self):
        from ecos.l0.governance import CRDTSync, StateSnapshot
        
        sync = CRDTSync("node-1")
        local = StateSnapshot(node_id="node-1", version=1, data={"a": 1})
        remote = StateSnapshot(node_id="node-2", version=1, data={"b": 2})
        
        merged = sync.merge(local, remote)
        assert merged.version == 2
        # LWW: remote 时间戳更新（默认），所以 remote 获胜
        assert "b" in merged.data
    
    def test_crdt_sync_lww(self):
        """测试 LWW-Register 冲突解决"""
        from ecos.l0.governance import CRDTSync, StateSnapshot
        from datetime import datetime, timezone, timedelta
        
        sync = CRDTSync("node-1")
        
        # 创建两个有冲突的快照
        local_time = datetime.now(timezone.utc)
        remote_time = local_time + timedelta(seconds=10)
        
        local = StateSnapshot(
            node_id="node-1",
            version=1,
            data={"key": "local_value"},
            timestamp=local_time,
        )
        remote = StateSnapshot(
            node_id="node-2",
            version=1,
            data={"key": "remote_value"},
            timestamp=remote_time,
        )
        
        # LWW: remote 时间戳更新，应该获胜
        merged = sync.merge(local, remote)
        assert merged.data["key"] == "remote_value"
    
    def test_node_manager(self):
        """测试节点管理器"""
        from ecos.l0.governance import NodeManager, NodeStatus
        
        manager = NodeManager()
        
        # 注册节点
        node = manager.register("node-1", {"role": "worker"})
        assert node.node_id == "node-1"
        assert node.status == NodeStatus.ONLINE
        
        # 获取节点
        retrieved = manager.get_node("node-1")
        assert retrieved is not None
        assert retrieved.node_id == "node-1"
        
        # 更新心跳
        assert manager.update_heartbeat("node-1")
        
        # 获取在线节点
        online = manager.get_online_nodes()
        assert len(online) == 1
        
        # 注销节点
        assert manager.unregister("node-1")
        assert manager.get_node("node-1") is None
    
    def test_node_health_check(self):
        """测试节点健康检查"""
        from ecos.l0.governance import NodeManager, NodeStatus
        
        manager = NodeManager()
        manager.heartbeat_interval = 1  # 1 秒
        
        # 注册节点
        manager.register("node-1")
        
        # 立即检查应该是健康
        health = manager.check_health()
        assert health["node-1"] == NodeStatus.HEALTHY


class TestAgentRegistry:
    """Agent 注册中心测试"""
    
    def test_register_agent(self):
        """测试注册 Agent"""
        from ecos.l0.governance import AgentRegistry, AgentStatus
        
        registry = AgentRegistry()
        agent = registry.register("agent-1", "worker-1", ["task", "compute"])
        
        assert agent.agent_id == "agent-1"
        assert agent.name == "worker-1"
        assert agent.status == AgentStatus.IDLE
        assert "task" in agent.capabilities
    
    def test_discover_agents(self):
        """测试发现 Agent"""
        from ecos.l0.governance import AgentRegistry, AgentStatus
        
        registry = AgentRegistry()
        registry.register("agent-1", "worker-1", ["task", "compute"])
        registry.register("agent-2", "worker-2", ["compute"])
        
        # 按能力查找
        agents = registry.discover_agents("task")
        assert len(agents) == 1
        assert agents[0].agent_id == "agent-1"
        
        # 按状态查找
        registry.update_status("agent-1", AgentStatus.BUSY)
        idle_agents = registry.get_idle_agents()
        assert len(idle_agents) == 1
        assert idle_agents[0].agent_id == "agent-2"


class TestTaskScheduler:
    """任务调度器测试"""
    
    def test_submit_and_assign(self):
        """测试提交和分配任务"""
        from ecos.l0.governance import TaskScheduler, TaskStatus
        
        scheduler = TaskScheduler()
        
        # 提交任务
        task = scheduler.submit_task("task-1", "测试任务", required_capabilities=["task"])
        assert task.task_id == "task-1"
        assert task.status == TaskStatus.PENDING
        
        # 分配任务
        assert scheduler.assign_task("task-1", "agent-1")
        assert task.status == TaskStatus.ASSIGNED
        assert task.assigned_agent == "agent-1"
    
    def test_task_lifecycle(self):
        """测试任务生命周期"""
        from ecos.l0.governance import TaskScheduler, TaskStatus
        
        scheduler = TaskScheduler()
        
        # 提交
        task = scheduler.submit_task("task-1", "测试任务")
        assert task.status == TaskStatus.PENDING
        
        # 分配
        scheduler.assign_task("task-1", "agent-1")
        assert task.status == TaskStatus.ASSIGNED
        
        # 开始
        scheduler.start_task("task-1")
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        
        # 完成
        scheduler.complete_task("task-1", result={"output": "done"})
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.result == {"output": "done"}
    
    def test_task_priority(self):
        """测试任务优先级"""
        from ecos.l0.governance import TaskScheduler, TaskStatus
        
        scheduler = TaskScheduler()
        
        # 提交不同优先级的任务
        scheduler.submit_task("task-1", "低优先级", priority=1)
        scheduler.submit_task("task-2", "高优先级", priority=10)
        scheduler.submit_task("task-3", "中优先级", priority=5)
        
        # 获取下一个任务应该是高优先级
        next_task = scheduler.get_next_task()
        assert next_task is not None
        assert next_task.task_id == "task-2"
        assert next_task.priority == 10


class TestFailoverManager:
    """故障转移管理器测试"""
    
    def test_add_rule(self):
        """测试添加规则"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy
        
        manager = FailoverManager()
        rule = FailoverRule(
            rule_id="rule-1",
            source_node="node-1",
            target_nodes=["node-2", "node-3"],
            strategy=FailoverStrategy.ROUND_ROBIN,
        )
        
        manager.add_rule(rule)
        assert manager.get_rule("rule-1") is not None
    
    def test_execute_failover(self):
        """测试执行故障转移"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy
        
        manager = FailoverManager()
        rule = FailoverRule(
            rule_id="rule-1",
            source_node="node-1",
            target_nodes=["node-2", "node-3"],
            strategy=FailoverStrategy.ROUND_ROBIN,
        )
        manager.add_rule(rule)
        
        # 执行故障转移
        target = manager.execute_failover("node-1")
        assert target in ["node-2", "node-3"]


class TestLoadBalancer:
    """负载均衡器测试"""
    
    def test_register_and_select(self):
        """测试注册和选择节点"""
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy
        
        balancer = LoadBalancer(LoadBalancingStrategy.ROUND_ROBIN)
        
        # 注册节点
        balancer.register_node("node-1", weight=1)
        balancer.register_node("node-2", weight=2)
        
        # 选择节点
        node = balancer.select_node()
        assert node in ["node-1", "node-2"]
    
    def test_least_connections(self):
        """测试最少连接策略"""
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy
        
        balancer = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
        
        balancer.register_node("node-1", weight=1)
        balancer.register_node("node-2", weight=1)
        
        # 设置连接数
        balancer.update_connections("node-1", 10)
        balancer.update_connections("node-2", 5)
        
        # 选择节点应该是 node-2 (连接数最少)
        node = balancer.select_node()
        assert node == "node-2"


class TestRolePrimitive:
    """角色原语测试"""
    
    def test_role_manager(self):
        from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
        
        manager = RoleManager()
        
        # 定义角色
        role = RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["task"],
            constraints={},
        )
        assert manager.define_role(role)
        
        # 分配角色
        assert manager.assign_role("agent-1", "worker")
        
        # 获取角色
        retrieved = manager.get_role("agent-1")
        assert retrieved is not None
        assert retrieved.role_id == "worker"
        
        # 列出角色
        roles = manager.list_roles()
        assert len(roles) == 1


class TestSwarmPrimitive:
    """蜂群原语测试"""
    
    def test_swarm_manager(self):
        from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern
        
        manager = SwarmManager()
        manager.agents = ["agent-1", "agent-2", "agent-3"]
        
        state = SwarmState(
            agents=manager.agents,
            behaviors=[],
        )
        
        # 检测涌现
        behaviors = manager.detect_emergence(state)
        assert len(behaviors) > 0
        assert behaviors[0].pattern == EmergencePattern.CLUSTERING


class TestPersonalKnowledgePrimitive:
    """个人知识原语测试"""
    
    def test_personal_knowledge_manager(self):
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            UserPreference,
            PreferenceType,
        )
        
        manager = PersonalKnowledgeManager()
        
        # 添加知识
        node = KnowledgeNode(
            node_id="k1",
            knowledge_type=KnowledgeType.FACT,
            content={"topic": "AI"},
        )
        assert manager.add_knowledge(node)
        
        # 查询知识
        results = manager.query_knowledge("AI")
        assert len(results) == 1
        
        # 学习偏好
        pref = UserPreference(
            user_id="user-1",
            preference_type=PreferenceType.TOPIC,
            key="interest",
            value="AI",
        )
        assert manager.learn_preference("user-1", pref)
        
        # 获取推荐
        recs = manager.get_recommendation("user-1", {})
        assert len(recs) > 0


# ══════════════════════════════════════════════════════════════
# 蜂群式AI原语扩展测试 (提升覆盖率)
# ══════════════════════════════════════════════════════════════

class TestDistributedPrimitiveExtended:
    """分布式原语扩展测试"""
    
    def test_crdt_sync_version_conflict(self):
        from ecos.l0.governance import CRDTSync, StateSnapshot
        
        sync = CRDTSync("node-1")
        sync.version = 5
        
        snapshot = StateSnapshot(
            node_id="node-2",
            version=3,  # 旧版本
            data={"key": "value"},
        )
        
        result = sync.sync(snapshot)
        # LWW 策略：远程版本虽然旧，但如果数据不同仍然会合并
        # 这里测试的是版本冲突时的行为
        assert result.local_version == 5
    
    def test_crdt_get_version(self):
        from ecos.l0.governance import CRDTSync
        
        sync = CRDTSync("node-1")
        assert sync.get_version() == 0
        
        sync.version = 10
        assert sync.get_version() == 10
    
    def test_crdt_get_node_status(self):
        from ecos.l0.governance import CRDTSync, NodeStatus
        
        sync = CRDTSync("node-1")
        status = sync.get_node_status("node-2")
        assert status == NodeStatus.OFFLINE


class TestRolePrimitiveExtended:
    """角色原语扩展测试"""
    
    def test_role_switch(self):
        from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
        
        manager = RoleManager()
        
        # 定义两个角色
        worker = RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["task"],
            constraints={},
        )
        manager = RoleManager()
        manager.define_role(worker)
        
        manager = RoleManager()
        manager.define_role(worker)
        specialist = RoleDefinition(
            role_id="specialist",
            role_type=RoleType.SPECIALIST,
            capabilities=["expert"],
            constraints={},
        )
        manager.define_role(specialist)
        
        # 分配角色
        manager.assign_role("agent-1", "worker")
        
        # 切换角色
        assert manager.switch_role("agent-1", "specialist")
        
        # 验证切换
        retrieved = manager.get_role("agent-1")
        assert retrieved.role_id == "specialist"
    
    def test_role_assign_nonexistent(self):
        from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
        
        manager = RoleManager()
        role = RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["task"],
            constraints={},
        )
        manager.define_role(role)
        
        # 分配不存在的角色
        assert not manager.assign_role("agent-1", "nonexistent")
    
    def test_role_switch_nonexistent_agent(self):
        from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
        
        manager = RoleManager()
        role = RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["task"],
            constraints={},
        )
        manager.define_role(role)
        
        # 切换不存在的 agent
        assert not manager.switch_role("nonexistent", "worker")
    
    def test_role_to_dict(self):
        from ecos.l0.governance import RoleDefinition, RoleType, AgentRole, RoleStatus
        
        role = RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["task"],
            constraints={"max_tasks": 5},
        )
        d = role.to_dict()
        assert d["role_id"] == "worker"
        assert d["role_type"] == "worker"
        assert "task" in d["capabilities"]
        
        agent_role = AgentRole(
            agent_id="agent-1",
            role_id="worker",
            status=RoleStatus.ACTIVE,
        )
        d = agent_role.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["status"] == "active"


class TestSwarmPrimitiveExtended:
    """蜂群原语扩展测试"""
    
    def test_swarm_predict_emergence(self):
        from ecos.l0.governance import SwarmManager, SwarmState, EmergentBehavior, EmergencePattern
        
        manager = SwarmManager()
        manager.agents = ["agent-1", "agent-2"]
        
        state = SwarmState(
            agents=manager.agents,
            behaviors=[
                EmergentBehavior(
                    pattern=EmergencePattern.CLUSTERING,
                    agents=["agent-1"],
                    confidence=0.8,
                )
            ],
        )
        
        predicted = manager.predict_emergence(state)
        assert len(predicted) > 0
        assert predicted[0].pattern == EmergencePattern.SPECIALIZATION
    
    def test_swarm_control_emergence(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern
        
        manager = SwarmManager()
        
        behavior = EmergentBehavior(
            pattern=EmergencePattern.CASCADE,
            agents=["agent-1", "agent-2"],
            confidence=0.9,
        )
        
        # 控制涌现
        assert manager.control_emergence(behavior, "suppress")
        assert manager.control_emergence(behavior, "amplify")
    
    def test_swarm_get_state(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern
        
        manager = SwarmManager()
        manager.agents = ["agent-1", "agent-2"]
        manager.behaviors = [
            EmergentBehavior(
                pattern=EmergencePattern.CLUSTERING,
                agents=["agent-1"],
                confidence=0.8,
            )
        ]
        
        state = manager.get_swarm_state()
        assert len(state.agents) == 2
        assert len(state.behaviors) == 1
    
    def test_emergent_behavior_to_dict(self):
        from ecos.l0.governance import EmergentBehavior, EmergencePattern, EmergenceLevel
        
        behavior = EmergentBehavior(
            pattern=EmergencePattern.OSCILLATION,
            agents=["agent-1", "agent-2", "agent-3"],
            confidence=0.7,
            level=EmergenceLevel.HIGH,
        )
        
        d = behavior.to_dict()
        assert d["pattern"] == "oscillation"
        assert len(d["agents"]) == 3
        assert d["confidence"] == 0.7
        assert d["level"] == "high"


class TestPersonalKnowledgePrimitiveExtended:
    """个人知识原语扩展测试"""
    
    def test_knowledge_graph(self):
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )
        
        manager = PersonalKnowledgeManager()
        
        # 添加有关系的知识
        node1 = KnowledgeNode(
            node_id="k1",
            knowledge_type=KnowledgeType.CONCEPT,
            content={"topic": "AI"},
            relations=["k2"],
        )
        node2 = KnowledgeNode(
            node_id="k2",
            knowledge_type=KnowledgeType.FACT,
            content={"topic": "ML"},
            relations=["k1"],
        )
        
        manager.add_knowledge(node1)
        manager.add_knowledge(node2)
        
        graph = manager.get_knowledge_graph()
        assert "k1" in graph
        assert "k2" in graph
        assert "k2" in graph["k1"]
    
    def test_query_knowledge_no_match(self):
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )
        
        manager = PersonalKnowledgeManager()
        
        node = KnowledgeNode(
            node_id="k1",
            knowledge_type=KnowledgeType.FACT,
            content={"topic": "AI"},
        )
        manager.add_knowledge(node)
        
        results = manager.query_knowledge("quantum")
        assert len(results) == 0
    
    def test_knowledge_node_to_dict(self):
        from ecos.l0.governance import KnowledgeNode, KnowledgeType
        
        node = KnowledgeNode(
            node_id="k1",
            knowledge_type=KnowledgeType.PROCEDURE,
            content={"steps": ["step1", "step2"]},
            relations=["k2"],
        )
        
        d = node.to_dict()
        assert d["node_id"] == "k1"
        assert d["knowledge_type"] == "procedure"
        assert "created_at" in d
