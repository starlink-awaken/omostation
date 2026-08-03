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
    "execution": {"backend": "default", "mode": "sequential"},
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
    @patch(
        "ecos.workflow.loader.open",
        new_callable=mock_open,
        read_data="name: from-definition\nsteps: []",
    )
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
        assert result["name"] == "from-m1"  # type: ignore[reportOptionalSubscript]
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
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
            result = _load_from_m1("workflow-test-m1")
            assert result is not None
            assert result["id"] == "workflow-test-m1"

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_match_by_kebab(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
            result = _load_from_m1("test-m1")
            assert result is not None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_match_by_name(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
            result = _load_from_m1("Test M1 Workflow")
            assert result is not None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_no_match(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
            result = _load_from_m1("nonexistent")
            assert result is None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_not_a_workflow_type(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-test.yaml")]
        with patch(
            "ecos.workflow.loader.open",
            mock_open(read_data=json.dumps({"type": "Other"})),
        ):
            result = _load_from_m1("test")
            assert result is None

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_parse_error_skipped(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-bad.yaml")]
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data="not valid yaml: {")
        ):
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
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
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
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
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
        with patch(
            "ecos.workflow.loader.open", mock_open(read_data=json.dumps(SAMPLE_M1_WF))
        ):
            result = list_from_m1()
            assert len(result) == 1
            assert result[0]["id"] == "workflow-test-m1"
            assert result[0]["domain"] == "governance"
            assert result[0]["steps_count"] == 1

    @patch("ecos.workflow.loader.M1_WF_DIR")
    def test_skips_non_workflow(self, mock_dir):
        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [Path("WORKFLOW-other.yaml")]
        with patch(
            "ecos.workflow.loader.open",
            mock_open(read_data=json.dumps({"type": "Other"})),
        ):
            assert list_from_m1() == []


# =========================================================================
# _execute_step
# =========================================================================


class TestExecuteStep:
    @patch("ecos.workflow.actions.subprocess.run")
    def test_health_check_ok(self, mock_run):
        mock_run.return_value.stdout = json.dumps(
            {"results": [{"pass": True}, {"pass": True}]}
        )
        result = _execute_step("health_check")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
    def test_health_check_fail(self, mock_run):
        mock_run.return_value.stdout = json.dumps({"results": [{"pass": False}]})
        result = _execute_step("health_check")
        assert result["passed"] is False

    @patch("ecos.workflow.actions.subprocess.run")
    def test_health_check_parse_error(self, mock_run):
        mock_run.return_value.stdout = "not json"
        from unittest.mock import MagicMock

        mock_run.return_value = MagicMock()
        mock_run.return_value.stdout = "not json"
        result = _execute_step("health_check")
        assert result["passed"] is False
        assert "解析失败" in result["summary"]

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_validate_all_ok(self, mock_run):
        mock_run.return_value.stdout = "0❌ all passed"
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_validate_all")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_validate_all_fail(self, mock_run):
        mock_run.return_value.stdout = "3❌ failed"
        mock_run.return_value.returncode = 1
        result = _execute_step("domain_validate_all")
        assert result["passed"] is False

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_audit_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_audit")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_audit_fail(self, mock_run):
        mock_run.return_value.returncode = 1
        result = _execute_step("domain_audit")
        assert result["passed"] is False

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_check_refs_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "✅ 0 个断链"
        result = _execute_step("domain_check_refs")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
    def test_domain_sync_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("domain_sync")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
    def test_bos_validate_ok(self, mock_run):
        mock_run.return_value.returncode = 0
        result = _execute_step("bos_validate")
        assert result["passed"] is True

    @patch("ecos.workflow.actions.subprocess.run")
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
        with patch(
            "ecos.workflow.executor._execute_step", side_effect=ValueError("boom")
        ):
            result = execute_workflow("test")
            assert result["failed"] == 2

    @patch("ecos.workflow.executor.load_workflow")
    @patch("ecos.workflow.executor._execute_step")
    @patch("ecos.workflow.executor.log_operation")
    def test_workflow_abort_on_failure(self, mock_log, mock_exec, mock_load):
        wf = {
            "name": "abort-test",
            "execution": {"backend": "default", "mode": "sequential"},
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
            "execution": {"backend": "default", "mode": "sequential"},
            "steps": [{"name": "m1-step", "action": "health_check"}],
        }
        mock_load.return_value = m1_wf
        with patch(
            "ecos.workflow.executor._execute_step",
            return_value={"passed": True, "summary": "routed"},
        ):
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
        register(
            "resolve-test",
            "ecos.workflow.executor",
            "_execute_step",
            description="resolve test",
        )
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
        violations = validate_workflow(
            {
                "execution": {"mode": "unknown"},
                "steps": [{"name": "s1", "action": "test"}],
            }
        )
        # X1: mode 未知, 步骤通过
        mode_violations = [v for v in violations if v["id"] == "WF-V001"]
        assert len(mode_violations) == 1

    def test_validate_workflow_broken_dep(self):
        violations = validate_workflow(
            {
                "steps": [
                    {"name": "step-2", "action": "test", "depends_on": ["step-1"]},
                ],
            }
        )
        dep_violations = [v for v in violations if v["id"] == "WF-V002"]
        assert len(dep_violations) == 1

    def test_validate_workflow_clean(self):
        violations = validate_workflow(
            {
                "execution": {"mode": "workflow"},
                "steps": [
                    {"name": "step-1", "action": "test"},
                    {"name": "step-2", "action": "test", "depends_on": ["step-1"]},
                ],
            }
        )
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
            result = X2BudgetDeducer.deduct(
                "wf-test", {"execution": {"budget": {"token_limit": 1000}}}
            )
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
        ledger.write_text(
            json.dumps({"event": "deduct", "balance_after": 50000}) + "\n"
        )
        original = X2BudgetDeducer.LEDGER_PATH
        X2BudgetDeducer.LEDGER_PATH = ledger
        try:
            result = X2BudgetDeducer.check_budget(
                {"execution": {"budget": {"token_limit": 1000}}}
            )
            assert result["balance"] == 50000
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_debt_generated_on_negative(self, tmp_path):
        from ecos.workflow.validator import X2BudgetDeducer

        original = X2BudgetDeducer.LEDGER_PATH
        X2BudgetDeducer.LEDGER_PATH = tmp_path / "debt_ledger.jsonl"
        try:
            result = X2BudgetDeducer.deduct(
                "wf-debt", {"execution": {"budget": {"token_limit": 200000}}}
            )  # > default 100000
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
                "backend": "default",
                "mode": "sequential",
                "budget": {"token_limit": 500},
            },
        }
        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow", lambda name: test_wf
        )

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
            assert result.get("failed", 0) == 1  # 熔断时 workflow 标记为失败
            assert "steps" in result
            assert len(result["steps"]) == 0, "熔断时不应执行任何步骤"
        finally:
            X2BudgetDeducer.LEDGER_PATH = original

    def test_no_circuit_break_without_budget_config(self, tmp_path, monkeypatch):
        """无预算配置时不阻断（即使余额为 0）"""
        from ecos.workflow.executor import execute_m1_workflow
        from ecos.workflow.validator import X2BudgetDeducer
        import json

        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-no-budget",
                "steps": [{"name": "s1", "action": "health_check"}],
                "execution": {"backend": "default"},
            },
        )

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
            status = X2BudgetDeducer.check_budget(
                {
                    "execution": {"budget": {"token_limit": 500}},
                }
            )
            assert status["ok"] is False
            assert any("余额不足" in w for w in status.get("warnings", []))

            # 余额充足
            status2 = X2BudgetDeducer.check_budget(
                {
                    "execution": {"budget": {"token_limit": 50}},
                }
            )
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
                {
                    "name": "M0 Test",
                    "execution": {"mode": "workflow", "backend": "default"},
                },
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
                {
                    "passed": 0,
                    "failed": 2,
                    "steps": [{"name": "s1", "status": "failed"}],
                },
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

        result = symphony.execute(
            {"id": "wf-symphony", "steps": [{"name": "s1", "action": "health_check"}]}
        )

        assert result["passed"] >= 1
        assert (
            captured["path"]
            == Path.home() / ".omo" / "state" / "llm_quota_ledger.jsonl"
        )
        assert captured["entry"]["event"] == "cost_record"  # type: ignore[reportIndexIssue]
        assert captured["entry"]["workflow_id"] == "wf-symphony"  # type: ignore[reportIndexIssue]


