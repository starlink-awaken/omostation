"""Tests for Workflow Engine."""

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
    execute_workflow,
    list_from_m1,
    list_workflows,
    load_workflow,
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


# ── load_workflow ──

class TestLoadWorkflow:
    @patch("ecos.workflow._load_from_m1")
    @patch("ecos.workflow.open", new_callable=mock_open, read_data="name: from-definition\nsteps: []")
    @patch("ecos.workflow.WF_DIR")
    def test_load_from_definitions(self, mock_wf_dir, mock_file, mock_m1):
        mock_m1.return_value = None
        mock_wf_dir.__truediv__.return_value.exists.return_value = True
        result = load_workflow("test-wf")
        assert result is not None
        assert result["name"] == "from-definition"

    @patch("ecos.workflow._load_from_m1")
    def test_load_from_m1_first(self, mock_m1):
        mock_m1.return_value = {"name": "from-m1", "id": "workflow-test"}
        result = load_workflow("test")
        assert result["name"] == "from-m1"
        mock_m1.assert_called_once_with("test")

    @patch("ecos.workflow._load_from_m1")
    @patch("ecos.workflow.WF_DIR", new_callable=MagicMock)
    def test_load_not_found(self, mock_wf_dir, mock_m1):
        mock_m1.return_value = None
        mock_wf_dir.__truediv__.return_value.exists.return_value = False
        result = load_workflow("nonexistent")
        assert result is None


# ── _load_from_m1 ──

