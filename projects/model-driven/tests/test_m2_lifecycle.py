"""
Tests for model_driven.mof.m2_lifecycle — M2 元模型扩展
"""

import pytest
from model_driven.mof.m2_lifecycle import (
    ALL_M2_SCHEMAS,
    M2Schema,
    get_schema,
    list_all_schema_names,
    list_schemas_by_stage,
)
from model_driven.mof.m3_extended import LifecycleStage


class TestM2SchemaCount:
    def test_total_schemas(self):
        assert len(ALL_M2_SCHEMAS) == 24

    def test_all_schema_names(self):
        names = list_all_schema_names()
        assert "roadmap" in names
        assert "okr" in names
        assert "adr" in names
        assert "spec_design" in names
        assert "code_module" in names
        assert "deployment_config" in names
        assert "runbook" in names
        assert "incident" in names
        assert "user_journey" in names
        assert "cost_model" in names


class TestM2SchemaByStage:
    def test_planning_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.PLANNING)
        names = [s.m2_type for s in schemas]
        assert "roadmap" in names
        assert "okr" in names
        assert "initiative" in names
        assert len(schemas) == 3

    def test_design_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.DESIGN)
        names = [s.m2_type for s in schemas]
        assert "adr" in names
        assert "spec_design" in names
        assert "interface_contract" in names

    def test_development_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.DEVELOPMENT)
        names = [s.m2_type for s in schemas]
        assert "code_module" in names
        assert "test_suite" in names
        assert "ci_pipeline" in names

    def test_deployment_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.DEPLOYMENT)
        names = [s.m2_type for s in schemas]
        assert "deployment_config" in names
        assert "release_plan" in names
        assert "environment" in names

    def test_runtime_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.RUNTIME)
        names = [s.m2_type for s in schemas]
        assert "runbook" in names
        assert "alert_rule" in names
        assert "dashboard_config" in names

    def test_operations_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.OPERATIONS)
        names = [s.m2_type for s in schemas]
        assert "incident" in names
        assert "change_request" in names
        assert "migration_plan" in names

    def test_business_ops_schemas(self):
        schemas = list_schemas_by_stage(LifecycleStage.BUSINESS_OPS)
        names = [s.m2_type for s in schemas]
        assert "user_journey" in names
        assert "value_stream" in names
        assert "feedback" in names


class TestGetSchema:
    def test_get_existing_schema(self):
        schema = get_schema("adr")
        assert schema is not None
        assert schema.m2_type == "adr"
        assert schema.m3_parent == "GovernanceElement.Decision"

    def test_get_nonexistent_schema(self):
        assert get_schema("nonexistent") is None


class TestSchemaValidation:
    def test_all_schemas_have_required_fields(self):
        for name, schema in ALL_M2_SCHEMAS.items():
            assert schema.m2_type != "", f"{name}: m2_type is empty"
            assert schema.m3_parent != "", f"{name}: m3_parent is empty"
            assert schema.description != "", f"{name}: description is empty"

    def test_all_schemas_have_state_machine(self):
        for name, schema in ALL_M2_SCHEMAS.items():
            assert len(schema.state_machine) > 0, f"{name}: state_machine is empty"

    def test_all_schemas_have_terminal_state(self):
        terminal_states = ["archived", "discarded", "rejected"]
        for name, schema in ALL_M2_SCHEMAS.items():
            has_terminal = any(
                ts in schema.state_machine
                for ts in terminal_states
            )
            assert has_terminal, f"{name}: no terminal state found"

    def test_okr_schema(self):
        schema = get_schema("okr")
        assert schema is not None
        assert "objective" in schema.required_properties
        assert "key_results" in schema.required_properties
        assert "deadline" in schema.required_properties
        assert len(schema.validation_rules) >= 2

    def test_incident_schema(self):
        schema = get_schema("incident")
        assert schema is not None
        assert "severity" in schema.required_properties
        assert "description" in schema.required_properties
        assert "detected_at" in schema.required_properties
        assert len(schema.state_machine) >= 5  # 事件有复杂状态机

    def test_adr_schema(self):
        schema = get_schema("adr")
        assert schema is not None
        assert "context" in schema.required_properties
        assert "decision" in schema.required_properties
        assert "consequences" in schema.required_properties
