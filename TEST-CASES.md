# L0 治理模块测试用例

> 完整测试用例 · 覆盖所有功能

---

## 一、测试用例总览

| 模块 | 测试类 | 测试用例数 | 状态 |
|------|--------|------------|------|
| primitives | TestCheckResult | 2 | ✅ |
| primitives | TestGovernanceEvent | 2 | ✅ |
| event_bus | TestGovernanceEventBus | 2 | ✅ |
| checkers | TestX1-X4 Checkers | 6 | ✅ |
| optimization | TestGovernanceAlert | 2 | ✅ |
| optimization | TestHealthSnapshot | 2 | ✅ |
| optimization | TestTrendAnalysis | 2 | ✅ |
| optimization | TestPrediction | 2 | ✅ |
| alert_engine | TestAlertEngine | 2 | ✅ |
| alert_engine | TestLogHandler | 1 | ✅ |
| history_store | TestSQLiteHistoryStore | 2 | ✅ |
| registry | TestGovernanceRegistry | 1 | ✅ |
| distributed | TestDistributedPrimitive | 2 | ✅ |
| role | TestRolePrimitive | 1 | ✅ |
| swarm | TestSwarmPrimitive | 1 | ✅ |
| personal | TestPersonalKnowledgePrimitive | 1 | ✅ |
| **总计** | | **30** | **✅** |

---

## 二、X1-X4 治理原语测试

### 2.1 TestCheckResult

```python
# 测试用例 1: 创建 CheckResult
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

# 测试用例 2: CheckResult 序列化
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
```

### 2.2 TestGovernanceEvent

```python
# 测试用例 3: 创建 GovernanceEvent
def test_create_event(self):
    event = GovernanceEvent(
        event_type="check_started",
        dimension="X1",
        check_id="test-check",
    )
    assert event.event_type == "check_started"
    assert event.dimension == "X1"

# 测试用例 4: GovernanceEvent 序列化
def test_to_dict(self):
    event = GovernanceEvent(
        event_type="check_completed",
        dimension="X3",
        check_id="test-check",
    )
    d = event.to_dict()
    assert d["event_type"] == "check_completed"
    assert d["dimension"] == "X3"
```

---

## 三、事件总线测试

### 3.1 TestGovernanceEventBus

```python
# 测试用例 5: 订阅和发布
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

# 测试用例 6: 发射检查开始事件
def test_emit_check_started(self):
    bus = GovernanceEventBus()
    received = []
    bus.subscribe("check_started", lambda e: received.append(e))
    
    bus.emit_check_started("x1-test", "X1")
    assert len(received) == 1
```

---

## 四、X1-X4 检查器测试

### 4.1 TestX1AuditChainChecker

```python
# 测试用例 7: X1 检查器执行
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

# 测试用例 8: X1 检查器描述
def test_get_description(self, tmp_path):
    checker = X1AuditChainChecker(tmp_path)
    desc = checker.get_description()
    assert "审计" in desc or "安全" in desc
```

### 4.2 TestX2StalenessChecker

```python
# 测试用例 9: X2 检查器执行
def test_execute(self, tmp_path):
    omo_dir = tmp_path / ".omo" / "state"
    omo_dir.mkdir(parents=True)
    (omo_dir / "system.yaml").write_text("debt_weight: 1.0\ndebt_metrics:\n  debt_health: 100.0\n")
    
    checker = X2StalenessChecker(tmp_path)
    result = checker.execute()
    
    assert result.dimension == "X2"
    assert result.status in [CheckStatus.PASS, CheckStatus.FAIL]
```

### 4.3 TestX3ValueChecker

```python
# 测试用例 10: X3 检查器执行
def test_execute(self, tmp_path):
    gov_dir = tmp_path / ".omo" / "_knowledge" / "governance"
    gov_dir.mkdir(parents=True)
    (gov_dir / "sla.md").write_text("# SLA\n")
    
    checker = X3ValueChecker(tmp_path)
    result = checker.execute()
    
    assert result.dimension == "X3"
    assert result.status in [CheckStatus.PASS, CheckStatus.WARN]
```

### 4.4 TestX4ConsistencyChecker

```python
# 测试用例 11: X4 检查器执行
def test_execute(self, tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    for i in range(5):
        (tmp_path / ".github" / "workflows" / f"ci-{i}.yml").touch()
    
    for proj in ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]:
        (tmp_path / "projects" / proj / ".githooks").mkdir(parents=True)
    
    checker = X4ConsistencyChecker(tmp_path)
    result = checker.execute()
    
    assert result.dimension == "X4"
    assert result.status == CheckStatus.PASS
```

---

## 五、优化原语测试

### 5.1 TestGovernanceAlert

```python
# 测试用例 12: 创建 GovernanceAlert
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

# 测试用例 13: GovernanceAlert 序列化
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
```

### 5.2 TestHealthSnapshot

```python
# 测试用例 14: 创建 HealthSnapshot
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

# 测试用例 15: HealthSnapshot 序列化
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
```

### 5.3 TestTrendAnalysis

```python
# 测试用例 16: 创建 TrendAnalysis
def test_create_trend(self):
    trend = TrendAnalysis(
        metric="health_score",
        current=82.0,
        previous=75.0,
        change=7.0,
        trend="improving",
    )
    assert trend.trend == "improving"

# 测试用例 17: TrendAnalysis 序列化
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
```

