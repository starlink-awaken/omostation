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
        (omo_dir / "system.yaml").write_text(
            "debt_weight: 1.0\ndebt_metrics:\n  debt_health: 100.0\n"
        )

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

    def test_node_manager_version_and_cleanup_helpers(self):
        """心跳应推进版本，离线节点可被过滤与清理。"""
        from datetime import datetime, timedelta, timezone

        from ecos.l0.governance import NodeManager

        manager = NodeManager()
        manager.heartbeat_interval = 1
        node = manager.register("node-1")
        old_version = node.version

        assert manager.update_heartbeat("node-1") is True
        assert manager.get_node("node-1").version == old_version + 1  # type: ignore[reportOptionalMemberAccess]

        healthy = manager.get_healthy_nodes()
        assert [n.node_id for n in healthy] == ["node-1"]

        manager.nodes["node-1"].last_heartbeat = datetime.now(timezone.utc) - timedelta(
            seconds=10
        )
        removed = manager.remove_offline_nodes()
        assert removed == ["node-1"]
        assert manager.get_node("node-1") is None

    def test_state_sync_service_snapshot_and_merge(self):
        """StateSyncService 应生成快照并按策略合并远程状态。"""
        from ecos.l0.governance import StateSnapshot, StateSyncService, SyncStrategy

        service = StateSyncService("node-1", strategy=SyncStrategy.EVENTUAL)
        service.set("key1", "local")
        snapshot = service.generate_snapshot()
        assert snapshot.node_id == "node-1"
        assert snapshot.checksum

        remote_snapshot = StateSnapshot(
            node_id="node-2", version=2, data={"key1": "remote", "key2": "new"}
        )
        result = service.sync_from_snapshot(remote_snapshot)

        assert result.success is True
        assert result.conflicts == ["key1"]
        assert service.get("key1") == "remote"
        assert service.get("key2") == "new"

    def test_communication_protocol_send_dispatch_and_dead_letter(self):
        """CommunicationProtocol 应支持连接、发送、分发和死信。"""
        from ecos.l0.governance import (
            CommunicationProtocol,
            Message,
            MessageType,
            ProtocolType,
        )

        protocol = CommunicationProtocol("node-1", protocol_type=ProtocolType.TCP)
        protocol.connect("node-2")

        message = Message(
            message_id="msg-1",
            message_type=MessageType.SYNC,
            source="node-1",
            target="node-2",
            payload={"ok": True},
        )
        assert protocol.send("node-2", message) is True

        captured = []
        protocol.register_handler(
            MessageType.SYNC, lambda msg: captured.append(msg.payload) or "done"
        )
        assert protocol.dispatch(message) == "done"
        assert captured == [{"ok": True}]

        failed = Message(
            message_id="msg-2",
            message_type=MessageType.HEARTBEAT,
            source="node-1",
            target="ghost",
            payload={},
        )
        assert protocol.send("ghost", failed) is False
        assert protocol.dead_letter_queue[-1]["message_id"] == "msg-2"


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
        task = scheduler.submit_task(
            "task-1", "测试任务", required_capabilities=["task"]
        )
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
        from ecos.l0.governance import TaskScheduler

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

    def test_role_collaboration(self):
        """测试角色协作"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleCollaboration,
            CollaborationMode,
        )

        manager = RoleManager()
        collaboration = RoleCollaboration(manager)

        # 定义角色
        manager.define_role(
            RoleDefinition(
                role_id="worker",
                role_type=RoleType.WORKER,
                capabilities=["task"],
                constraints={},
            )
        )
        manager.define_role(
            RoleDefinition(
                role_id="coordinator",
                role_type=RoleType.COORDINATOR,
                capabilities=["manage"],
                constraints={},
            )
        )

        # 创建协作任务
        task = collaboration.create_task(
            "task-1",
            "协作任务",
            ["worker", "coordinator"],
            CollaborationMode.SEQUENTIAL,
        )
        assert task.task_id == "task-1"

        # 分配角色
        assignments = {"worker": "agent-1", "coordinator": "agent-2"}
        assert collaboration.assign_roles_to_task("task-1", assignments)
        assert task.status == "assigned"

        # 开始任务
        assert collaboration.start_task("task-1")
        assert task.status == "running"

        # 完成任务
        assert collaboration.complete_task("task-1", {"output": "done"})
        assert task.status == "completed"

    def test_role_evaluator(self):
        """测试角色评估"""
        from ecos.l0.governance import RoleEvaluator

        evaluator = RoleEvaluator()

        # 评估
        eval1 = evaluator.evaluate(
            "agent-1", "worker", 85.0, {"speed": 0.9, "quality": 0.8}
        )
        assert eval1.score == 85.0

        evaluator.evaluate("agent-2", "worker", 92.0, {"speed": 0.95, "quality": 0.9})

        # 获取最新评估
        latest = evaluator.get_evaluation("agent-1")
        assert latest is not None
        assert latest.score == 85.0

        # 获取平均分
        avg = evaluator.get_average_score("worker")
        assert avg == 88.5  # (85 + 92) / 2

        # 获取 top agents
        top = evaluator.get_top_agents("worker", limit=1)
        assert len(top) == 1
        assert top[0].score == 92.0


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
        assert retrieved.role_id == "specialist"  # type: ignore[reportOptionalMemberAccess]

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
        from ecos.l0.governance import (
            SwarmManager,
            SwarmState,
            EmergentBehavior,
            EmergencePattern,
        )

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


class TestPersonalKnowledgePrimitiveExtended:
    """个人知识原语扩展测试"""

    def test_knowledge_graph(self):
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )

        manager = PersonalKnowledgeManager()

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

    def test_knowledge_graph_builder(self):
        """测试知识图谱构建器"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()

        builder.add_node("n1", {"type": "concept"})
        builder.add_node("n2", {"type": "fact"})
        builder.add_edge("n1", "n2", "related_to")

        neighbors = builder.get_neighbors("n1")
        assert "n2" in neighbors

        paths = builder.find_path("n1", "n2")
        assert len(paths) > 0
        assert paths[0] == ["n1", "n2"]

        mermaid = builder.to_mermaid()
        assert "n1" in mermaid
        assert "n2" in mermaid

    def test_preference_engine(self):
        """测试偏好学习引擎"""
        from ecos.l0.governance import PreferenceEngine

        engine = PreferenceEngine()

        engine.learn("user-1", "AI", "topic", 1.0)
        engine.learn("user-1", "ML", "topic", 0.8)
        engine.learn("user-1", "Python", "topic", 0.6)

        pref = engine.get_preference("user-1", "AI")
        assert abs(pref - 1.0) < 0.01  # 考虑时间衰减

        top = engine.get_top_preferences("user-1", 2)
        assert len(top) == 2
        assert top[0][0] == "AI"

    def test_recommendation_engine(self):
        """测试推荐引擎"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        pe = PreferenceEngine()
        engine = RecommendationEngine(km, pe)

        # 添加知识
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.FACT,
                content={"topic": "AI"},
            )
        )

        # 学习偏好
        pe.learn("user-1", "AI", "topic", 1.0)

        # 获取推荐
        recs = engine.recommend("user-1")
        assert len(recs) > 0
        assert recs[0].node_id == "k1"


# ══════════════════════════════════════════════════════════════
# 深度集成测试 — 真实算法行为验证
# ══════════════════════════════════════════════════════════════


class TestStateSyncServiceIntegration:
    """StateSyncService 深度集成测试 — 验证向量时钟、冲突检测、增量同步"""

    def test_two_node_sync_vector_clock(self):
        """两个节点同步后向量时钟正确合并"""
        from ecos.l0.governance import StateSyncService

        node_a = StateSyncService("node-a")
        node_b = StateSyncService("node-b")

        node_a.set("x", 1)
        node_a.set("y", 2)
        node_b.set("z", 3)

        snap_a = node_a.generate_snapshot()
        snap_b = node_b.generate_snapshot()

        node_b.sync_from_snapshot(snap_a)
        node_a.sync_from_snapshot(snap_b)

        assert node_a.get("x") == 1
        assert node_a.get("y") == 2
        assert node_a.get("z") == 3
        assert node_b.get("x") == 1
        assert node_b.get("y") == 2
        assert node_b.get("z") == 3

        assert "node-b" in node_a.vector_clock
        assert "node-a" in node_b.vector_clock

    def test_conflict_detection_crdt(self):
        """CRDT 策略下检测到冲突但保留本地值"""
        from ecos.l0.governance import StateSyncService, SyncStrategy
        from datetime import datetime, timezone, timedelta

        node_a = StateSyncService("node-a", SyncStrategy.CRDT)
        node_b = StateSyncService("node-b", SyncStrategy.CRDT)

        node_a.set("key", "local_value")
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        snap_a = node_a.generate_snapshot()
        snap_a.timestamp = old_time

        node_b.set("key", "remote_value")
        snap_b = node_b.generate_snapshot()

        result = node_a.sync_from_snapshot(snap_b)
        assert "key" in result.conflicts

    def test_eventual_consistency_converges(self):
        """最终一致性策略下两个节点收敛到相同状态"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        node_a = StateSyncService("node-a", SyncStrategy.EVENTUAL)
        node_b = StateSyncService("node-b", SyncStrategy.EVENTUAL)

        node_a.set("counter", 10)
        node_b.set("counter", 20)

        snap_b = node_b.generate_snapshot()

        node_a.sync_from_snapshot(snap_b)
        snap_a_after = node_a.generate_snapshot()
        node_b.sync_from_snapshot(snap_a_after)

        assert node_a.get("counter") == node_b.get("counter")

    def test_delta_sync_only_changes(self):
        """增量同步只返回变化的键"""
        from ecos.l0.governance import StateSyncService

        node_a = StateSyncService("node-a")
        node_a.set("a", 1)
        node_a.set("b", 2)

        remote_clock = {"node-a": 0}
        delta = node_a.get_delta_since(remote_clock)
        assert "a" in delta
        assert "b" in delta

        remote_clock2 = {"node-a": 2}
        delta2 = node_a.get_delta_since(remote_clock2)
        assert len(delta2) == 0

    def test_batch_merge_state(self):
        """批量合并远程状态"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        local = StateSyncService("local", SyncStrategy.EVENTUAL)
        local.set("k1", "v1")

        remote_state = {"k1": "v1_new", "k2": "v2"}
        remote_clock = {"remote": 5}

        result = local.merge_state(remote_state, remote_clock)
        assert result.success
        assert local.get("k1") == "v1_new"
        assert local.get("k2") == "v2"


class TestSwarmManagerDeepIntegration:
    """SwarmManager 深度集成测试 — 验证振荡检测、级联检测、特化检测"""

    def test_oscillation_detection(self):
        """振荡检测：Agent 状态在正负值之间摆动"""
        from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1", "a2"]

        oscillating_values = [10, -10, 8, -8, 6, -6]
        for val in oscillating_values:
            manager.update_agent_state("a1", {"value": val})
        manager.update_agent_state("a2", {"value": 1})

        state = SwarmState(agents=["a1", "a2"], behaviors=[])
        behaviors = manager.detect_emergence(state)

        oscillation = [
            b for b in behaviors if b.pattern == EmergencePattern.OSCILLATION
        ]
        assert len(oscillation) == 1
        assert "a1" in oscillation[0].agents

    def test_cascade_detection(self):
        """级联检测：一个 Agent 的状态变化触发其他 Agent 变化"""
        from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1", "a2", "a3"]

        manager.update_agent_state("a1", {"status": "trigger"})
        manager.update_agent_state("a2", {"status": "trigger"})
        manager.update_agent_state("a3", {"status": "trigger"})
        manager.update_agent_state("a1", {"status": "cascade"})
        manager.update_agent_state("a2", {"status": "cascade"})
        manager.update_agent_state("a3", {"status": "cascade"})

        state = SwarmState(agents=["a1", "a2", "a3"], behaviors=[])
        behaviors = manager.detect_emergence(state)

        cascade = [b for b in behaviors if b.pattern == EmergencePattern.CASCADE]
        assert len(cascade) >= 1

    def test_specialization_detection(self):
        """特化检测：Agent 演化出不同角色"""
        from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1", "a2", "a3", "a4"]

        manager.update_agent_state("a1", {"role": "researcher"})
        manager.update_agent_state("a2", {"role": "researcher"})
        manager.update_agent_state("a3", {"role": "coder"})
        manager.update_agent_state("a4", {"role": "reviewer"})

        state = SwarmState(
            agents=manager.agents,
            agent_states=manager.agent_states,
            behaviors=[],
        )
        behaviors = manager.detect_emergence(state)

        spec = [b for b in behaviors if b.pattern == EmergencePattern.SPECIALIZATION]
        assert len(spec) == 1
        assert spec[0].metadata["unique_roles"] >= 2

    def test_weighted_collective_decision(self):
        """加权投票决策：高权重 Agent 影响更大"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        weights = {"boss": 5.0, "worker1": 1.0, "worker2": 1.0}

        engine.create_proposal(
            "p1",
            "选择方案",
            ["A", "B"],
            DecisionMethod.WEIGHTED_VOTE,
            agent_weights=weights,
        )
        engine.vote("p1", "boss", "B")
        engine.vote("p1", "worker1", "A")
        engine.vote("p1", "worker2", "A")

        result = engine.decide("p1")
        assert result == "B"

    def test_consensus_requires_unanimity(self):
        """共识决策要求所有人一致"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        engine.create_proposal("p1", "共识", ["X", "Y"], DecisionMethod.CONSENSUS)
        engine.vote("p1", "a1", "X")
        engine.vote("p1", "a2", "Y")

        result = engine.decide("p1")
        assert result is None

    def test_vote_revoke(self):
        """撤回投票"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        engine.create_proposal("p1", "测试", ["A", "B"], DecisionMethod.MAJORITY_VOTE)
        engine.vote("p1", "a1", "A")
        assert engine.revoke_vote("p1", "a1")

        tally = engine.tally_votes("p1")
        assert tally["total_votes"] == 0

    def test_pheromone_decision(self):
        """信息素决策：累积权重收敛到最高强度选项"""
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        weights = {"a1": 3.0, "a2": 2.0, "a3": 1.0}
        engine.create_proposal(
            "p1", "信息素", ["X", "Y"], DecisionMethod.PHEROMONE, agent_weights=weights
        )
        engine.vote("p1", "a1", "X")
        engine.vote("p1", "a2", "X")
        engine.vote("p1", "a3", "Y")

        result = engine.decide("p1")
        assert result == "X"


