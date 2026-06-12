"""L0 治理模块测试"""

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
        assert "审计链" in desc


class TestX2StalenessChecker:
    """X2 抗熵检查器测试"""
    
    def test_execute(self, tmp_path):
        # 创建 system.yaml
        omo_dir = tmp_path / ".omo" / "state"
        omo_dir.mkdir(parents=True)
        (omo_dir / "system.yaml").write_text("debt_weight: 1.0\ndebt_health: 100.0\n")
        
        checker = X2StalenessChecker(tmp_path)
        result = checker.execute()
        
        assert result.dimension == "X2"
        assert result.status == CheckStatus.PASS


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