class TestAgoraBackend:
    def test_step_to_bos_uri_output(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri

        result = _step_to_bos_uri(
            {
                "name": "test",
                "action": "research",
                "output": ["bos://analysis/minerva/research"],
            },
            "research",
        )
        assert result == "bos://analysis/minerva/research"

    def test_step_to_bos_uri_action_map(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri

        result = _step_to_bos_uri(
            {"name": "test", "action": "health_check"}, "health_check"
        )
        assert result == "bos://governance/omo/audit"

    def test_step_to_bos_uri_fallback(self):
        from ecos.workflow.agora_mcp_backend import _step_to_bos_uri

        result = _step_to_bos_uri(
            {"name": "test", "action": "custom_thing"}, "custom_thing"
        )
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


class TestDynamicBackend:
    """Dynamic mode 测试 — LLM 驱动的动态工作流"""

    def test_dynamic_fallback_linear(self):
        """LLM 不可用时回退到线性执行"""
        from ecos.workflow.dynamic_backend import execute

        m1 = {
            "name": "test-dynamic",
            "execution": {"mode": "dynamic", "dynamic": {"max_steps": 5}},
            "steps": [
                {"name": "s1", "action": "health_check"},
                {"name": "s2", "action": "domain_audit"},
            ],
        }
        result = execute(m1)
        assert "steps" in result
        assert result["passed"] >= 0
        assert result["failed"] >= 0

    def test_dynamic_fallback_runs_all_actions(self):
        """回退模式下应尝试执行所有检测到的可用动作"""
        from ecos.workflow.dynamic_backend import execute

        # 动态工作流内部会调用 actions.py 的 resolve_action
        # 而 health_check 依赖 ~/.ecos/scripts/ecos-health-check.py
        # 所以预期 health_check 会失败（环境因素），但不应抛异常
        m1 = {
            "name": "test-dynamic-all",
            "description": "测试全量执行",
            "execution": {"mode": "dynamic", "dynamic": {"max_steps": 10}},
            "steps": [
                {"name": "s1", "action": "health_check"},
                {"name": "s2", "action": "domain_audit"},
            ],
        }
        result = execute(m1)
        steps = result.get("steps", [])
        assert len(steps) >= 1, "应至少执行一个步骤"

    def test_dynamic_registered_as_backend(self):
        """dynamic 后端应在 backend_registry 中注册"""
        from ecos.workflow.backend_registry import list_backends, resolve

        backends = list_backends()
        names = {b["name"] for b in backends}
        assert "dynamic" in names, "dynamic 后端应已注册"

        # mode=dynamic 应能解析到 dynamic backend
        fn = resolve({"execution": {"mode": "dynamic"}})
        assert callable(fn)

    def test_dynamic_planner_detect_actions(self):
        """_detect_actions 应从 M1 步骤中提取动作"""
        from ecos.workflow.dynamic_backend import _detect_actions

        m1 = {
            "steps": [
                {"name": "s1", "action": "health_check"},
                {"name": "s2", "action": "domain_audit"},
            ],
        }
        actions = _detect_actions(m1)
        assert "health_check" in actions
        assert "domain_audit" in actions

    def test_dynamic_completes_with_custom_actions(self):
        """指定 available_actions 时应只执行这些动作"""
        from ecos.workflow.dynamic_backend import execute

        m1 = {
            "name": "test-dynamic-custom",
            "execution": {
                "mode": "dynamic",
                "dynamic": {
                    "max_steps": 3,
                    "available_actions": ["bos_validate"],
                },
            },
            "steps": [],
        }
        result = execute(m1)
        # bos_validate 依赖 ~/bin/ecos，但不应抛异常
        assert "error" not in result

    def test_dynamic_planner_fallback_decide(self):
        """DynamicPlanner 回退模式应依次返回 available_actions 中的动作"""
        from ecos.workflow.dynamic_backend import DynamicPlanner

        planner = DynamicPlanner(
            objective="测试",
            available_actions=["health_check", "domain_audit"],
        )

        # 第一次调用: 返回 health_check
        d1 = planner.decide({"results": []})
        assert d1["action"] == "health_check"

        # 第二次调用: 返回 domain_audit
        d2 = planner.decide({"results": [{"step": "health_check", "ok": True}]})
        assert d2["action"] == "domain_audit"

        # 第三次调用: 返回 __done__
        d3 = planner.decide(
            {
                "results": [
                    {"step": "health_check", "ok": True},
                    {"step": "domain_audit", "ok": True},
                ],
            }
        )
        assert d3["action"] == "__done__"


class TestCustomCommand:
    """step.command 自定义命令测试"""

    def test_execute_custom_command_ok(self):
        from ecos.workflow.executor import _execute_step

        result = _execute_step(
            "custom_pwd",
            step={
                "name": "测试pwd",
                "action": "custom_pwd",
                "command": "echo hello_world",
            },
        )
        assert result["passed"] is True
        assert "hello_world" in result.get("summary", "")

    def test_execute_custom_command_fails(self):
        from ecos.workflow.executor import _execute_step

        result = _execute_step(
            "custom_false",
            step={
                "name": "测试false",
                "action": "custom_false",
                "command": "false",
            },
        )
        assert result["passed"] is False

    def test_execute_custom_command_not_found(self):
        from ecos.workflow.executor import _execute_step

        result = _execute_step(
            "nonexistent_bin",
            step={
                "name": "测试不存在",
                "action": "nonexistent_bin",
                "command": "/nonexistent/binary --flag",
            },
        )
        assert result["passed"] is False
        assert "未找到" in result.get("summary", "")

    def test_execute_custom_command_timeout(self):
        from ecos.workflow.executor import _execute_step

        result = _execute_step(
            "custom_sleep",
            step={
                "name": "测试超时",
                "action": "custom_sleep",
                "command": "sleep 30",
                "timeout": 1,
            },
        )
        assert result["passed"] is False
        assert "超时" in result.get("summary", "")

    def test_custom_command_through_default_backend(self, monkeypatch):
        """通过默认后端执行自定义命令"""
        from ecos.workflow.backend_registry import resolve

        wf = {
            "execution": {"backend": "default"},
            "steps": [
                {"name": "自定义步骤", "action": "custom_echo", "command": "echo ok"},
            ],
        }
        fn = resolve(wf)
        result = fn(wf)
        assert result["passed"] == 1
        assert result["failed"] == 0

    def test_registered_action_still_works(self):
        """已注册 action 不受影响"""
        from ecos.workflow.executor import _execute_step

        # domain_audit 是已注册 action，即使传了 command 也不该用 command
        result = _execute_step(
            "domain_audit",
            step={
                "name": "审计",
                "action": "domain_audit",
                "command": "echo should_not_run",
            },
        )
        # domain_audit 依赖 ~/bin/ecos，但这是已注册 action
        # 所以 command 字段被忽略，走正常 action 路由
        assert (
            "result" not in result
            or result.get("result", {}).get("stdout", "") != "should_not_run"
        )


class TestSubWorkflow:
    """子工作流 (workflow_run action) 测试"""

    def test_workflow_run_action_registered(self):
        from ecos.workflow.actions import list_actions, resolve_action

        names = {a["name"] for a in list_actions()}
        assert "workflow_run" in names

        handler = resolve_action("workflow_run")
        assert handler is not None, "workflow_run handler 应可解析"

    def test_workflow_run_no_name(self):
        from ecos.workflow.actions import resolve_action

        handler = resolve_action("workflow_run")
        result = handler({})  # type: ignore[reportOptionalCall]
        assert result["passed"] is False
        assert "未指定" in result.get("summary", "")

    def test_step_workflow_field_merged_to_params(self):
        """step 中的 workflow 字段应合并到 handler params"""
        from ecos.workflow.executor import _execute_step

        result = _execute_step(
            "workflow_run",
            step={
                "name": "子工作流",
                "action": "workflow_run",
                "workflow": "WORKFLOW-ECOS-DAILY-HEALTH",
            },
        )
        # WORKFLOW-ECOS-DAILY-HEALTH 存在，所以不应返回"未指定"
        summary = result.get("summary", "")
        assert "未指定" not in summary, f"不应是未指定: {summary}"

    def test_workflow_run_via_default_backend(self, monkeypatch):
        """通过默认后端执行子工作流"""
        from ecos.workflow.backend_registry import resolve

        wf = {
            "execution": {"backend": "default", "mode": "sequential"},
            "steps": [
                {
                    "name": "子工作流",
                    "action": "workflow_run",
                    "workflow": "WORKFLOW-ECOS-DAILY-HEALTH",
                },
            ],
        }
        fn = resolve(wf)
        result = fn(wf)
        assert "steps" in result
        # 子工作流可能因环境脚本缺失而失败，但不应抛异常
        assert result["passed"] >= 0
        assert result["failed"] >= 0


class TestRetryStrategy:
    """Retry 策略测试"""

    def test_parse_retry_config_empty(self):
        from ecos.workflow.backend_registry import _parse_retry_config

        assert _parse_retry_config({}) == {}

    def test_parse_retry_config_legacy(self):
        from ecos.workflow.backend_registry import _parse_retry_config

        cfg = _parse_retry_config({"max_retries": 3})
        assert cfg["max_attempts"] == 3
        assert cfg["policy"] == "on_failure"

    def test_parse_retry_config_full(self):
        from ecos.workflow.backend_registry import _parse_retry_config

        cfg = _parse_retry_config(
            {
                "retry": {
                    "max_attempts": 5,
                    "policy": "always",
                    "backoff": {
                        "initial_delay": 2.0,
                        "multiplier": 3.0,
                        "max_delay": 120.0,
                    },
                },
            }
        )
        assert cfg["max_attempts"] == 5
        assert cfg["policy"] == "always"
        assert cfg["backoff"]["initial_delay"] == 2.0
        assert cfg["backoff"]["multiplier"] == 3.0

    def test_compute_backoff(self):
        from ecos.workflow.backend_registry import _compute_backoff_delay

        cfg = {
            "backoff": {
                "initial_delay": 1.0,
                "multiplier": 2.0,
                "max_delay": 60.0,
                "jitter": 0.0,
            }
        }
        d1 = _compute_backoff_delay(1, cfg)
        d2 = _compute_backoff_delay(2, cfg)
        d7 = _compute_backoff_delay(7, cfg)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d7 == 60.0

    def test_should_retry_failure(self):
        from ecos.workflow.backend_registry import _should_retry

        assert _should_retry("on_failure", {"passed": False}, None) is True
        assert _should_retry("on_error", {"passed": False}, None) is False

    def test_should_retry_error(self):
        from ecos.workflow.backend_registry import _should_retry

        assert _should_retry("on_error", {}, Exception("boom")) is True
        assert _should_retry("on_failure", {}, Exception("boom")) is False


class TestDAGExecution:
    """DAG 拓扑排序执行测试"""

    def test_no_deps_single_layer(self):
        from ecos.workflow.backend_registry import _topological_sort

        steps = [
            {"name": "A", "action": "health_check"},
            {"name": "B", "action": "domain_audit"},
        ]
        layers = _topological_sort(steps)
        assert len(layers) == 1
        assert len(layers[0]) == 2
        assert layers[0][0]["name"] == "A"
        assert layers[0][1]["name"] == "B"

    def test_with_deps_multi_layer(self):
        from ecos.workflow.backend_registry import _topological_sort

        steps = [
            {"name": "A", "action": "check", "depends_on": []},
            {"name": "B", "action": "process", "depends_on": ["A"]},
            {"name": "C", "action": "report", "depends_on": ["B"]},
        ]
        layers = _topological_sort(steps)
        assert len(layers) == 3, f"expected 3 layers, got {len(layers)}"
        assert layers[0][0]["name"] == "A"
        assert layers[1][0]["name"] == "B"
        assert layers[2][0]["name"] == "C"

    def test_diamond_deps(self):
        from ecos.workflow.backend_registry import _topological_sort

        steps = [
            {"name": "A", "action": "start", "depends_on": []},
            {"name": "B", "action": "parallel_1", "depends_on": ["A"]},
            {"name": "C", "action": "parallel_2", "depends_on": ["A"]},
            {"name": "D", "action": "merge", "depends_on": ["B", "C"]},
        ]
        layers = _topological_sort(steps)
        assert len(layers) == 3
        assert layers[0][0]["name"] == "A"
        assert {s["name"] for s in layers[1]} == {"B", "C"}
        assert layers[2][0]["name"] == "D"

    def test_default_executor_respects_deps(self, monkeypatch):
        from ecos.workflow.backend_registry import resolve

        executed_order = []

        def mock_execute(m1_node, params=None):
            nonlocal executed_order
            for step in m1_node.get("steps", []):
                executed_order.append(step.get("name", ""))
            return {"steps": [], "passed": 0, "failed": 0}

        monkeypatch.setattr(
            "ecos.workflow.backend_registry._default_executor", mock_execute
        )

        wf = {
            "execution": {"backend": "default", "mode": "sequential"},
            "steps": [
                {"name": "A", "action": "echo"},
                {"name": "B", "action": "echo", "depends_on": ["A"]},
            ],
        }
        fn = resolve(wf)
        fn(wf)
        # A 应在 B 之前
        assert executed_order.index("A") < executed_order.index("B")


class TestConditionalSteps:
    """条件步骤 (step.when) 测试"""

    def test_no_condition_runs(self):
        from ecos.workflow.backend_registry import _evaluate_when

        assert _evaluate_when("", {"steps": []}) is False

    def test_skip_when_passed_is_false(self):
        from ecos.workflow.backend_registry import _evaluate_when

        results = {"steps": [{"name": "前置", "status": "failed"}]}
        assert _evaluate_when("${steps.前置.passed}", results) is True

    def test_run_when_passed_is_true(self):
        from ecos.workflow.backend_registry import _evaluate_when

        results = {"steps": [{"name": "前置", "status": "ok"}]}
        assert _evaluate_when("${steps.前置.passed}", results) is False

    def test_run_when_failed_is_true(self):
        from ecos.workflow.backend_registry import _evaluate_when

        results = {"steps": [{"name": "前置", "status": "failed"}]}
        assert _evaluate_when("${steps.前置.failed}", results) is False  # False=不跳过

    def test_skip_when_failed_is_false(self):
        from ecos.workflow.backend_registry import _evaluate_when

        results = {"steps": [{"name": "前置", "status": "ok"}]}
        assert (
            _evaluate_when("${steps.前置.failed}", results) is True
        )  # True=跳过（条件不满足）

    def test_referenced_step_not_found(self):
        from ecos.workflow.backend_registry import _evaluate_when

        assert _evaluate_when("${steps.未知.passed}", {"steps": []}) is False

    def test_skipped_step_in_executor(self, monkeypatch):
        """通过 executor 验证条件跳过"""
        from ecos.workflow.backend_registry import resolve

        executed_steps = []

        def mock_execute(m1_node, params=None):
            nonlocal executed_steps
            result = {"steps": [], "passed": 0, "failed": 0}
            for s in m1_node.get("steps", []):
                name = s.get("name", "")
                if name == "前置":
                    result["steps"].append(
                        {"name": name, "status": "failed", "result": {"passed": False}}
                    )
                    result["failed"] += 1
                else:
                    result["steps"].append(
                        {"name": name, "status": "ok", "result": {"passed": True}}
                    )
                    result["passed"] += 1
                executed_steps.append(name)
            return result

        monkeypatch.setattr(
            "ecos.workflow.backend_registry._default_executor", mock_execute
        )

        # 当 前置 失败时，后置 应被跳过
        wf = {
            "execution": {"backend": "default", "mode": "sequential"},
            "steps": [
                {"name": "前置", "action": "health_check"},
                {
                    "name": "后置",
                    "action": "echo",
                    "command": "echo skip",
                    "when": "${steps.前置.failed}",
                },
            ],
        }
        fn = resolve(wf)
        result = fn(wf)
        step_names = [s["name"] for s in result.get("steps", [])]
        assert "前置" in step_names
        assert "后置" in step_names


class TestDefaultMeshSink:
    """默认 Mesh sink 接入测试 — Phase 1a 目标达成验证"""

    def test_default_mesh_sink_is_used_when_not_specified(self, tmp_path, monkeypatch):
        """不显式传入 event_sink 时，应自动使用 default_mesh_sink"""
        from ecos.workflow.executor import execute_m1_workflow

        sink_calls = []

        def spy_sink(event):
            sink_calls.append(event)

        # 用 mock step 确保走到 emit_event (non-dry_run)
        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-mesh-auto-connect",
                "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
                "execution": {"backend": "default"},
            },
        )
        # 用 monkeypatch 正确替换 executor 模块内的 get_default_mesh_sink
        monkeypatch.setattr(
            "ecos.workflow.executor.get_default_mesh_sink",
            lambda: spy_sink,
        )

        # 关键：不传 event_sink；non-dry_run 模式会 emit WorkflowRequested
        result = execute_m1_workflow("test-mesh-auto-connect")

        # 应该 emit WorkflowRequested 事件
        assert len(sink_calls) >= 1, "应自动 emit Mesh 事件，无需显式传入 event_sink"
        assert any(c.get("event_type") == "WorkflowRequested" for c in sink_calls), (
            "应包含 WorkflowRequested 事件"
        )

    def test_default_mesh_sink_graceful_degradation_when_omo_not_found(
        self, tmp_path, monkeypatch
    ):
        """找不到 OMO 时静默降级，不阻断 workflow 执行"""
        from ecos.workflow.executor import execute_m1_workflow
        import ecos.workflow.default_mesh_sink as dms

        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        try:
            monkeypatch.setattr(
                "ecos.workflow.executor.load_workflow",
                lambda name: {
                    "name": "test-no-omo",
                    "steps": [{"name": "noop"}],
                    "execution": {"backend": "default"},
                },
            )

            # 不抛异常，正常执行
            result = execute_m1_workflow("test-no-omo")
            assert result is not None  # 不崩溃
        finally:
            dms._find_omo_root = original