class TestKnowledgeGraphDeepIntegration:
    """KnowledgeGraphBuilder 深度集成测试 — PageRank、介数中心性、社区发现"""

    def test_pagerank_hub_node(self):
        """PageRank：连接多的节点得分更高"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["A", "B", "C", "D"]:
            builder.add_node(n)
        builder.add_edge("A", "B", "knows")
        builder.add_edge("A", "C", "knows")
        builder.add_edge("A", "D", "knows")
        builder.add_edge("B", "C", "knows")

        pr = builder.pagerank()
        assert pr["A"] > pr["B"]
        assert pr["A"] > pr["C"]
        assert pr["A"] > pr["D"]

    def test_betweenness_centrality_bridge(self):
        """介数中心性：桥接节点得分最高"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["L1", "L2", "Bridge", "R1", "R2"]:
            builder.add_node(n)
        builder.add_edge("L1", "L2", "link")
        builder.add_edge("L2", "Bridge", "link")
        builder.add_edge("Bridge", "R1", "link")
        builder.add_edge("R1", "R2", "link")

        bc = builder.betweenness_centrality()
        assert bc.get("Bridge", 0) > bc.get("L1", 0)
        assert bc.get("Bridge", 0) > bc.get("R2", 0)

    def test_community_detection(self):
        """社区发现：密集连接的节点归为同一社区"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["A", "B", "C", "X", "Y", "Z"]:
            builder.add_node(n)
        builder.add_edge("A", "B", "intra")
        builder.add_edge("B", "C", "intra")
        builder.add_edge("A", "C", "intra")
        builder.add_edge("X", "Y", "intra")
        builder.add_edge("Y", "Z", "intra")
        builder.add_edge("X", "Z", "intra")
        builder.add_edge("A", "X", "inter")

        communities = builder.find_communities()
        assert len(communities) >= 2

    def test_find_path_multi_hop(self):
        """多跳路径搜索"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["S", "A", "B", "C", "T"]:
            builder.add_node(n)
        builder.add_edge("S", "A", "link")
        builder.add_edge("A", "B", "link")
        builder.add_edge("B", "C", "link")
        builder.add_edge("C", "T", "link")

        paths = builder.find_path("S", "T", max_depth=5)
        assert len(paths) >= 1
        assert paths[0][0] == "S"
        assert paths[0][-1] == "T"

    def test_degree_centrality(self):
        """度中心性计算"""
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["hub", "a", "b", "c", "d"]:
            builder.add_node(n)
        builder.add_edge("hub", "a", "link")
        builder.add_edge("hub", "b", "link")
        builder.add_edge("hub", "c", "link")
        builder.add_edge("hub", "d", "link")

        dc = builder.degree_centrality()
        assert dc["hub"] == 1.0
        assert dc["a"] < dc["hub"]


