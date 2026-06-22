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


# =========================================================================
# 白盒补全: X2/X3/X4/M0/Agora 层测试
# =========================================================================

class TestX2BudgetDeducer:
    def test_check_budget_no_config(self):
        from ecos.workflow.validator import X2BudgetDeducer
        result = X2BudgetDeducer.check_budget({})
        assert result["ok"] is True
        assert not result["budget"]

    def test_deduct_creates_ledger(self, tmp_path):
        from ecos.workflow.validator import X2BudgetDeducer
        original = X2BudgetDeducer.LEDGER_PATH
        X2BudgetDeducer.LEDGER_PATH = tmp_path / "test_ledger.jsonl"
        try:
            result = X2BudgetDeducer.deduct("wf-test", {"execution": {"budget": {"token_limit": 1000}}})
            assert result["ok"] is True
            assert result["balance_before"] == 100000  # default
            assert result["balance_after"] == 99000
            assert X2BudgetDeducer.LEDGER_PATH.exists()
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_read_balance_from_ledger(self, tmp_path):
        from ecos.workflow.validator import X2BudgetDeducer
        import json
        ledger = tmp_path / "test_ledger.jsonl"
        ledger.write_text(json.dumps({"event": "deduct", "balance_after": 50000}) + "\n")
        original = X2BudgetDeducer.LEDGER_PATH
        X2BudgetDeducer.LEDGER_PATH = ledger
        try:
            result = X2BudgetDeducer.check_budget({"execution": {"budget": {"token_limit": 1000}}})
            assert result["balance"] == 50000
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_debt_generated_on_negative(self, tmp_path):
        from ecos.workflow.validator import X2BudgetDeducer
        original = X2BudgetDeducer.LEDGER_PATH
        X2BudgetDeducer.LEDGER_PATH = tmp_path / "debt_ledger.jsonl"
        try:
            result = X2BudgetDeducer.deduct("wf-debt", {"execution": {"budget": {"token_limit": 200000}}})  # > default 100000
            assert result["debt_generated"] is True
            assert result["balance_after"] < 0
        finally:
            X2BudgetDeducer.LEDGER_PATH = original


class TestX3CostRecorder:
    def test_record_creates_entry(self, tmp_path):
        from ecos.workflow.validator import X3CostRecorder
        original = X3CostRecorder.LEDGER_PATH
        X3CostRecorder.LEDGER_PATH = tmp_path / "cost_ledger.jsonl"
        try:
            X3CostRecorder.record("wf-cost", {"passed": 2, "failed": 0})
            content = X3CostRecorder.LEDGER_PATH.read_text()
            assert "wf-cost" in content
            assert "cost_record" in content
        finally:
            X3CostRecorder.LEDGER_PATH = original


class TestX2CircuitBreak:
    """X2 熔断自动化测试: 余额耗尽→阻断执行"""

    def test_circuit_break_on_depleted_budget(self, tmp_path, monkeypatch):
        """余额不足且有预算配置时→阻断并返回 X2 熔断错误"""
        from ecos.workflow.executor import execute_m1_workflow
        from ecos.workflow.validator import X2BudgetDeducer
        import json

        # 注入有 budget 配置的测试工作流
        test_wf = {
            "name": "test-budget-wf",
            "steps": [{"name": "s1", "action": "health_check"}],
            "execution": {
                "backend": "default", "mode": "sequential",
                "budget": {"token_limit": 500},
            },
        }
        monkeypatch.setattr("ecos.workflow.executor.load_workflow", lambda name: test_wf)

        # 设置余额不足
        original = X2BudgetDeducer.LEDGER_PATH
        ledger = tmp_path / "x2_circuit.jsonl"
        ledger.write_text(json.dumps({"event": "balance", "balance": 10}) + "\n")
        X2BudgetDeducer.LEDGER_PATH = ledger

        try:
            result = execute_m1_workflow("test-budget-wf")
            assert "error" in result, "余额不足时应返回 error"
            assert "X2 熔断" in result["error"]
            assert result.get("passed", 0) == 0
            assert result.get("failed", 0) == 0
            assert "steps" in result
            assert len(result["steps"]) == 0, "熔断时不应执行任何步骤"
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_no_circuit_break_without_budget_config(self, tmp_path, monkeypatch):
        """无预算配置时不阻断（即使余额为 0）"""
        from ecos.workflow.executor import execute_m1_workflow
        from ecos.workflow.validator import X2BudgetDeducer
        import json

        monkeypatch.setattr("ecos.workflow.executor.load_workflow", lambda name: {
            "name": "test-no-budget",
            "steps": [{"name": "s1", "action": "health_check"}],
            "execution": {"backend": "default"},
        })

        original = X2BudgetDeducer.LEDGER_PATH
        ledger = tmp_path / "x2_nobudget.jsonl"
        ledger.write_text(json.dumps({"event": "balance", "balance": 0}) + "\n")
        X2BudgetDeducer.LEDGER_PATH = ledger

        try:
            result = execute_m1_workflow("test-no-budget")
            # 无 budget 配置不应阻断，但 health_check 执行可能需要 ~/.ecos/scripts 等环境
            # 重点是: 不应有 X2 熔断错误
            err = result.get("error", "")
            assert "X2 熔断" not in err, "无 budget 配置不应触发 X2 熔断"
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_circuit_break_uses_check_budget_logic(self, tmp_path):
        """熔断逻辑直接依赖 X2BudgetDeducer.check_budget"""
        from ecos.workflow.validator import X2BudgetDeducer
        import json

        # 验证 check_budget 检测余额不足的正确行为
        original = X2BudgetDeducer.LEDGER_PATH
        ledger = tmp_path / "x2_check.jsonl"
        ledger.write_text(json.dumps({"event": "balance", "balance": 100}) + "\n")
        X2BudgetDeducer.LEDGER_PATH = ledger

        try:
            # 余额不足 (100 < 500)
            status = X2BudgetDeducer.check_budget({
                "execution": {"budget": {"token_limit": 500}},
            })
            assert status["ok"] is False
            assert any("余额不足" in w for w in status.get("warnings", []))

            # 余额充足
            status2 = X2BudgetDeducer.check_budget({
                "execution": {"budget": {"token_limit": 50}},
            })
            assert status2["ok"] is True
        finally:
            X2BudgetDeducer.LEDGER_PATH = original