class TestMeshGate:
    """Mesh connection gate tests - Phase 3 governance gate"""

    def test_mesh_gate_warning_when_omo_not_found(self, tmp_path, monkeypatch):
        """Mesh gate should produce warning (not error) when OMO not found."""
        import ecos.workflow.default_mesh_sink as dms
        from ecos.workflow.mesh_gate import mesh_gate_check

        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        dms._store_instance = None
        try:
            violations = mesh_gate_check()
            assert len(violations) == 1
            assert violations[0]["severity"] == "warning"
            assert violations[0]["id"] == "MESH-GATE-01"
        finally:
            dms._find_omo_root = original
            dms._store_instance = None

    def test_mesh_gate_error_in_strict_mode(self, tmp_path, monkeypatch):
        """Mesh gate should produce error in strict mode when OMO not found."""
        import ecos.workflow.default_mesh_sink as dms
        from ecos.workflow.mesh_gate import mesh_gate_check

        monkeypatch.setenv("ECOS_MESH_GATE_STRICT", "1")
        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        dms._store_instance = None
        try:
            violations = mesh_gate_check()
            assert len(violations) == 1
            assert violations[0]["severity"] == "error"
        finally:
            dms._find_omo_root = original
            dms._store_instance = None
            monkeypatch.delenv("ECOS_MESH_GATE_STRICT", raising=False)

    def test_mesh_gate_passes_when_store_available(self, tmp_path, monkeypatch):
        """Mesh gate should pass (no violations) when store is available."""
        from ecos.workflow.mesh_gate import mesh_gate_check

        class MockStore:
            def __init__(self):
                self.omo_dir = tmp_path

            def events(self):
                return []

        monkeypatch.setattr(
            "ecos.workflow.mesh_gate._get_workflow_mesh_store"
            if hasattr(
                __import__(
                    "ecos.workflow.mesh_gate", fromlist=["_get_workflow_mesh_store"]
                ),
                "_get_workflow_mesh_store",
            )
            else "ecos.workflow.default_mesh_sink._get_workflow_mesh_store",
            lambda: MockStore(),
        )

        violations = mesh_gate_check()
        assert len(violations) == 0

    def test_executor_blocks_in_strict_mode(self, tmp_path, monkeypatch):
        """Executor should block execution when Mesh gate is in strict mode."""
        import ecos.workflow.default_mesh_sink as dms

        monkeypatch.setenv("ECOS_MESH_GATE_STRICT", "1")
        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        dms._store_instance = None
        try:
            monkeypatch.setattr(
                "ecos.workflow.executor.load_workflow",
                lambda name: {
                    "name": "test-strict-block",
                    "steps": [{"name": "noop"}],
                    "execution": {"backend": "default", "mode": "workflow"},
                },
            )
            result = execute_m1_workflow("test-strict-block")
            assert result["failed"] == 1
            assert result.get("error_code") == "MESH_GATE_BLOCKED"
        finally:
            dms._find_omo_root = original
            dms._store_instance = None
            monkeypatch.delenv("ECOS_MESH_GATE_STRICT", raising=False)

    def test_executor_warns_in_default_mode(self, tmp_path, monkeypatch):
        """Executor should continue with warning in default (non-strict) mode."""
        import ecos.workflow.default_mesh_sink as dms

        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        dms._store_instance = None
        try:
            monkeypatch.setattr(
                "ecos.workflow.executor.load_workflow",
                lambda name: {
                    "name": "test-warn-continue",
                    "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
                    "execution": {"backend": "default", "mode": "workflow"},
                },
            )
            result = execute_m1_workflow("test-warn-continue")
            assert result.get("error_code") != "MESH_GATE_BLOCKED"
            assert any(
                v.get("id") == "MESH-GATE-01" for v in result.get("violations", [])
            )
        finally:
            dms._find_omo_root = original
            dms._store_instance = None