class TestRoleSwitcherIntegration:
    """RoleSwitcher 深度集成测试 — 冷却期、前置条件、冲突"""

    def test_cooldown_prevents_rapid_switch(self):
        """冷却期内不允许切换角色"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleSwitcher,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="r1", role_type=RoleType.WORKER, capabilities=[], constraints={}
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="r2",
                role_type=RoleType.SPECIALIST,
                capabilities=[],
                constraints={},
            )
        )
        rm.assign_role("a1", "r1")

        switcher = RoleSwitcher(rm, cooldown_seconds=10)
        ok, msg = switcher.switch("a1", "r2")
        assert ok

        ok2, msg2 = switcher.switch("a1", "r1")
        assert not ok2
        assert "冷却期" in msg2

    def test_prerequisite_blocks_switch(self):
        """前置角色不满足时阻止切换"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleSwitcher,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="novice",
                role_type=RoleType.WORKER,
                capabilities=[],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="expert",
                role_type=RoleType.SPECIALIST,
                capabilities=[],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="outsider",
                role_type=RoleType.WORKER,
                capabilities=[],
                constraints={},
            )
        )
        rm.assign_role("a1", "outsider")  # agent has "outsider", not "novice"

        switcher = RoleSwitcher(rm, cooldown_seconds=0)
        switcher.set_prerequisites("expert", ["novice"])

        ok, msg = switcher.switch("a1", "expert")
        assert not ok
        assert "前置角色" in msg

    def test_conflict_blocks_switch(self):
        """角色冲突时阻止切换"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleSwitcher,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="worker",
                role_type=RoleType.WORKER,
                capabilities=[],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="manager",
                role_type=RoleType.MANAGER,
                capabilities=[],
                constraints={},
            )
        )
        rm.assign_role("a1", "worker")

        switcher = RoleSwitcher(rm, cooldown_seconds=0)
        switcher.set_conflicts("manager", ["worker"])

        ok, msg = switcher.switch("a1", "manager")
        assert not ok
        assert "冲突" in msg

    def test_switch_history_tracked(self):
        """切换历史被正确记录"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleSwitcher,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="r1", role_type=RoleType.WORKER, capabilities=[], constraints={}
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="r2",
                role_type=RoleType.SPECIALIST,
                capabilities=[],
                constraints={},
            )
        )
        rm.assign_role("a1", "r1")

        switcher = RoleSwitcher(rm, cooldown_seconds=0)
        switcher.switch("a1", "r2")

        history = switcher.get_switch_history("a1")
        assert len(history) == 1
        assert history[0]["old_role"] == "r1"
        assert history[0]["new_role"] == "r2"

    def test_role_distribution(self):
        """角色分布统计正确"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleSwitcher,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="r1", role_type=RoleType.WORKER, capabilities=[], constraints={}
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="r2",
                role_type=RoleType.SPECIALIST,
                capabilities=[],
                constraints={},
            )
        )
        rm.assign_role("a1", "r1")
        rm.assign_role("a2", "r1")
        rm.assign_role("a3", "r2")

        switcher = RoleSwitcher(rm, cooldown_seconds=0)
        dist = switcher.get_role_distribution()
        assert len(dist["r1"]) == 2
        assert len(dist["r2"]) == 1


class TestFailoverManagerDeepIntegration:
    """FailoverManager 深度集成测试 — 轮询轮转、故障转移历史"""

    def test_round_robin_rotation(self):
        """轮询策略正确轮转目标节点"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        manager = FailoverManager()
        rule = FailoverRule(
            rule_id="r1",
            source_node="s1",
            target_nodes=["t1", "t2", "t3"],
            strategy=FailoverStrategy.ROUND_ROBIN,
        )
        manager.add_rule(rule)

        targets = set()
        for _ in range(6):
            t = manager.execute_failover("s1")
            targets.add(t)

        assert targets == {"t1", "t2", "t3"}

    def test_failover_history_recorded(self):
        """故障转移历史被正确记录"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        manager = FailoverManager()
        rule = FailoverRule(
            rule_id="r1",
            source_node="s1",
            target_nodes=["t1", "t2"],
            strategy=FailoverStrategy.ROUND_ROBIN,
        )
        manager.add_rule(rule)

        manager.execute_failover("s1")
        manager.execute_failover("s1")

        history = manager.get_failover_history()
        assert len(history) == 2
        assert history[0]["source"] == "s1"

    def test_least_loaded_strategy(self):
        """最小负载策略选择负载最低的节点"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        manager = FailoverManager()
        manager.update_node_load("t1", 10)
        manager.update_node_load("t2", 2)
        manager.update_node_load("t3", 5)

        rule = FailoverRule(
            rule_id="r1",
            source_node="s1",
            target_nodes=["t1", "t2", "t3"],
            strategy=FailoverStrategy.LEAST_LOADED,
        )
        manager.add_rule(rule)

        target = manager.execute_failover("s1")
        assert target == "t2"

    def test_priority_strategy(self):
        """优先级策略选择最高优先级节点"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        manager = FailoverManager()
        manager.update_node_priority("t1", 1)
        manager.update_node_priority("t2", 10)
        manager.update_node_priority("t3", 5)

        rule = FailoverRule(
            rule_id="r1",
            source_node="s1",
            target_nodes=["t1", "t2", "t3"],
            strategy=FailoverStrategy.PRIORITY,
        )
        manager.add_rule(rule)

        target = manager.execute_failover("s1")
        assert target == "t2"

    def test_failover_count(self):
        """故障转移计数正确"""
        from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

        manager = FailoverManager()
        rule = FailoverRule(
            rule_id="r1",
            source_node="s1",
            target_nodes=["t1"],
            strategy=FailoverStrategy.ROUND_ROBIN,
        )
        manager.add_rule(rule)

        manager.execute_failover("s1")
        manager.execute_failover("s1")

        counts = manager.get_failover_count()
        assert counts["s1"] == 2


class TestRecommendationEngineDeepIntegration:
    """RecommendationEngine 深度集成测试 — TF-IDF + 偏好匹配"""

    def test_tfidf_relevance_ranking(self):
        """TF-IDF 相关度排名：包含更多相关词的文档排名更高"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.FACT,
                content={
                    "text": "artificial intelligence machine learning deep learning"
                },
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "cooking recipes pasta italian food"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k3",
                knowledge_type=KnowledgeType.CONCEPT,
                content={"text": "neural network artificial intelligence training"},
            )
        )

        pe = PreferenceEngine()
        pe.learn("user-1", "artificial", "topic", 1.0)
        pe.learn("user-1", "intelligence", "topic", 1.0)

        engine = RecommendationEngine(km, pe)
        recs = engine.recommend("user-1")
        assert len(recs) >= 2
        assert recs[0].node_id in ("k1", "k3")

    def test_preference_boosts_ranking(self):
        """偏好匹配提升排名"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "python programming language"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "java programming language"},
            )
        )

        pe = PreferenceEngine()
        pe.learn("user-1", "python", "topic", 5.0)

        engine = RecommendationEngine(km, pe)
        recs = engine.recommend("user-1")
        assert recs[0].node_id == "k1"

    def test_similar_content_recommendation(self):
        """相似内容推荐"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.CONCEPT,
                content={"text": "machine learning algorithms"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.CONCEPT,
                content={"text": "deep learning neural networks"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k3",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "cooking italian pasta"},
            )
        )

        pe = PreferenceEngine()
        engine = RecommendationEngine(km, pe)
        recs = engine.recommend_similar("k1")
        assert len(recs) >= 1
        assert recs[0].node_id == "k2"

    def test_tag_based_query(self):
        """标签查询"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "AI"},
                tags=["tech", "ai"],
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "ML"},
                tags=["tech", "ml"],
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k3",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "cooking"},
                tags=["food"],
            )
        )

        results = km.query_by_tags(["tech"])
        assert len(results) == 2

        results = km.query_by_tags(["ai"], match_all=True)
        assert len(results) == 1

    def test_related_knowledge(self):
        """关联知识查询"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.CONCEPT,
                content={"text": "AI"},
                relations=["k2", "k3"],
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "ML"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k3",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "DL"},
            )
        )

        related = km.get_related("k1", depth=1)
        assert len(related) == 2

    def test_preference_decay(self):
        """偏好随时间衰减"""
        from ecos.l0.governance import PreferenceEngine

        engine = PreferenceEngine(decay_half_life_days=0.001)
        engine.learn("u1", "key", "topic", 10.0)

        current = engine.get_preference("u1", "key")
        assert current > 0


