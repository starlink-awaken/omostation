"""Tests for Workflow Engine — Phase 1 模块化后适配"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


# Mock l0_audit before importing ecos.workflow
l0_audit_mock = MagicMock()
sys.modules["l0_audit"] = l0_audit_mock

from ecos.workflow import (  # noqa: E402
    _execute_step,
    _load_from_m1,
    build_trigger_registry,
    execute_m1_workflow,
    execute_workflow,
    list_backends,
    list_from_m1,
    list_workflows,
    load_workflow,
    match_event,
    register,
    resolve,
    validate_workflow,
)

# ── Fixtures ──

SAMPLE_WF = {
    "name": "test-workflow",
    "description": "A test workflow",
    "steps": [
        {"name": "step-1", "action": "health_check"},
        {"name": "step-2", "action": "domain_validate_all"},
    ],
}

SAMPLE_M1_WF = {
    "type": "Workflow",
    "id": "workflow-test-m1",
    "name": "Test M1 Workflow",
    "domain": "governance",
    "layer": "L0",
    "subtype": "audit",
    "bos_uri": "bos://governance/workflow/test-m1",
    "status": "active",
    "steps": [{"name": "m1-step", "action": "health_check"}],
    "execution": {"on_failure": "abort"},
}

SAMPLE_BACKEND_WF = {
    **SAMPLE_M1_WF,
    "execution": {
        "backend": "test-backend",
        "on_failure": "abort",
    },
}


# =========================================================================
# load_workflow
# =========================================================================

class TestLoadWorkflow:
    @patch("ecos.workflow.loader._load_from_m1")
    @patch("ecos.workflow.loader.open", new_callable=mock_open, read_data="name: from-definition\nsteps: []")
    @patch("ecos.workflow.loader.WF_DIR")
    def test_load_from_definitions(self, mock_wf_dir, mock_file, mock_m1):
        mock_m1.return_value = None
        mock_wf_dir.__truediv__.return_value.exists.return_value = True
        result = load_workflow("test-wf")
        assert result is not None
        assert result["name"] == "from-definition"

    @patch("ecos.workflow.loader._load_from_m1")
    def test_load_from_m1_first(self, mock_m1):
        mock_m1.return_value = {"name": "from-m1", "id": "workflow-test"}
        result = load_workflow("test")
        assert result["name"] == "from-m1"
        mock_m1.assert_called_once_with("test")

    @patch("ecos.workflow.loader._load_from_m1")
    @patch("ecos.workflow.loader.WF_DIR")
    def test_load_not_found(self, mock_wf_dir, mock_m1):
        mock_m1.return_value = None
        mock_wf_dir.__truediv__.return_value.exists.return_value = False
        result = load_workflow("nonexistent")
        assert result is None


# =========================================================================
# _load_from_m1
# =========================================================================

class TestLoadFromM1:
    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_dir_not_exists(self, mock_dir):
        mock_dir.exists.return_value = False
        assert _load_from_m1("test") is None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_match_by_id(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("workflow-test-m1")
            assert result is not None
            assert result["id"] == "workflow-test-m1"

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_match_by_kebab(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("test-m1")
            assert result is not None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_match_by_name(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("Test M1 Workflow")
            assert result is not None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_no_match(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("nonexistent")
            assert result is None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_not_a_workflow_type(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps({"type": "Other"}))):
            result = _load_from_m1("test")
            assert result is None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_parse_error_skipped(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-bad.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data="not valid yaml: {")):
            result = _load_from_m1("test")
            assert result is None


# =========================================================================
# list_workflows
# =========================================================================

class TestListWorkflows:
    @patch("ecos.workflow.loader.M1_WF_DIR")
    @patch("ecos.workflow.loader.WF_DIR")
    def test_no_dirs(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = False
        mock_wf.exists.return_value = False
        assert list_workflows() == []

    @patch("ecos.workflow.loader.M1_WF_DIR")
    @patch("ecos.workflow.loader.WF_DIR")
    def test_lists_m1_workflows(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = True
        mock_m1.glob.return_value = [Path("WORKFLOW-test.yaml")]
        mock_wf.exists.return_value = False
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_workflows()
            assert len(result) == 1
            assert result[0]["source"] == "m1"
            assert result[0]["name"] == "workflow-test-m1"

    @patch("ecos.workflow.loader.M1_WF_DIR")
    @patch("ecos.workflow.loader.WF_DIR")
    def test_dedup(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = True
        mock_m1.glob.return_value = [Path("WORKFLOW-test.yaml")]
        mock_wf.exists.return_value = True
        mock_wf.glob.return_value = [Path("test-m1.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_workflows()
            names = [w["name"] for w in result]
            assert names.count("test-m1") == 1


# =========================================================================
# list_from_m1
# =========================================================================

class TestListFromM1:
    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_no_dir(self, mock_dir):
        mock_dir.exists.return_value = False
        assert list_from_m1() == []

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_lists_workflows(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_from_m1()
            assert len(result) == 1
            assert result[0]["id"] == "workflow-test-m1"
            assert result[0]["domain"] == "governance"
            assert result[0]["steps_count"] == 1

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_skips_non_workflow(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch("ecos.workflow.loader.open", mock_open(read_data=json.dumps({"type": "Other"}))):
            assert list_from_m1() == []


# =========================================================================
# _execute_step
# =========================================================================

class TestExecuteStep:
    @patch("ecos.workflow.executor.subprocess.run")
    def test_health_check_ok(self, mock_run):
        mock_run.return_value.stdout = json.dumps({"results": [{"pass": True}, {"pass": True}]})
        result = _execute_step("health_check")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_health_check_fail(self, mock_run):
        mock_run.return_value.stdout = json.dumps({"results": [{"pass": False}]})
        result = _execute_step("health_check")
        assert result["passed"] is False

    @patch("ecos.workflow.executor.subprocess.run")
    def test_health_check_parse_error(self, mock_run):
        mock_run.return_value.stdout = "not json"
        from unittest.mock import MagicMock
        mock_run.return_value = MagicMock()
        mock_run.return_value.stdout = "not json"
        result = _execute_step("health_check")
        assert result["passed"] is False
        assert "解析失败" in result["summary"]

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_validate_all_ok(self, mock_run):
        mock_run.return_value.stdout = "0❌ all passed"
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_validate_all")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_validate_all_fail(self, mock_run):
        mock_run.return_value.stdout = "3❌ failed"
        mock_run.return_value.returncode = 1
        result = _execute_step("domain_validate_all")
        assert result["passed"] is False

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_audit_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_audit")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_audit_fail(self, mock_run):
        mock_run.return_value.returncode = 1
        result = _execute_step("domain_audit")
        assert result["passed"] is False

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_check_refs_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "✅ 0 个断链"
        result = _execute_step("domain_check_refs")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_sync_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_sync")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_bos_validate_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("bos_validate")
        assert result["passed"] is True

    @patch("ecos.workflow.executor.subprocess.run")
    def test_domain_routes_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_routes")
        assert result["passed"] is True

    def test_unknown_action(self):
        result = _execute_step("nonexistent")
        assert result["passed"] is False
        assert "未知动作" in result["summary"]


# =========================================================================
# execute_workflow (向后兼容)
# =========================================================================

class TestExecuteWorkflow:
    @patch("ecos.workflow.executor.load_workflow")
    def test_workflow_not_found(self, mock_load):
        mock_load.return_value = None
        result = execute_workflow("nonexistent")
        assert "error" in result
        assert "不存在" in result["error"]

    @patch("ecos.workflow.executor.load_workflow")
    def test_workflow_no_steps(self, mock_load):
        mock_load.return_value = {"name": "empty", "steps": []}
        result = execute_workflow("empty")
        assert "error" in result
        assert "无步骤定义" in result["error"]

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor._execute_step")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_dry_run(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        result = execute_workflow("test", dry_run=True)
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["steps"][0]["status"] == "dry_run"
        mock_exec.assert_not_called()

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor._execute_step")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_all_pass(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        mock_exec.return_value = {"passed": True, "summary": "ok"}
        result = execute_workflow("test")
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["source"] == "definition"

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor._execute_step")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_some_fail(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        mock_exec.side_effect = [
            {"passed": True, "summary": "ok"},
            {"passed": False, "summary": "failed"},
        ]
        result = execute_workflow("test")
        assert result["passed"] == 1
        assert result["failed"] == 1

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_step_exception(self, mock_log, mock_load):
        mock_load.return_value = SAMPLE_WF
        with patch("ecos.workflow.executor._execute_step", side_effect=ValueError("boom")):
            result = execute_workflow("test")
            assert result["failed"] == 2

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor._execute_step")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_abort_on_failure(self, mock_log, mock_exec, mock_load):
        wf = {
            "name": "abort-test",
            "steps": [
                {"name": "step-1", "action": "ok", "on_failure": "abort"},
                {"name": "step-2", "action": "never_reached"},
            ],
        }
        mock_load.return_value = wf
        mock_exec.side_effect = ValueError("boom")
        result = execute_workflow("abort-test")
        assert result["failed"] == 1
        assert result["passed"] == 0

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_m1_source(self, mock_log, mock_load):
        m1_wf = {
            "name": "m1-workflow",
            "bos_uri": "bos://governance/test",
            "steps": [{"name": "m1-step", "action": "health_check"}],
        }
        mock_load.return_value = m1_wf
        with patch("ecos.workflow.executor._execute_step", return_value={"passed": True, "summary": "routed"}):
            result = execute_workflow("m1-workflow")
            assert result["source"] == "m1"
            assert result["passed"] == 1


# =========================================================================
# 新功能: execute_m1_workflow + BackendRegistry
# =========================================================================

class TestExecuteM1Workflow:
    @patch("ecos.workflow.executor.load_workflow")
    def test_backend_routing(self, mock_load):
        wf = {**SAMPLE_BACKEND_WF}
        mock_load.return_value = wf
        # 注册一个测试后端
        def _test_backend(m1, params=None):
            return {"passed": True, "summary": "test backend"}
        register("test-backend", "tests.test_workflow", "_test_backend")
        result = execute_m1_workflow("test")
        assert result["source"] == "m1"
        assert result["passed"] >= 0

    @patch("ecos.workflow.executor.load_workflow")
    def test_dry_run(self, mock_load):
        mock_load.return_value = SAMPLE_BACKEND_WF
        result = execute_m1_workflow("test", dry_run=True)
        assert result["source"] == "m1"
        for step in result["steps"]:
            assert step["status"] == "dry_run"


class TestBackendRegistry:
    def test_register_and_list(self):
        register("test-echo", "ecos.workflow.executor", "_execute_step")
        backends = list_backends()
        names = [b["name"] for b in backends]
        assert "test-echo" in names

    def test_resolve_default(self):
        wf = {"execution": {}}
        fn = resolve(wf)
        assert callable(fn)

    def test_resolve_by_name(self):
        register("resolve-test", "ecos.workflow.executor", "_execute_step",
                 description="resolve test")
        wf = {"execution": {"backend": "resolve-test"}}
        fn = resolve(wf)
        assert callable(fn)


# =========================================================================
# 事件监听器
# =========================================================================

class TestEventListener:
    def test_build_trigger_registry(self):
        registry = build_trigger_registry()
        # Should have entries from M1 nodes with triggers
        assert isinstance(registry, dict)

    def test_match_event_exact(self):
        registry = {
            "bos://omo/task/created": ["wf-1"],
            "bos://analysis/query": ["wf-2"],
        }
        matched = match_event({"bos_uri": "bos://omo/task/created"}, registry)
        assert matched == ["wf-1"]

    def test_match_event_prefix(self):
        registry = {
            "bos://memory/*": ["wf-memory"],
        }
        matched = match_event({"bos_uri": "bos://memory/kos/search"}, registry)
        assert matched == ["wf-memory"]

    def test_match_event_no_match(self):
        registry = {"bos://omo/task/created": ["wf-1"]}
        matched = match_event({"bos_uri": "bos://unknown/event"}, registry)
        assert matched == []

    def test_match_event_no_uri(self):
        matched = match_event({"type": "just_a_type"}, {"something": ["wf-1"]})
        assert matched == []

    def test_match_event_from_source_field(self):
        registry = {"bos://omo/drift": ["wf-drift"]}
        matched = match_event({"source": "bos://omo/drift"}, registry)
        assert matched == ["wf-drift"]


class TestValidator:
    def test_validate_workflow_unknown_mode(self):
        violations = validate_workflow({
            "execution": {"mode": "unknown"},
            "steps": [{"name": "s1", "action": "test"}],
        })
        # X1: mode 未知, 步骤通过
        mode_violations = [v for v in violations if v["id"] == "WF-V001"]
        assert len(mode_violations) == 1

    def test_validate_workflow_broken_dep(self):
        violations = validate_workflow({
            "steps": [
                {"name": "step-2", "action": "test", "depends_on": ["step-1"]},
            ],
        })
        dep_violations = [v for v in violations if v["id"] == "WF-V002"]
        assert len(dep_violations) == 1

    def test_validate_workflow_clean(self):
        violations = validate_workflow({
            "execution": {"mode": "workflow"},
            "steps": [
                {"name": "step-1", "action": "test"},
                {"name": "step-2", "action": "test", "depends_on": ["step-1"]},
            ],
        })
        clean = [v for v in violations if v.get("severity") == "error"]
        assert len(clean) == 0