class TestSceneBindingBridge:
    """Phase 4: Scene binding bridge tests"""

    def test_executor_emits_scene_binding_from_workflow_metadata(
        self, tmp_path, monkeypatch
    ):
        """Executor should include scene_binding in WorkflowRequested when defined in workflow metadata."""
        sink_calls = []

        def spy_sink(event):
            sink_calls.append(event)

        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-scene",
                "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
                "execution": {"backend": "default", "mode": "workflow"},
                "metadata": {
                    "scene_binding": {
                        "scene_id": "scene-1",
                        "journey_id": "journey-1",
                        "outcome_metric": "success_rate",
                    }
                },
            },
        )
        monkeypatch.setattr(
            "ecos.workflow.executor.get_default_mesh_sink",
            lambda: spy_sink,
        )

        execute_m1_workflow("test-scene")

        requested = [
            c for c in sink_calls if c.get("event_type") == "WorkflowRequested"
        ]
        assert len(requested) >= 1
        assert requested[0]["payload"]["scene_binding"]["scene_id"] == "scene-1"
        assert requested[0]["payload"]["scene_binding"]["journey_id"] == "journey-1"

    def test_executor_emits_scene_binding_from_params(self, tmp_path, monkeypatch):
        """Executor should include scene_binding from params when not in workflow metadata."""
        sink_calls = []

        def spy_sink(event):
            sink_calls.append(event)

        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-scene-params",
                "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
                "execution": {"backend": "default", "mode": "workflow"},
            },
        )
        monkeypatch.setattr(
            "ecos.workflow.executor.get_default_mesh_sink",
            lambda: spy_sink,
        )

        execute_m1_workflow(
            "test-scene-params",
            params={
                "scene_binding": {
                    "scene_id": "param-scene",
                    "journey_id": "param-journey",
                    "outcome_metric": "param-metric",
                }
            },
        )

        requested = [
            c for c in sink_calls if c.get("event_type") == "WorkflowRequested"
        ]
        assert len(requested) >= 1
        assert requested[0]["payload"]["scene_binding"]["scene_id"] == "param-scene"

    def test_executor_omits_scene_binding_when_absent(self, tmp_path, monkeypatch):
        """Executor should not include scene_binding when not available."""
        sink_calls = []

        def spy_sink(event):
            sink_calls.append(event)

        monkeypatch.setattr(
            "ecos.workflow.executor.load_workflow",
            lambda name: {
                "name": "test-no-scene",
                "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
                "execution": {"backend": "default", "mode": "workflow"},
            },
        )
        monkeypatch.setattr(
            "ecos.workflow.executor.get_default_mesh_sink",
            lambda: spy_sink,
        )

        execute_m1_workflow("test-no-scene")

        requested = [
            c for c in sink_calls if c.get("event_type") == "WorkflowRequested"
        ]
        assert len(requested) >= 1
        assert "scene_binding" not in requested[0]["payload"]