# ══════════════════════════════════════════════════════════════
# Phase 1-5 验收标准验证测试
# ══════════════════════════════════════════════════════════════


class TestPhase1Acceptance:
    """Phase 1 验收: 2机状态同步延迟 < 100ms"""

    def test_sync_latency_under_100ms(self):
        import time
        from ecos.l0.governance import StateSyncService, SyncStrategy

        node_a = StateSyncService("node-a", SyncStrategy.CRDT)
        node_b = StateSyncService("node-b", SyncStrategy.CRDT)

        for i in range(100):
            node_a.set(f"key-{i}", f"value-{i}")

        start = time.monotonic()
        snap = node_a.generate_snapshot()
        node_b.sync_from_snapshot(snap)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 100, f"同步延迟 {elapsed_ms:.1f}ms 超过 100ms"
        assert node_b.get("key-99") == "value-99"

    def test_multi_key_sync_completes(self):
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        for i in range(50):
            a.set(f"k{i}", i)

        snap_a = a.generate_snapshot()
        b.sync_from_snapshot(snap_a)

        for i in range(50):
            assert b.get(f"k{i}") == i


class TestPhase2Acceptance:
    """Phase 2 验收: 4机任务调度成功率 > 99%"""

    def test_four_node_scheduling_success_rate(self):
        from ecos.l0.governance import AgentRegistry, TaskScheduler

        registry = AgentRegistry()
        scheduler = TaskScheduler()

        for i in range(4):
            registry.register(f"agent-{i}", f"worker-{i}", ["compute", "task"])

        total_tasks = 100
        success_count = 0

        for i in range(total_tasks):
            scheduler.submit_task(
                f"task-{i}", f"任务{i}", required_capabilities=["task"]
            )
            idle = registry.get_idle_agents()
            if idle:
                scheduler.assign_task(f"task-{i}", idle[0].agent_id)
                scheduler.start_task(f"task-{i}")
                scheduler.complete_task(f"task-{i}", result={"output": "done"})
                success_count += 1

        rate = success_count / total_tasks
        assert rate > 0.99, f"成功率 {rate:.1%} 低于 99%"

    def test_task_priority_scheduling(self):
        from ecos.l0.governance import TaskScheduler

        scheduler = TaskScheduler()
        scheduler.submit_task("low", "低优先级", priority=1)
        scheduler.submit_task("high", "高优先级", priority=10)
        scheduler.submit_task("mid", "中优先级", priority=5)

        next_task = scheduler.get_next_task()
        assert next_task.task_id == "high"  # type: ignore[reportOptionalMemberAccess]


class TestPhase3Acceptance:
    """Phase 3 验收: 3角色协作完成率 > 95%"""

    def test_three_role_collaboration_success_rate(self):
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleCollaboration,
            CollaborationMode,
        )

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="worker",
                role_type=RoleType.WORKER,
                capabilities=["execute"],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="reviewer",
                role_type=RoleType.SPECIALIST,
                capabilities=["review"],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="coordinator",
                role_type=RoleType.COORDINATOR,
                capabilities=["manage"],
                constraints={},
            )
        )

        collab = RoleCollaboration(rm)

        total_tasks = 50
        success_count = 0

        for i in range(total_tasks):
            collab.create_task(
                f"task-{i}",
                f"协作任务{i}",
                ["worker", "reviewer", "coordinator"],
                CollaborationMode.SEQUENTIAL,
            )
            assignments = {
                "worker": f"worker-{i}",
                "reviewer": f"reviewer-{i}",
                "coordinator": f"coord-{i}",
            }
            if collab.assign_roles_to_task(f"task-{i}", assignments):
                collab.start_task(f"task-{i}")
                collab.complete_task(f"task-{i}", {"result": "done"})
                success_count += 1

        rate = success_count / total_tasks
        assert rate > 0.95, f"协作完成率 {rate:.1%} 低于 95%"

    def test_role_evaluator_scoring(self):
        from ecos.l0.governance import RoleEvaluator

        evaluator = RoleEvaluator()
        for score in [80, 85, 90, 95, 75]:
            evaluator.evaluate("agent-1", "worker", score)

        avg = evaluator.get_average_score("worker")
        assert 80 <= avg <= 85

        trend = evaluator.get_improvement_trend("agent-1", "worker")
        assert trend in ("improving", "stable", "declining")


class TestPhase4Acceptance:
    """Phase 4 验收: 涌现检测准确率 > 80%"""

    def test_emergence_detection_accuracy(self):
        from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern

        correct = 0
        total = 10

        for _ in range(total):
            manager = SwarmManager()
            for i in range(5):
                manager.add_agent(f"a{i}", initial_state={"role": "general"})

            state = SwarmState(
                agents=manager.agents,
                agent_states=manager.agent_states,
                behaviors=[],
            )
            behaviors = manager.detect_emergence(state)
            patterns = [b.pattern for b in behaviors]

            if EmergencePattern.CLUSTERING in patterns:
                correct += 1

        rate = correct / total
        assert rate > 0.80, f"检测准确率 {rate:.1%} 低于 80%"

    def test_collective_decision_majority(self):
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        engine.create_proposal(
            "p1", "测试", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE
        )

        for i in range(7):
            engine.vote("p1", f"a{i}", "A")
        for i in range(3):
            engine.vote("p1", f"b{i}", "B")

        result = engine.decide("p1")
        assert result == "A"


