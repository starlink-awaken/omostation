"""
Tests for model_driven.toolchain.trigger_registry — Trigger 统一注册管理
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def trigger_m1_dir():
    """创建临时 M1 Trigger 目录并设置 ECOS_WORKSPACE"""
    import os

    import yaml
    d = Path(tempfile.mkdtemp())
    # 创建完整的路径结构
    m1_trigger = d / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"
    m1_trigger.mkdir(parents=True)
    # 设置环境变量让 TriggerRegistry 找到临时目录
    os.environ["ECOS_WORKSPACE"] = str(d)

    triggers = [
        {"id": "TRIGGER-TEST-DAEMON", "type": "trigger", "name": "Test Daemon", "status": "active",
         "domain": "meta", "layer": "L0", "created": "2026-06-09", "version": "1.0.0",
         "properties": {"trigger_type": "daemon", "trigger_source": "test", "trigger_action": "test", "schedule": "every 6h",
                        "dependencies": ["TRIGGER-TEST-EVENTBUS"]}},
        {"id": "TRIGGER-TEST-EVENTBUS", "type": "trigger", "name": "Test EventBus", "status": "active",
         "domain": "meta", "layer": "I0", "created": "2026-06-09", "version": "1.0.0",
         "properties": {"trigger_type": "event_bus", "trigger_source": "test", "trigger_action": "test", "schedule": "on_publish"}},
    ]
    for t in triggers:
        with open(m1_trigger / f"{t['id']}.yaml", "w") as f:
            yaml.dump(t, f)
    return str(d)


class TestTriggerRegistry:
    def test_list_all(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        triggers = registry.list_all()
        assert len(triggers) == 2

    def test_list_by_type(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        daemons = registry.list_all(trigger_type="daemon")
        assert len(daemons) == 1
        assert daemons[0].trigger_type == "daemon"

    def test_list_by_layer(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        l0 = registry.list_all(layer="L0")
        assert len(l0) == 1
        assert l0[0].layer == "L0"

    def test_get_trigger(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        t = registry.get_trigger("TRIGGER-TEST-DAEMON")
        assert t is not None
        assert t.name == "Test Daemon"
        assert t.dependencies == ["TRIGGER-TEST-EVENTBUS"]
        assert registry.get_trigger("nonexistent") is None

    def test_list_types(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        types = registry.list_types()
        assert "daemon" in types
        assert "event_bus" in types

    def test_list_layers(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        layers = registry.list_layers()
        assert "L0" in layers
        assert "I0" in layers

    def test_reload(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        count = registry.reload()
        assert count == 2

    def test_check_health_single(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        result = registry.check_health("TRIGGER-TEST-DAEMON")
        assert "trigger" in result
        assert result["trigger"]["trigger_id"] == "TRIGGER-TEST-DAEMON"

    def test_check_health_all(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        result = registry.check_health()
        assert "summary" in result
        assert "triggers" in result

    def test_run_derivation(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        result = registry.run_derivation()
        assert result["total_rules"] >= 1

    def test_get_dashboard(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        dashboard = registry.get_dashboard()
        assert dashboard["total_triggers"] == 2
        assert "by_type" in dashboard
        assert "dependency_graph" in dashboard
        assert "TRIGGER-TEST-DAEMON" in dashboard["dependency_graph"]

    def test_detect_drift(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        drifts = registry.detect_drift()
        # 无 M0 快照 → 应有 drift
        assert len(drifts) >= 1

    def test_record_execution_and_drift(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        # 记录成功执行
        snap = registry.record_execution("TRIGGER-TEST-DAEMON", success=True)
        assert snap is not None
        assert snap.status == "healthy"
        # 漂移检测应减少
        drifts = registry.detect_drift()
        daemon_drifts = [d for d in drifts if d["trigger_id"] == "TRIGGER-TEST-DAEMON"]
        assert len(daemon_drifts) == 0  # 有 M0 快照且 healthy

    def test_save_m0(self, trigger_m1_dir):
        from model_driven.toolchain.trigger_registry import TriggerRegistry
        registry = TriggerRegistry(m1_dir=str(Path(trigger_m1_dir) / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "trigger"))
        registry.record_execution("TRIGGER-TEST-DAEMON", success=True)
        assert registry.save_m0()