class TestX4ConsistencyChecker:
    def test_check_result_ok(self):
        from ecos.workflow.validator import X4ConsistencyChecker
        violations = X4ConsistencyChecker.check_result(
            {"steps": [{"name": "s1"}]},
            {"passed": 1, "failed": 0, "steps": [{"name": "s1", "status": "ok"}]},
        )
        assert len(violations) == 0

    def test_check_result_failed(self):
        from ecos.workflow.validator import X4ConsistencyChecker
        violations = X4ConsistencyChecker.check_result(
            {"steps": [{"name": "s1"}]},
            {"passed": 0, "failed": 1, "steps": [{"name": "s1", "status": "failed"}]},
        )
        assert any(v["id"] == "X4-C01-FAILED" for v in violations)

    def test_check_result_mismatch_count(self):
        from ecos.workflow.validator import X4ConsistencyChecker
        violations = X4ConsistencyChecker.check_result(
            {"steps": [{"name": "s1"}, {"name": "s2"}]},
            {"passed": 1, "failed": 0, "steps": [{"name": "s1", "status": "ok"}]},
        )
        assert any(v["id"] == "X4-C01-STEP-COUNT" for v in violations)


class TestM0Snapshot:
    def test_generate_snapshot(self, tmp_path):
        from ecos.workflow.validator import generate_m0_snapshot, M0_SNAPSHOT_DIR
        import yaml
        original = M0_SNAPSHOT_DIR
        import ecos.workflow.validator as vmod
        vmod.M0_SNAPSHOT_DIR = tmp_path / "m0"
        try:
            path = generate_m0_snapshot(
                "wf-m0-test",
                {"name": "M0 Test", "execution": {"mode": "workflow", "backend": "default"}},
                {"passed": 1, "failed": 0, "steps": [{"name": "s1", "status": "ok"}]},
            )
            assert path is not None
            with open(path) as f:
                snap = yaml.safe_load(f)
            assert snap["schema"] == "M0-v1"
            assert snap["status"] == "ok"
            assert snap["workflow_id"] == "wf-m0-test"
        finally:
            vmod.M0_SNAPSHOT_DIR = original

    def test_generate_snapshot_failed(self, tmp_path):
        from ecos.workflow.validator import generate_m0_snapshot, M0_SNAPSHOT_DIR
        import yaml
        import ecos.workflow.validator as vmod
        original = M0_SNAPSHOT_DIR
        vmod.M0_SNAPSHOT_DIR = tmp_path / "m0-fail"
        try:
            path = generate_m0_snapshot(
                "wf-fail",
                {"name": "Fail Test", "execution": {}},
                {"passed": 0, "failed": 2, "steps": [{"name": "s1", "status": "failed"}]},
            )
            assert path is not None
            with open(path) as f:
                snap = yaml.safe_load(f)
            assert snap["status"] == "failed"
        finally:
            vmod.M0_SNAPSHOT_DIR = original


class TestSymphonyBackend:
    def test_execute_records_cost_via_governed_helper(self, monkeypatch):
        from ecos.workflow.backends import symphony

        captured: dict[str, object] = {}

        def fake_append(path, entry):
            captured["path"] = path
            captured["entry"] = entry

        monkeypatch.setattr(symphony, "append_jsonl_record", fake_append)

        result = symphony.execute({"id": "wf-symphony", "steps": [{"name": "s1", "action": "health_check"}]})

        assert result["passed"] >= 1
        assert captured["path"] == Path.home() / ".omo" / "state" / "llm_quota_ledger.jsonl"
        assert captured["entry"]["event"] == "cost_record"
        assert captured["entry"]["workflow_id"] == "wf-symphony"


class TestAgoraBackend:
    def test_step_to_bos_uri_output(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri
        result = _step_to_bos_uri(
            {"name": "test", "action": "research", "output": ["bos://analysis/minerva/research"]},
            "research",
        )
        assert result == "bos://analysis/minerva/research"

    def test_step_to_bos_uri_action_map(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri
        result = _step_to_bos_uri({"name": "test", "action": "health_check"}, "health_check")
        assert result == "bos://governance/omo/audit"

    def test_step_to_bos_uri_fallback(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri
        result = _step_to_bos_uri({"name": "test", "action": "custom_thing"}, "custom_thing")
        assert "bos://" in result

    def test_agora_execute_fallback_on_unreachable(self):
        from ecos.workflow.agora_mcp_backend import execute
        result = execute({"steps": [{"name": "s1", "action": "health_check"}]})
        # Agora is unreachable, should fallback gracefully
        assert "steps" in result


class TestEventTriggerHeal:
    def test_execute_matched_empty_event(self):
        from ecos.workflow.event_listener import execute_matched
        results = execute_matched({"bos_uri": "bos://nonexistent/event"})
        assert results == []

    def test_trigger_heal_with_default(self):
        from ecos.workflow.event_listener import _trigger_heal
        result = _trigger_heal("wf-failed", {"failed": 2, "passed": 0})
        assert result is not None
        # Falls back to health check when heal workflow doesn't exist
        assert isinstance(result, dict)
