"""Integration test for eCOS Dynamic Workflows.

Verifies the logic of DynamicPlanner and DynamicExecutor:
1. LLM-driven planning mode (with automated Mock fallback for offline/CI environments)
2. Decayed fallback mode (linear sequence execution when LLM is unavailable)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Resolve workspace ecos path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "ecos" / "src"))


def test_dynamic_workflow_execution_mocked():
    """Test LLM-driven planner step execution with mocked completions."""
    m1_node = {
        "name": "WORKFLOW-DYNAMIC-TEST",
        "description": "测试 LLM 动态决策流",
        "execution": {
            "mode": "dynamic",
            "dynamic": {
                "objective": "完成系统健康巡检并生成报告",
                "max_steps": 5,
                "available_actions": [
                    "health_check"
                ],
                "llm_model": "gpt-4o-mini"
            }
        },
        "steps": [
            {"name": "health_check", "action": "health_check"}
        ]
    }

    dummy_handler = lambda params: {"passed": True, "summary": "health_check: ✅"}

    # Preset the expected decision sequence from LLM
    mock_response_1 = MagicMock()
    mock_response_1.choices = [
        MagicMock(message=MagicMock(content='{"action": "health_check", "name": "自动健康巡检", "reason": "优先检查核心服务存活状态", "params": {}}'))
    ]
    mock_response_2 = MagicMock()
    mock_response_2.choices = [
        MagicMock(message=MagicMock(content='{"action": "__done__", "name": "完成", "reason": "已执行健康巡检且通过"}'))
    ]

    mock_completions = MagicMock()
    mock_completions.create.side_effect = [mock_response_1, mock_response_2]

    mock_client = MagicMock()
    mock_client.chat = MagicMock(completions=mock_completions)

    with patch("openai.OpenAI", return_value=mock_client), \
         patch("ecos.workflow.actions.resolve_action", return_value=dummy_handler):
        
        from ecos.workflow.dynamic_backend import execute
        
        # Override environment variables to force OpenAI instantiation
        old_model = os.environ.get("DYNAMIC_WF_MODEL")
        old_key = os.environ.get("OPENAI_API_KEY")
        
        os.environ["DYNAMIC_WF_MODEL"] = "gpt-4o-mini"
        os.environ["OPENAI_API_KEY"] = "sk-mock-key"
        
        try:
            results = execute(m1_node)
            
            # Validation
            assert results["passed"] == 1
            assert results["failed"] == 0
            assert len(results["steps"]) == 1
            assert results["steps"][0]["action"] == "health_check"
            assert results["steps"][0]["status"] == "ok"
            assert results["steps"][0]["reason"] == "优先检查核心服务存活状态"
        finally:
            # Restore environment variables
            if old_model:
                os.environ["DYNAMIC_WF_MODEL"] = old_model
            else:
                os.environ.pop("DYNAMIC_WF_MODEL", None)
                
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)


def test_dynamic_workflow_fallback_execution():
    """Test standard linear sequential fallback when LLM is unavailable."""
    m1_node = {
        "name": "WORKFLOW-DYNAMIC-FALLBACK",
        "description": "测试 Fallback 线性降级",
        "execution": {
            "mode": "dynamic",
            "dynamic": {
                "objective": "执行降级巡检",
                "max_steps": 5,
                "available_actions": [
                    "health_check",
                    "domain_validate_all"
                ],
                "llm_model": ""  # Empty model triggers fallback automatically
            }
        },
        "steps": [
            {"name": "health_check", "action": "health_check"},
            {"name": "domain_validate_all", "action": "domain_validate_all"}
        ]
    }

    dummy_handler = lambda params: {"passed": True, "summary": "Mocked action passed"}

    with patch("ecos.workflow.actions.resolve_action", return_value=dummy_handler):
        from ecos.workflow.dynamic_backend import execute
        
        # Ensure no active LLM model environment
        old_model = os.environ.get("DYNAMIC_WF_MODEL")
        os.environ.pop("DYNAMIC_WF_MODEL", None)
        
        try:
            results = execute(m1_node)
            
            # Validation
            # Fallback should sequentially try executing all available actions
            assert results["passed"] == 2
            assert results["failed"] == 0
            # 2 execution steps + 1 completion step
            assert len(results["steps"]) == 3
            assert results["steps"][0]["action"] == "health_check"
            assert results["steps"][1]["action"] == "domain_validate_all"
            assert results["steps"][2]["action"] == "__done__"
        finally:
            if old_model:
                os.environ["DYNAMIC_WF_MODEL"] = old_model


def test_real_llm_planning_flow():
    """Real LLM integration test (only executed if active keys are available)."""
    model = os.environ.get("DYNAMIC_WF_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")

    if not model or not api_key or api_key == "sk-placeholder":
        # Skip gracefully in offline/CI environments
        import pytest
        pytest.skip("No real OpenAI/Volcengine API Key configuration found. Skipping real planning test.")

    m1_node = {
        "name": "WORKFLOW-REAL-LLM-TEST",
        "description": "Real LLM path validation",
        "execution": {
            "mode": "dynamic",
            "dynamic": {
                "objective": "验证基础巡检动作并宣告完成",
                "max_steps": 3,
                "available_actions": [
                    "health_check"
                ],
                "llm_model": model
            }
        }
    }

    dummy_handler = lambda params: {"passed": True, "summary": "health_check: ✅"}

    with patch("ecos.workflow.actions.resolve_action", return_value=dummy_handler):
        from ecos.workflow.dynamic_backend import execute
        results = execute(m1_node)
        
        assert results["passed"] >= 1
        assert len(results["steps"]) >= 1
        assert results["steps"][-1]["action"] == "__done__"