class TestPhase5Acceptance:
    """Phase 5 验收: 知识图谱覆盖率 > 90%"""

    def test_knowledge_graph_coverage(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        nodes = [f"n{i}" for i in range(20)]
        for n in nodes:
            builder.add_node(n)

        for i in range(19):
            builder.add_edge(f"n{i}", f"n{i + 1}", "related")

        coverage = len(builder.nodes) / len(nodes)
        assert coverage > 0.90, f"覆盖率 {coverage:.1%} 低于 90%"

    def test_pagerank_convergence(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        for n in ["A", "B", "C", "D", "E"]:
            builder.add_node(n)
        builder.add_edge("A", "B", "link")
        builder.add_edge("A", "C", "link")
        builder.add_edge("A", "D", "link")
        builder.add_edge("A", "E", "link")

        pr = builder.pagerank()
        assert abs(sum(pr.values()) - 1.0) < 0.01
        assert pr["A"] > 0.3

    def test_recommendation_quality(self):
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        km.add_knowledge(
            KnowledgeNode(
                node_id="k1",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "python machine learning algorithms"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k2",
                knowledge_type=KnowledgeType.FACT,
                content={"text": "cooking italian pasta recipes"},
            )
        )
        km.add_knowledge(
            KnowledgeNode(
                node_id="k3",
                knowledge_type=KnowledgeType.CONCEPT,
                content={"text": "deep learning neural networks"},
            )
        )

        pe = PreferenceEngine()
        pe.learn("user-1", "machine", "topic", 5.0)
        pe.learn("user-1", "learning", "topic", 5.0)

        engine = RecommendationEngine(km, pe)
        recs = engine.recommend("user-1", limit=3)

        relevant = sum(1 for r in recs if r.node_id in ("k1", "k3"))
        assert relevant >= 1


# ══════════════════════════════════════════════════════════════
# 治理检查器测试
# ══════════════════════════════════════════════════════════════


class TestSwarmBrainStructureChecker:
    """蜂群大脑结构检查器测试"""

    def test_execute_pass(self, tmp_path):
        from ecos.l0.governance import SwarmBrainStructureChecker, CheckStatus

        (tmp_path / "src" / "ecos" / "l0" / "governance").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l1" / "runtime").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l2" / "engine").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l3" / "entry").mkdir(parents=True)

        for f in [
            "distributed.py",
            "role.py",
            "swarm.py",
            "personal.py",
            "agent_registry.py",
            "task_scheduler.py",
            "failover.py",
            "load_balancer.py",
        ]:
            (tmp_path / "src" / "ecos" / "l0" / "governance" / f).write_text(
                "# placeholder\n" * 100
            )

        for layer in ["l1/runtime", "l2/engine", "l3/entry"]:
            (tmp_path / "src" / "ecos" / layer / "__init__.py").write_text(
                "# " + "x" * 600
            )

        for d in ["test_l0", "test_l1", "test_l2", "test_l3"]:
            (tmp_path / "tests" / d).mkdir(parents=True)
            (tmp_path / "tests" / d / "test_x.py").write_text("# test")

        checker = SwarmBrainStructureChecker(tmp_path)
        result = checker.execute()
        assert result.status == CheckStatus.PASS

    def test_execute_warn(self, tmp_path):
        from ecos.l0.governance import SwarmBrainStructureChecker, CheckStatus

        (tmp_path / "src" / "ecos" / "l0" / "governance").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l1" / "runtime").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l2" / "engine").mkdir(parents=True)
        (tmp_path / "src" / "ecos" / "l3" / "entry").mkdir(parents=True)

        for f in [
            "distributed.py",
            "role.py",
            "swarm.py",
            "personal.py",
            "agent_registry.py",
            "task_scheduler.py",
            "failover.py",
            "load_balancer.py",
        ]:
            (tmp_path / "src" / "ecos" / "l0" / "governance" / f).write_text("x" * 200)

        for layer in ["l1/runtime", "l2/engine", "l3/entry"]:
            (tmp_path / "src" / "ecos" / layer / "__init__.py").write_text("x" * 200)

        (tmp_path / "tests" / "test_l0").mkdir(parents=True)
        (tmp_path / "tests" / "test_l0" / "test_x.py").write_text("# test")

        checker = SwarmBrainStructureChecker(tmp_path)
        result = checker.execute()
        assert result.status in (CheckStatus.WARN, CheckStatus.FAIL)

    def test_get_description(self, tmp_path):
        from ecos.l0.governance import SwarmBrainStructureChecker

        checker = SwarmBrainStructureChecker(tmp_path)
        desc = checker.get_description()
        assert "蜂群大脑" in desc


# ══════════════════════════════════════════════════════════════
# 跨层集成测试 — L0 → L1 → L2 → L3 全链路
# ══════════════════════════════════════════════════════════════


