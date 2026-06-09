"""
Tests for model_driven.toolchain — 模型驱动工具链
"""

from model_driven.toolchain import create_default_bus
from model_driven.toolchain.bus import ToolchainBus, ToolDefinition
from model_driven.toolchain.tools import (
    tool_derive,
    tool_design,
    tool_evolve,
    tool_report,
    tool_validate,
)


class TestToolchainBus:
    def test_register_and_list(self):
        bus = ToolchainBus()
        bus.register("test-tool", lambda: None, ToolDefinition(
            name="test-tool", description="测试工具", category="test",
        ))
        tools = bus.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "test-tool"

    def test_list_by_category(self):
        bus = create_default_bus()
        design_tools = bus.list_tools(category="design")
        assert len(design_tools) == 1
        assert design_tools[0].name == "model-design"

    def test_list_categories(self):
        bus = create_default_bus()
        categories = bus.list_categories()
        assert "design" in categories
        assert "validate" in categories
        assert "derive" in categories

    def test_execute_success(self):
        bus = create_default_bus()
        result = bus.execute("model-design", m2_type="adr", name="测试ADR")
        assert result.success
        assert result.data["success"]

    def test_execute_unknown_tool(self):
        bus = ToolchainBus()
        result = bus.execute("nonexistent")
        assert not result.success
        assert "不存在" in result.message

    def test_execute_history(self):
        bus = create_default_bus()
        bus.execute("model-design", m2_type="adr", name="测试")
        history = bus.get_history()
        assert len(history) == 1

    def test_get_stats(self):
        bus = create_default_bus()
        bus.execute("model-design", m2_type="adr", name="测试")
        stats = bus.get_stats()
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 100.0

    def test_unregister(self):
        bus = create_default_bus()
        assert bus.unregister("model-design")
        assert not bus.unregister("nonexistent")
        tools = bus.list_tools()
        assert len(tools) == 14


class TestDefaultBus:
    def test_all_tools_registered(self):
        bus = create_default_bus()
        tools = bus.list_tools()
        assert len(tools) == 15  # 12 core + 3 MOF

    def test_tool_names(self):
        bus = create_default_bus()
        names = [t.name for t in bus.list_tools()]
        assert "model-design" in names
        assert "model-generate" in names
        assert "model-derive" in names
        assert "model-validate" in names
        assert "model-connect" in names
        assert "model-compile" in names
        assert "model-evolve" in names
        assert "model-monitor" in names
        assert "model-deploy" in names
        assert "model-observe" in names
        assert "model-report" in names
        assert "model-archive" in names
        # MOF tools
        assert "mof-scan" in names
        assert "mof-model" in names
        assert "mof-extract" in names


class TestToolDesign:
    def test_design_valid(self):
        result = tool_design(m2_type="adr", name="测试ADR", properties={
            "context": "测试背景",
            "decision": "测试决策",
            "consequences": "测试后果",
        })
        assert result["success"]
        assert result["node"]["is_valid"]

    def test_design_missing_required(self):
        result = tool_design(m2_type="adr", name="测试ADR")
        assert result["success"]
        assert not result["node"]["is_valid"]
        assert len(result["node"]["missing_required"]) > 0

    def test_design_unknown_type(self):
        result = tool_design(m2_type="unknown_type", name="测试")
        assert not result["success"]


class TestToolValidate:
    def test_validate_valid_model(self):
        model = {
            "id": "ADR-001",
            "type": "adr",
            "status": "proposed",
            "properties": {
                "context": "这是一个背景描述",
                "decision": "这是一个决策",
                "consequences": "这是一个后果",
            },
        }
        result = tool_validate(model=model)
        assert result["passed"], f"Expected passed but got errors: {result.get('errors', [])}"

    def test_validate_invalid_model(self):
        model = {
            "id": "ADR-002",
            "type": "adr",
            "status": "invalid_status",
            "properties": {},
        }
        result = tool_validate(model=model)
        assert not result["passed"]
        assert len(result["errors"]) > 0


class TestToolDerive:
    def test_derive_risks(self):
        models = [
            {"id": "ADR-001", "type": "adr", "properties": {}},
        ]
        result = tool_derive(models=models)
        assert result["success"]
        assert len(result["risks"]) > 0


class TestToolEvolve:
    def test_evolve_drift(self):
        model = {"id": "ADR-001", "status": "proposed"}
        snapshot = {"id": "ADR-001", "status": "accepted"}
        result = tool_evolve(model=model, snapshot=snapshot)
        assert result["drift_detected"]

    def test_evolve_no_drift(self):
        model = {"id": "ADR-001", "status": "proposed"}
        snapshot = {"id": "ADR-001", "status": "proposed"}
        result = tool_evolve(model=model, snapshot=snapshot)
        assert not result["drift_detected"]


class TestToolReport:
    def test_report(self):
        models = [
            {"id": "1", "type": "adr", "stage": "design", "status": "active"},
            {"id": "2", "type": "okr", "stage": "planning", "status": "active"},
            {"id": "3", "type": "adr", "stage": "design", "status": "archived"},
        ]
        result = tool_report(models=models)
        assert result["success"]
        assert result["report"]["total_models"] == 3
        assert result["report"]["by_type"]["adr"] == 2
        assert result["report"]["by_type"]["okr"] == 1