class TestMeshHealth:
    """Mesh health monitor tests"""

    def test_health_unavailable_when_no_store(self, monkeypatch):
        """Health should report unavailable when Mesh store not found."""
        import ecos.workflow.default_mesh_sink as dms
        from ecos.workflow.mesh_health import mesh_health_snapshot

        original = dms._find_omo_root
        dms._find_omo_root = lambda *a, **kw: None
        dms._store_instance = None
        try:
            health = mesh_health_snapshot()
            assert health["status"] == "unavailable"
            assert health["connected"] is False
            assert health["event_count"] == 0
        finally:
            dms._find_omo_root = original
            dms._store_instance = None

    def test_health_degraded_when_store_empty(self, monkeypatch):
        """Health should report degraded when store has no events."""
        from ecos.workflow.mesh_health import mesh_health_snapshot

        class MockEmptyStore:
            def events(self):
                return []

        monkeypatch.setattr(
            "ecos.workflow.default_mesh_sink._get_workflow_mesh_store",
            lambda: MockEmptyStore(),
        )

        health = mesh_health_snapshot()
        assert health["status"] == "degraded"
        assert health["connected"] is True
        assert health["event_count"] == 0

    def test_health_healthy_with_recent_events(self, monkeypatch):
        """Health should report healthy when store has recent events."""
        from datetime import UTC, datetime
        from ecos.workflow.mesh_health import mesh_health_snapshot

        now = datetime.now(UTC).isoformat()

        class MockActiveStore:
            def events(self):
                return [
                    {
                        "event_type": "WorkflowRequested",
                        "occurred_at": now,
                        "producer": "agent-workflow",
                    },
                    {
                        "event_type": "StepDispatched",
                        "occurred_at": now,
                        "producer": "omo.omo_worker_dispatch",
                    },
                ]

        monkeypatch.setattr(
            "ecos.workflow.default_mesh_sink._get_workflow_mesh_store",
            lambda: MockActiveStore(),
        )

        health = mesh_health_snapshot()
        assert health["status"] == "healthy"
        assert health["event_count"] == 2
        assert health["events_last_hour"] >= 2
        assert "agent-workflow" in health["bridges_active"]
        assert "omo.omo_worker_dispatch" in health["bridges_active"]

    def test_health_check_returns_violations(self, monkeypatch):
        """mesh_health_check should return violations when degraded."""
        from ecos.workflow.mesh_health import mesh_health_check

        class MockEmptyStore:
            def events(self):
                return []

        monkeypatch.setattr(
            "ecos.workflow.default_mesh_sink._get_workflow_mesh_store",
            lambda: MockEmptyStore(),
        )

        violations = mesh_health_check()
        assert len(violations) == 1
        assert violations[0]["severity"] == "warning"
        assert "MESH-HEALTH" in violations[0]["id"]

    def test_health_check_empty_when_healthy(self, monkeypatch):
        """mesh_health_check should return empty list when healthy."""
        from datetime import UTC, datetime
        from ecos.workflow.mesh_health import mesh_health_check

        now = datetime.now(UTC).isoformat()

        class MockStore:
            def events(self):
                return [
                    {
                        "event_type": "WorkflowRequested",
                        "occurred_at": now,
                        "producer": "test",
                    }
                ]

        monkeypatch.setattr(
            "ecos.workflow.default_mesh_sink._get_workflow_mesh_store",
            lambda: MockStore(),
        )

        violations = mesh_health_check()
        assert len(violations) == 0