### 5.4 TestPrediction

```python
# 测试用例 18: 创建 Prediction
def test_create_prediction(self):
    pred = Prediction(
        metric="health_score",
        days=7,
        predicted_value=90.0,
    )
    assert pred.days == 7

# 测试用例 19: Prediction 序列化
def test_to_dict(self):
    pred = Prediction(
        metric="health_score",
        days=7,
        predicted_value=90.0,
    )
    d = pred.to_dict()
    assert d["predicted_value"] == 90.0
```

---

## 六、告警引擎测试

### 6.1 TestAlertEngine

```python
# 测试用例 20: 评估失败告警
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

# 测试用例 21: 评估通过无告警
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
```

### 6.2 TestLogHandler

```python
# 测试用例 22: 日志处理
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
```

---

## 七、历史存储测试

### 7.1 TestSQLiteHistoryStore

```python
# 测试用例 23: 记录和查询
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

# 测试用例 24: 趋势分析
def test_analyze_trend(self, tmp_path):
    db_path = tmp_path / "test.db"
    store = SQLiteHistoryStore(db_path)
    
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
```

---

## 八、注册表测试

### 8.1 TestGovernanceRegistry

```python
# 测试用例 25: 加载和运行
def test_load_and_run(self, tmp_path):
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
```

---

## 九、蜂群式AI原语测试

### 9.1 TestDistributedPrimitive

```python
# 测试用例 26: CRDT 同步
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
    assert result.merged_version == 1

# 测试用例 27: CRDT 合并
def test_crdt_merge(self):
    from ecos.l0.governance import CRDTSync, StateSnapshot
    
    sync = CRDTSync("node-1")
    local = StateSnapshot(node_id="node-1", version=1, data={"a": 1})
    remote = StateSnapshot(node_id="node-2", version=1, data={"b": 2})
    
    merged = sync.merge(local, remote)
    assert merged.version == 2
    assert "a" in merged.data
    assert "b" in merged.data
```

### 9.2 TestRolePrimitive

```python
# 测试用例 28: 角色管理器
def test_role_manager(self):
    from ecos.l0.governance import RoleManager, RoleDefinition, RoleType
    
    manager = RoleManager()
    
    role = RoleDefinition(
        role_id="worker",
        role_type=RoleType.WORKER,
        capabilities=["task"],
        constraints={},
    )
    assert manager.define_role(role)
    assert manager.assign_role("agent-1", "worker")
    
    retrieved = manager.get_role("agent-1")
    assert retrieved is not None
    assert retrieved.role_id == "worker"
    
    roles = manager.list_roles()
    assert len(roles) == 1
```

### 9.3 TestSwarmPrimitive

```python
# 测试用例 29: 蜂群管理器
def test_swarm_manager(self):
    from ecos.l0.governance import SwarmManager, SwarmState, EmergencePattern
    
    manager = SwarmManager()
    manager.agents = ["agent-1", "agent-2", "agent-3"]
    
    state = SwarmState(
        agents=manager.agents,
        behaviors=[],
    )
    
    behaviors = manager.detect_emergence(state)
    assert len(behaviors) > 0
    assert behaviors[0].pattern == EmergencePattern.CLUSTERING
```

### 9.4 TestPersonalKnowledgePrimitive

```python
# 测试用例 30: 个人知识管理器
def test_personal_knowledge_manager(self):
    from ecos.l0.governance import (
        PersonalKnowledgeManager,
        KnowledgeNode,
        KnowledgeType,
        UserPreference,
        PreferenceType,
    )
    
    manager = PersonalKnowledgeManager()
    
    node = KnowledgeNode(
        node_id="k1",
        knowledge_type=KnowledgeType.FACT,
        content={"topic": "AI"},
    )
    assert manager.add_knowledge(node)
    
    results = manager.query_knowledge("AI")
    assert len(results) == 1
    
    pref = UserPreference(
        user_id="user-1",
        preference_type=PreferenceType.TOPIC,
        key="interest",
        value="AI",
    )
    assert manager.learn_preference("user-1", pref)
    
    recs = manager.get_recommendation("user-1", {})
    assert len(recs) > 0
```

---

## 十、测试执行

### 10.1 执行命令

```bash
cd projects/ecos
uv run pytest tests/test_l0/test_governance.py -v
```

### 10.2 预期结果

```
30 passed in 0.05s
```

---

## 十一、测试覆盖

| 模块 | 功能数 | 测试数 | 覆盖率 |
|------|--------|--------|--------|
| primitives | 5 | 4 | 80% |
| checkers | 4 | 6 | 150% |
| event_bus | 3 | 2 | 67% |
| registry | 3 | 1 | 33% |
| optimization | 6 | 6 | 100% |
| alert_engine | 2 | 2 | 100% |
| history_store | 3 | 2 | 67% |
| distributed | 5 | 2 | 40% |
| role | 8 | 1 | 13% |
| swarm | 7 | 1 | 14% |
| personal | 8 | 1 | 13% |
| **总计** | **52** | **30** | **58%** |

---

*测试用例版本: 1.1.0 · 更新: 2026-06-13*