class TestLoadFromM1:
    @patch("ecos.workflow.M1_WF_DIR")
    def test_dir_not_exists(self, mock_dir):
        mock_dir.exists.return_value = False
        assert _load_from_m1("test") is None

    @patch("ecos.workflow.M1_WF_DIR")
    def test_match_by_id(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("workflow-test-m1")
            assert result is not None
            assert result["id"] == "workflow-test-m1"

    @patch("ecos.workflow.M1_WF_DIR")
    def test_match_by_kebab(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("test-m1")
            assert result is not None

    @patch("ecos.workflow.M1_WF_DIR")
    def test_match_by_name(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("Test M1 Workflow")
            assert result is not None

    @patch("ecos.workflow.M1_WF_DIR")
    def test_no_match(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = _load_from_m1("nonexistent")
            assert result is None

    @patch("ecos.workflow.M1_WF_DIR")
    def test_not_a_workflow_type(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps({"type": "Other"}))):
            result = _load_from_m1("test")
            assert result is None

    @patch("ecos.workflow.M1_WF_DIR")
    def test_parse_error_skipped(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-bad.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data="not valid yaml: {")):
            result = _load_from_m1("test")
            assert result is None


# ── list_workflows ──

class TestListWorkflows:
    @patch("ecos.workflow.M1_WF_DIR")
    @patch("ecos.workflow.WF_DIR")
    def test_no_dirs(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = False
        mock_wf.exists.return_value = False
        assert list_workflows() == []

    @patch("ecos.workflow.M1_WF_DIR")
    @patch("ecos.workflow.WF_DIR")
    def test_lists_m1_workflows(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = True
        mock_m1.glob.return_value = [Path("WORKFLOW-test.yaml")]
        mock_wf.exists.return_value = False
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_workflows()
            assert len(result) == 1
            assert result[0]["source"] == "m1"
            assert result[0]["name"] == "workflow-test-m1"

    @patch("ecos.workflow.M1_WF_DIR")
    @patch("ecos.workflow.WF_DIR")
    def test_dedup(self, mock_wf, mock_m1):
        mock_m1.exists.return_value = True
        mock_m1.glob.return_value = [Path("WORKFLOW-test.yaml")]
        mock_wf.exists.return_value = True
        mock_wf.glob.return_value = [Path("test-m1.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_workflows()
            # Should only appear once (M1 takes priority)
            names = [w["name"] for w in result]
            assert names.count("test-m1") == 1


# ── list_from_m1 ──

class TestListFromM1:
    @patch("ecos.workflow.M1_WF_DIR")
    def test_no_dir(self, mock_dir):
        mock_dir.exists.return_value = False
        assert list_from_m1() == []

    @patch("ecos.workflow.M1_WF_DIR")
    def test_lists_workflows(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))):
            result = list_from_m1()
            assert len(result) == 1
            assert result[0]["id"] == "workflow-test-m1"
            assert result[0]["domain"] == "governance"
            assert result[0]["steps_count"] == 1

    @patch("ecos.workflow.M1_WF_DIR")
    def test_skips_non_workflow(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch("ecos.workflow.open", mock_open(read_data=json.dumps({"type": "Other"}))):
            assert list_from_m1() == []


# ── _execute_step ──

class TestExecuteStep:
    @patch("ecos.workflow.subprocess.run")
    def test_health_check_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"results": [{"pass": True}, {"pass": True}]})
        mock_run.return_value = mock_result
        result = _execute_step("health_check")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_health_check_fail(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"results": [{"pass": False}]})
        mock_run.return_value = mock_result
        result = _execute_step("health_check")
        assert result["passed"] is False

    @patch("ecos.workflow.subprocess.run")
    def test_health_check_parse_error(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "not json"
        mock_run.return_value = mock_result
        result = _execute_step("health_check")
        assert result["passed"] is False
        assert "解析失败" in result["summary"]

    @patch("ecos.workflow.subprocess.run")
    def test_domain_validate_all_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "0❌ all passed"
        mock_run.return_value = mock_result
        result = _execute_step("domain_validate_all")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_domain_validate_all_fail(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "3❌ failed"
        mock_run.return_value = mock_result
        result = _execute_step("domain_validate_all")
        assert result["passed"] is False

    @patch("ecos.workflow.subprocess.run")
    def test_domain_audit_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = _execute_step("domain_audit")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_domain_audit_fail(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        result = _execute_step("domain_audit")
        assert result["passed"] is False

    @patch("ecos.workflow.subprocess.run")
    def test_domain_check_refs_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✅ 0 个断链"
        mock_run.return_value = mock_result
        result = _execute_step("domain_check_refs")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_domain_sync_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = _execute_step("domain_sync")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_bos_validate_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = _execute_step("bos_validate")
        assert result["passed"] is True

    @patch("ecos.workflow.subprocess.run")
    def test_domain_routes_ok(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = _execute_step("domain_routes")
        assert result["passed"] is True

    def test_unknown_action(self):
        result = _execute_step("nonexistent")
        assert result["passed"] is False
        assert "未知动作" in result["summary"]


# ── execute_workflow ──

class TestExecuteWorkflow:
    @patch("ecos.workflow.load_workflow")
    def test_workflow_not_found(self, mock_load):
        mock_load.return_value = None
        result = execute_workflow("nonexistent")
        assert "error" in result
        assert "不存在" in result["error"]

    @patch("ecos.workflow.load_workflow")
    def test_workflow_no_steps(self, mock_load):
        mock_load.return_value = {"name": "empty", "steps": []}
        result = execute_workflow("empty")
        assert "error" in result
        assert "无步骤定义" in result["error"]

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow._execute_step")
    @patch("ecos.workflow.log_operation")
    def test_workflow_dry_run(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        result = execute_workflow("test", dry_run=True)
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["steps"][0]["status"] == "dry_run"
        mock_exec.assert_not_called()

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow._execute_step")
    @patch("ecos.workflow.log_operation")
    def test_workflow_all_pass(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        mock_exec.return_value = {"passed": True, "summary": "ok"}
        result = execute_workflow("test")
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["source"] == "definition"

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow._execute_step")
    @patch("ecos.workflow.log_operation")
    def test_workflow_some_fail(self, mock_log, mock_exec, mock_load):
        mock_load.return_value = SAMPLE_WF
        mock_exec.side_effect = [
            {"passed": True, "summary": "ok"},
            {"passed": False, "summary": "failed"},
        ]
        result = execute_workflow("test")
        assert result["passed"] == 1
        assert result["failed"] == 1

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow.log_operation")
    def test_workflow_step_exception(self, mock_log, mock_load):
        mock_load.return_value = SAMPLE_WF
        with patch("ecos.workflow._execute_step", side_effect=ValueError("boom")):
            result = execute_workflow("test")
            assert result["failed"] == 2  # both steps fail

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow._execute_step")
    @patch("ecos.workflow.log_operation")
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
        assert result["failed"] == 1  # only first step counted
        assert result["passed"] == 0

    @patch("ecos.workflow.load_workflow")
    @patch("ecos.workflow.log_operation")
    def test_workflow_m1_source(self, mock_log, mock_load):
        m1_wf = {
            "name": "m1-workflow",
            "bos_uri": "bos://governance/test",
            "steps": [{"name": "m1-step", "action": "health_check"}],
        }
        mock_load.return_value = m1_wf
        with patch("ecos.workflow._execute_step", return_value={"passed": True, "summary": "routed"}):
            result = execute_workflow("m1-workflow")
            assert result["source"] == "m1"
            assert result["passed"] == 1