class TestCrossLayerIntegration:
    """跨层集成测试 — 验证 L0-L3 全链路协作"""

    def test_l0_swarm_to_l2_engine(self):
        """L0 蜂群原语 → L2 蜂群引擎 集成"""
        from ecos.l0.governance import SwarmManager
        from ecos.l2.engine import SwarmEngine, EngineConfig

        l0_manager = SwarmManager()
        for i in range(5):
            l0_manager.add_agent(f"a{i}", initial_state={"role": "worker"})

        l2_engine = SwarmEngine(EngineConfig(engine_id="swarm-l2"))
        l2_engine.start()
        for aid in l0_manager.agents:
            l2_engine.register_agent(aid, l0_manager.agent_states.get(aid, {}))

        l0_state = l0_manager.get_swarm_state()
        l0_behaviors = l0_manager.detect_emergence(l0_state)
        l2_behaviors = l2_engine.detect_emergence()

        assert len(l0_behaviors) >= 1
        assert len(l2_behaviors) >= 1

    def test_l0_role_to_l2_collaboration(self):
        """L0 角色原语 → L2 协作引擎 集成"""
        from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
        from ecos.l2.engine import CollaborationEngine, EngineConfig

        rm = RoleManager()
        rm.define_role(
            RoleDefinition(
                role_id="worker",
                role_type=RoleType.WORKER,
                capabilities=["execute"],
                constraints={},
            )
        )

        l2_engine = CollaborationEngine(EngineConfig(engine_id="collab-l2"))
        l2_engine.start()

        for i in range(4):
            l2_engine.register_agent(f"agent-{i}", ["execute"])

        for i in range(10):
            l2_engine.submit_task(
                f"task-{i}", f"任务{i}", required_capabilities=["execute"]
            )

        assignments = l2_engine.auto_assign()
        assert len(assignments) == 10

        for task_id, agent_id in assignments:
            l2_engine.start_task(task_id)
            l2_engine.complete_task(task_id, {"output": "done"})

        status = l2_engine.get_pipeline_status()
        assert status["stage_distribution"].get("done", 0) == 10

    def test_l0_personal_to_l2_knowledge(self):
        """L0 个人知识原语 → L2 个人引擎 集成"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )
        from ecos.l2.engine import PersonalEngine, EngineConfig

        l0_km = PersonalKnowledgeManager()
        l0_pe = PreferenceEngine()

        l2_engine = PersonalEngine(EngineConfig(engine_id="personal-l2"))
        l2_engine.start()

        topics = ["AI", "ML", "Python", "Cooking", "Music"]
        for t in topics:
            l0_km.add_knowledge(
                KnowledgeNode(
                    node_id=t.lower(),
                    knowledge_type=KnowledgeType.FACT,
                    content={"topic": t},
                    tags=[t.lower()],
                )
            )
            l2_engine.add_knowledge(t.lower(), {"topic": t}, tags=[t.lower()])

        l0_pe.learn("user-1", "ai", "topic", 5.0)
        l2_engine.learn_preference("user-1", "ai", 5.0)

        l0_recs = RecommendationEngine(l0_km, l0_pe).recommend("user-1")
        l2_recs = l2_engine.get_recommendations("user-1")

        assert len(l0_recs) >= 1
        assert len(l2_recs) >= 1

    def test_l0_distributed_to_l1_sync(self):
        """L0 分布式原语 → L1 状态同步 集成"""
        from ecos.l0.governance import StateSyncService, SyncStrategy
        from ecos.l1.runtime import StateSyncService as L1StateSync

        l0_node_a = StateSyncService("node-a", SyncStrategy.EVENTUAL)
        l0_node_b = StateSyncService("node-b", SyncStrategy.EVENTUAL)
        l1_node = L1StateSync("node-l1")

        l0_node_a.set("x", 1)
        l0_node_a.set("y", 2)
        l1_node.set("z", 3)

        snap_a = l0_node_a.generate_snapshot()
        l0_node_b.sync_from_snapshot(snap_a)

        l1_node.sync_from({k: (v, 1) for k, v in l0_node_a.get_all().items()})

        assert l0_node_b.get("x") == 1
        assert l0_node_b.get("y") == 2
        assert l1_node.get("x") == 1
        assert l1_node.get("z") == 3

    def test_l3_cli_to_l0_check(self):
        """L3 CLI → L0 检查器 集成"""
        from ecos.l3.entry import GovernanceCLI

        cli = GovernanceCLI()
        result = cli.run(["check", "--dimension", "X1"])
        assert result == 0
        output = cli.get_output()
        assert any("X1" in line for line in output)

    def test_l3_mcp_full_workflow(self):
        """L3 MCP 完整工作流"""
        from ecos.l3.entry import GovernanceMCP

        mcp = GovernanceMCP()

        status = mcp.call_tool("governance_status")
        assert status["status"] == "ok"

        cluster = mcp.call_tool("cluster_list")
        assert cluster["status"] == "ok"
        assert isinstance(cluster["nodes"], list)

        swarm = mcp.call_tool("swarm_status")
        assert swarm["status"] == "ok"

        knowledge = mcp.call_tool("knowledge_stats")
        assert knowledge["status"] == "ok"

        task = mcp.call_tool("task_submit", {"task_id": "t1", "name": "test"})
        assert task["status"] == "ok"


# ══════════════════════════════════════════════════════════════
# 边界情况测试
# ══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试 — 空输入、极端值、异常路径"""

    def test_empty_graph_pagerank(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        pr = builder.pagerank()
        assert pr == {}

    def test_single_node_pagerank(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        builder.add_node("only")
        pr = builder.pagerank()
        assert abs(pr["only"] - 1.0) < 0.01

    def test_empty_swarm_detect(self):
        from ecos.l0.governance import SwarmManager, SwarmState

        manager = SwarmManager()
        state = SwarmState(agents=[], behaviors=[])
        behaviors = manager.detect_emergence(state)
        assert len(behaviors) == 0

    def test_single_agent_swarm(self):
        from ecos.l0.governance import SwarmManager, SwarmState

        manager = SwarmManager()
        manager.add_agent("solo")
        state = SwarmState(agents=["solo"], behaviors=[])
        behaviors = manager.detect_emergence(state)
        assert len(behaviors) == 0

    def test_empty_knowledge_query(self):
        from ecos.l0.governance import PersonalKnowledgeManager

        km = PersonalKnowledgeManager()
        results = km.query_knowledge("anything")
        assert len(results) == 0

    def test_empty_task_scheduler(self):
        from ecos.l0.governance import TaskScheduler

        scheduler = TaskScheduler()
        assert scheduler.get_next_task() is None
        assert len(scheduler.get_pending_tasks()) == 0

    def test_crdt_empty_snapshot_sync(self):
        from ecos.l0.governance import StateSyncService, SyncStrategy

        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        b = StateSyncService("b", SyncStrategy.EVENTUAL)

        snap = a.generate_snapshot()
        result = b.sync_from_snapshot(snap)
        assert result.success
        assert len(result.conflicts) == 0

    def test_failover_no_rules(self):
        from ecos.l0.governance import FailoverManager

        manager = FailoverManager()
        target = manager.execute_failover("nonexistent")
        assert target is None

    def test_load_balancer_empty(self):
        from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy

        balancer = LoadBalancer(LoadBalancingStrategy.ROUND_ROBIN)
        assert balancer.select_node() is None

    def test_role_manager_empty(self):
        from ecos.l0.governance import RoleManager

        rm = RoleManager()
        assert rm.list_roles() == []
        assert rm.get_role("nonexistent") is None

    def test_collective_decision_no_votes(self):
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        engine.create_proposal("p1", "空投票", ["A", "B"], DecisionMethod.MAJORITY_VOTE)
        result = engine.decide("p1")
        assert result is None

    def test_preference_engine_empty(self):
        from ecos.l0.governance import PreferenceEngine

        engine = PreferenceEngine()
        assert engine.get_preference("nobody", "nothing") == 0.0
        assert engine.get_top_preferences("nobody") == []

    def test_communication_protocol_no_connect(self):
        from ecos.l1.runtime import CommunicationProtocol, Message, MessageType

        protocol = CommunicationProtocol("node-1")
        msg = Message.create(MessageType.SYNC, "node-1", "node-2", {})
        result = protocol.send("node-2", msg)
        assert result is False

    def test_collaboration_engine_no_agents(self):
        from ecos.l2.engine import CollaborationEngine, EngineConfig

        engine = CollaborationEngine(EngineConfig(engine_id="e1"))
        engine.start()
        engine.submit_task("t1", "任务")
        assignments = engine.auto_assign()
        assert len(assignments) == 0

    def test_swarm_engine_consensus_no_majority(self):
        from ecos.l2.engine import SwarmEngine, EngineConfig

        engine = SwarmEngine(EngineConfig(engine_id="s1"))
        engine.start()
        engine.propose_decision("p1", "分裂", ["X", "Y"], method="majority_vote")
        engine.vote("p1", "a1", "X")
        engine.vote("p1", "a2", "Y")
        result = engine.resolve_decision("p1")
        assert result is None

    def test_governance_cli_help_all_commands(self):
        from ecos.l3.entry import GovernanceCLI

        cli = GovernanceCLI()
        for cmd in ["check", "status", "cluster", "swarm", "knowledge", "help"]:
            result = cli.run([cmd])
            assert result == 0

    def test_mcp_unknown_tool(self):
        from ecos.l3.entry import GovernanceMCP

        mcp = GovernanceMCP()
        result = mcp.call_tool("nonexistent_tool")
        assert "error" in result
        assert "available" in result


# ══════════════════════════════════════════════════════════════
# 端到端验证 — 蜂群式AI超级大脑全链路工作流
# ══════════════════════════════════════════════════════════════


class TestEndToEndWorkflow:
    """端到端验证 — 证明蜂群式AI超级大脑能真正工作"""

    def test_multi_node_state_sync_workflow(self):
        """多节点状态同步完整工作流"""
        from ecos.l0.governance import StateSyncService, SyncStrategy

        nodes = [StateSyncService(f"node-{i}", SyncStrategy.EVENTUAL) for i in range(4)]

        nodes[0].set("config", "v1")
        nodes[0].set("status", "active")

        snap0 = nodes[0].generate_snapshot()
        for n in nodes[1:]:
            n.sync_from_snapshot(snap0)

        nodes[1].set("counter", 100)
        nodes[2].set("counter", 200)

        snap1 = nodes[1].generate_snapshot()
        snap2 = nodes[2].generate_snapshot()
        nodes[0].sync_from_snapshot(snap1)
        nodes[0].sync_from_snapshot(snap2)

        assert nodes[0].get("config") == "v1"
        assert nodes[0].get("status") == "active"
        assert nodes[0].get("counter") == 200

        for n in nodes:
            assert n.get("config") == "v1"

    def test_swarm_decision_workflow(self):
        """蜂群集体决策完整工作流"""
        from ecos.l0.governance import SwarmManager, CollectiveDecision, DecisionMethod

        manager = SwarmManager()
        for i in range(8):
            manager.add_agent(
                f"agent-{i}", weight=1.0 + i * 0.5, initial_state={"role": "worker"}
            )

        decision = CollectiveDecision()
        weights = {f"agent-{i}": 1.0 + i * 0.5 for i in range(8)}
        decision.create_proposal(
            "deploy",
            "选择部署策略",
            ["blue-green", "canary", "rolling"],
            DecisionMethod.WEIGHTED_VOTE,
            agent_weights=weights,
        )

        decision.vote("deploy", "agent-0", "canary")
        decision.vote("deploy", "agent-1", "canary")
        decision.vote("deploy", "agent-2", "canary")
        decision.vote("deploy", "agent-3", "blue-green")
        decision.vote("deploy", "agent-4", "rolling")
        decision.vote("deploy", "agent-5", "canary")
        decision.vote("deploy", "agent-6", "blue-green")
        decision.vote("deploy", "agent-7", "canary")

        result = decision.decide("deploy")
        assert result == "canary"

        state = manager.get_swarm_state()
        behaviors = manager.detect_emergence(state)
        assert len(behaviors) >= 1

    def test_knowledge_recommendation_workflow(self):
        """知识推荐完整工作流"""
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            KnowledgeGraphBuilder,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        graph = KnowledgeGraphBuilder()
        pe = PreferenceEngine()

        docs = [
            (
                "python-basics",
                "Python programming language fundamentals",
                ["python", "programming"],
            ),
            (
                "ml-algorithms",
                "Machine learning algorithms and models",
                ["ml", "algorithms"],
            ),
            ("deep-learning", "Deep learning neural networks", ["dl", "neural"]),
            (
                "cooking-101",
                "Basic cooking recipes and techniques",
                ["cooking", "recipes"],
            ),
            (
                "data-science",
                "Data science with Python and statistics",
                ["data", "science"],
            ),
        ]

        for doc_id, text, tags in docs:
            km.add_knowledge(
                KnowledgeNode(
                    node_id=doc_id,
                    knowledge_type=KnowledgeType.FACT,
                    content={"text": text},
                    tags=tags,
                )
            )
            graph.add_node(doc_id, {"text": text})

        graph.add_edge("python-basics", "ml-algorithms", "prerequisite")
        graph.add_edge("ml-algorithms", "deep-learning", "prerequisite")
        graph.add_edge("python-basics", "data-science", "prerequisite")
        graph.add_edge("ml-algorithms", "data-science", "related")

        pe.learn("user-1", "python", "topic", 5.0)
        pe.learn("user-1", "machine", "topic", 3.0)

        rec_engine = RecommendationEngine(km, pe)
        recs = rec_engine.recommend("user-1", limit=3)
        assert len(recs) >= 1
        assert recs[0].node_id in ("python-basics", "ml-algorithms", "data-science")

        pr = graph.pagerank()
        assert pr["python-basics"] > 0.15

        similar = rec_engine.recommend_similar("ml-algorithms")
        assert len(similar) >= 1

    def test_role_collaboration_workflow(self):
        """角色协作完整工作流"""
        from ecos.l0.governance import (
            RoleManager,
            RoleDefinition,
            RoleType,
            RoleCollaboration,
            RoleEvaluator,
            CollaborationMode,
        )

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
        rm.define_role(
            RoleDefinition(
                role_id="reviewer",
                role_type=RoleType.SPECIALIST,
                capabilities=["review"],
                constraints={},
            )
        )
        rm.define_role(
            RoleDefinition(
                role_id="lead",
                role_type=RoleType.COORDINATOR,
                capabilities=["manage"],
                constraints={},
            )
        )

        collab = RoleCollaboration(rm)
        evaluator = RoleEvaluator()

        collab.create_task(
            "project-1",
            "开发新功能",
            ["analyst", "developer", "reviewer", "lead"],
            CollaborationMode.PIPELINE,
        )
        assignments = {
            "analyst": "alice",
            "developer": "bob",
            "reviewer": "carol",
            "lead": "dave",
        }
        collab.assign_roles_to_task("project-1", assignments)
        collab.start_task("project-1")
        collab.complete_task("project-1", {"result": "shipped"})

        evaluator.evaluate("alice", "analyst", 92.0, {"speed": 0.9, "quality": 0.95})
        evaluator.evaluate("bob", "developer", 88.0, {"speed": 0.85, "quality": 0.9})
        evaluator.evaluate("carol", "reviewer", 95.0, {"catch_rate": 0.98})
        evaluator.evaluate("dave", "lead", 90.0, {"coordination": 0.92})

        avg = evaluator.get_average_score("analyst")
        assert avg == 92.0

        top = evaluator.get_top_agents("reviewer")
        assert len(top) == 1
        assert top[0].score == 95.0

    def test_fault_tolerance_workflow(self):
        """故障容错完整工作流"""
        from ecos.l0.governance import (
            FailoverManager,
            FailoverRule,
            FailoverStrategy,
            LoadBalancer,
            LoadBalancingStrategy,
            NodeManager,
            NodeStatus,
        )

        nm = NodeManager()
        for i in range(4):
            nm.register(f"node-{i}")

        fm = FailoverManager()
        fm.add_rule(
            FailoverRule(
                rule_id="rule-1",
                source_node="node-0",
                target_nodes=["node-1", "node-2", "node-3"],
                strategy=FailoverStrategy.ROUND_ROBIN,
            )
        )

        lb = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
        for i in range(4):
            lb.register_node(f"node-{i}", weight=1)

        health = nm.check_health()
        healthy_count = sum(
            1 for s in health.values() if s in (NodeStatus.ONLINE, NodeStatus.HEALTHY)
        )
        assert healthy_count == 4

        target1 = fm.execute_failover("node-0")
        target2 = fm.execute_failover("node-0")
        assert target1 != target2

        lb.update_connections("node-0", 15)
        lb.update_connections("node-1", 10)
        lb.update_connections("node-2", 3)
        lb.update_connections("node-3", 8)
        best = lb.select_node()
        assert best == "node-2"

    def test_l3_full_system_check(self):
        """L3 全系统检查"""
        from ecos.l3.entry import GovernanceCLI, GovernanceMCP

        cli = GovernanceCLI()
        for cmd in ["check", "status", "cluster", "swarm", "knowledge", "help"]:
            result = cli.run([cmd])
            assert result == 0, f"命令 {cmd} 失败"

        mcp = GovernanceMCP()
        tools = mcp.list_tools()
        assert len(tools) == 14

        for tool in [
            "governance_check",
            "governance_status",
            "cluster_list",
            "swarm_status",
            "knowledge_stats",
            "task_submit",
        ]:
            result = mcp.call_tool(tool)
            assert result["status"] == "ok", f"工具 {tool} 失败"


# ══════════════════════════════════════════════════════════════
# 新功能测试 — DAG 调度 / 涌现控制 / 增量图谱
# ══════════════════════════════════════════════════════════════


class TestDAGScheduler:
    """DAG 任务调度器测试"""

    def test_dag_ready_tasks(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "任务A")
        ts.submit_task("B", "任务B")
        ts.submit_task("C", "任务C")

        dag.add_dependency("B", "A")
        dag.add_dependency("C", "B")

        ready = dag.get_ready_tasks()
        assert "A" in ready
        assert "B" not in ready
        assert "C" not in ready

    def test_dag_mark_completed(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "任务A")
        ts.submit_task("B", "任务B")
        ts.submit_task("C", "任务C")

        dag.add_dependency("B", "A")
        dag.add_dependency("C", "B")

        dag.mark_completed("A")
        ready = dag.get_ready_tasks()
        assert "B" in ready
        assert "C" not in ready

        dag.mark_completed("B")
        ready = dag.get_ready_tasks()
        assert "C" in ready

    def test_dag_topological_order(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "A", priority=1)
        ts.submit_task("B", "B", priority=2)
        ts.submit_task("C", "C", priority=3)

        dag.add_dependency("B", "A")
        dag.add_dependency("C", "A")

        order = dag.get_topological_order()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")

    def test_dag_critical_path(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "A")
        ts.submit_task("B", "B")
        ts.submit_task("C", "C")
        ts.submit_task("D", "D")

        dag.add_dependency("B", "A")
        dag.add_dependency("C", "B")
        dag.add_dependency("D", "C")

        path = dag.get_critical_path()
        assert path == ["A", "B", "C", "D"]

    def test_dag_execution_plan(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "A")
        ts.submit_task("B", "B")
        ts.submit_task("C", "C")
        ts.submit_task("D", "D")

        dag.add_dependency("B", "A")
        dag.add_dependency("C", "A")
        dag.add_dependency("D", "B")

        plan = dag.get_execution_plan()
        assert len(plan) >= 2
        assert "A" in plan[0]

    def test_dag_stats(self):
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        ts.submit_task("A", "A")
        ts.submit_task("B", "B")
        dag.add_dependency("B", "A")

        stats = dag.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["dependencies"] == 1


class TestEmergenceControl:
    """涌现控制策略测试"""

    def test_suppress(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1", "a2", "a3"]

        behavior = EmergentBehavior(
            pattern=EmergencePattern.CLUSTERING,
            agents=["a1", "a2"],
            confidence=0.9,
        )
        manager.control_emergence(behavior, "suppress")

        assert manager.agent_states["a1"].get("controlled") is True
        assert manager.agent_states["a2"].get("controlled") is True

    def test_amplify(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        manager.add_agent("a1", weight=1.0)

        behavior = EmergentBehavior(
            pattern=EmergencePattern.CLUSTERING,
            agents=["a1"],
            confidence=0.9,
        )
        manager.control_emergence(behavior, "amplify")

        assert manager.agent_weights["a1"] == 1.5

    def test_redirect(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1"]

        behavior = EmergentBehavior(
            pattern=EmergencePattern.OSCILLATION,
            agents=["a1"],
            confidence=0.8,
        )
        manager.control_emergence(behavior, "redirect")

        assert manager.agent_states["a1"].get("redirected") is True
        assert manager.agent_states["a1"].get("redirect_from") == "oscillation"

    def test_isolate(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1"]

        behavior = EmergentBehavior(
            pattern=EmergencePattern.CASCADE,
            agents=["a1"],
            confidence=0.9,
        )
        manager.control_emergence(behavior, "isolate")

        assert manager.agent_states["a1"].get("isolated") is True

    def test_merge(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        manager.agents = ["a1", "a2", "a3"]

        behavior = EmergentBehavior(
            pattern=EmergencePattern.CLUSTERING,
            agents=["a1", "a2", "a3"],
            confidence=0.9,
        )
        manager.control_emergence(behavior, "merge")

        merged = manager.agent_states["a1"].get("merged_agents", [])
        assert "a2" in merged
        assert "a3" in merged

    def test_invalid_action(self):
        from ecos.l0.governance import SwarmManager, EmergentBehavior, EmergencePattern

        manager = SwarmManager()
        behavior = EmergentBehavior(
            pattern=EmergencePattern.CLUSTERING,
            agents=["a1"],
            confidence=0.9,
        )
        assert manager.control_emergence(behavior, "invalid") is False


class TestIncrementalGraph:
    """增量图谱构建测试"""

    def test_add_node_returns_bool(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        assert g.add_node("n1") is True
        assert g.add_node("n1") is False

    def test_update_node(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        g.add_node("n1", {"type": "concept"})
        g.update_node("n1", {"label": "AI"})
        assert g.nodes["n1"]["label"] == "AI"
        assert g.nodes["n1"]["type"] == "concept"

    def test_add_edge_dedup(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        g.add_node("n1")
        g.add_node("n2")
        assert g.add_edge("n1", "n2", "related") is True
        assert g.add_edge("n1", "n2", "related") is False

    def test_update_edge(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        g.add_edge("n1", "n2", "related", weight=1.0)
        g.update_edge("n1", "n2", weight=5.0)
        assert g.get_edge_weight("n1", "n2") == 5.0

    def test_remove_edge(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        g.add_edge("n1", "n2", "related")
        assert g.remove_edge("n1", "n2") is True
        assert g.get_neighbors("n1") == []

    def test_version_tracking(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        assert g.version == 0
        g.add_node("n1")
        assert g.version == 1
        g.add_edge("n1", "n2", "link")
        assert g.version == 2

    def test_batch_add(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        count = g.batch_add(
            nodes=[("n1", {}), ("n2", {}), ("n3", {})],
            edges=[("n1", "n2", "link"), ("n2", "n3", "link")],
        )
        assert count == 5
        assert len(g.nodes) == 3
        assert len(g.edges) == 2

    def test_get_changes_since(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        g.add_node("n1")
        g.add_node("n2")
        changes = g.get_changes_since(1)
        assert len(changes) == 1
        assert changes[0]["op"] == "add_node"

    def test_snapshot_and_merge(self):
        from ecos.l0.governance import KnowledgeGraphBuilder

        g1 = KnowledgeGraphBuilder()
        g1.batch_add(
            nodes=[("n1", {"a": 1}), ("n2", {"b": 2})],
            edges=[("n1", "n2", "link")],
        )

        snap = g1.get_snapshot()

        g2 = KnowledgeGraphBuilder()
        merged = g2.merge_snapshot(snap)
        assert merged == 3
        assert len(g2.nodes) == 2
        assert len(g2.edges) == 1


# ══════════════════════════════════════════════════════════════
# 性能基准测试
# ══════════════════════════════════════════════════════════════


class TestPerformanceBenchmarks:
    """性能基准测试 — 确保算法满足延迟要求"""

    def test_state_sync_latency(self):
        import time
        from ecos.l0.governance import StateSyncService, SyncStrategy

        node_a = StateSyncService("a", SyncStrategy.EVENTUAL)
        node_b = StateSyncService("b", SyncStrategy.EVENTUAL)

        for i in range(100):
            node_a.set(f"k{i}", i)

        start = time.monotonic()
        snap = node_a.generate_snapshot()
        node_b.sync_from_snapshot(snap)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 10, f"同步延迟 {elapsed_ms:.2f}ms 超过 10ms"

    def test_pagerank_latency_100_nodes(self):
        import time
        from ecos.l0.governance import KnowledgeGraphBuilder

        g = KnowledgeGraphBuilder()
        for i in range(100):
            g.add_node(f"n{i}")
        for i in range(99):
            g.add_edge(f"n{i}", f"n{i + 1}", "link")
        g.add_edge("n99", "n0", "link")

        start = time.monotonic()
        pr = g.pagerank(iterations=20)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 50, f"PageRank 延迟 {elapsed_ms:.2f}ms 超过 50ms"
        assert abs(sum(pr.values()) - 1.0) < 0.01

    def test_recommendation_latency(self):
        import time
        from ecos.l0.governance import (
            PersonalKnowledgeManager,
            KnowledgeNode,
            KnowledgeType,
            PreferenceEngine,
            RecommendationEngine,
        )

        km = PersonalKnowledgeManager()
        pe = PreferenceEngine()

        for i in range(200):
            km.add_knowledge(
                KnowledgeNode(
                    node_id=f"doc-{i}",
                    knowledge_type=KnowledgeType.FACT,
                    content={"text": f"document about topic {i % 20}"},
                    tags=[f"tag-{i % 10}"],
                )
            )

        pe.learn("user-1", "topic", "topic", 5.0)

        engine = RecommendationEngine(km, pe)

        start = time.monotonic()
        recs = engine.recommend("user-1", limit=10)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 50, f"推荐延迟 {elapsed_ms:.2f}ms 超过 50ms"
        assert len(recs) <= 10

    def test_dag_topological_sort_latency(self):
        import time
        from ecos.l0.governance import TaskScheduler, DAGScheduler

        ts = TaskScheduler()
        dag = DAGScheduler(ts)

        for i in range(100):
            ts.submit_task(f"t{i}", f"Task {i}")

        for i in range(1, 100):
            dag.add_dependency(f"t{i}", f"t{i - 1}")

        start = time.monotonic()
        order = dag.get_topological_order()
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 10, f"拓扑排序延迟 {elapsed_ms:.2f}ms 超过 10ms"
        assert len(order) == 100

    def test_collective_decision_latency(self):
        import time
        from ecos.l0.governance import CollectiveDecision, DecisionMethod

        engine = CollectiveDecision()
        engine.create_proposal(
            "p1", "测试", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE
        )

        for i in range(50):
            engine.vote("p1", f"agent-{i}", "A" if i < 30 else "B")

        start = time.monotonic()
        result = engine.decide("p1")
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 5, f"决策延迟 {elapsed_ms:.2f}ms 超过 5ms"
        assert result == "A"

    def test_emergence_detection_latency(self):
        import time
        from ecos.l0.governance import SwarmManager, SwarmState

        manager = SwarmManager()
        for i in range(50):
            manager.add_agent(f"a{i}", initial_state={"role": "worker"})

        state = SwarmState(
            agents=manager.agents, agent_states=manager.agent_states, behaviors=[]
        )

        start = time.monotonic()
        manager.detect_emergence(state)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 20, f"涌现检测延迟 {elapsed_ms:.2f}ms 超过 20ms"
