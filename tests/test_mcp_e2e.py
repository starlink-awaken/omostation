"""Agent → MCP → Workflow 集成测试（工具注册验证）

验证 ecos MCP server 正确注册了所有 workflow 工具，
且工具函数可用（不经过 stdio 传输——那是 FastMCP 框架层的测试）。
"""

from __future__ import annotations


def test_workflow_list_function():
    """workflow_list() 直接调用应返回工作流列表"""
    from ecos.mcp_server import workflow_list

    result = workflow_list()
    assert "workflows" in result, f"缺少 workflows 字段: {result[:100]}"
    import json

    data = json.loads(result)
    assert "workflows" in data
    assert data["total"] >= 0


def test_workflow_backends_function():
    """workflow_backends() 应返回后端列表"""
    from ecos.mcp_server import workflow_backends

    result = workflow_backends()
    import json

    data = json.loads(result)
    assert "backends" in data
    backend_names = {b["name"] for b in data["backends"]}
    assert len(backend_names) >= 5, f"期望 >=5 backends, 实际: {backend_names}"
    assert "agora" in backend_names
    assert "dynamic" in backend_names


def test_workflow_actions_function():
    """workflow_actions() 应返回 action 列表"""
    from ecos.mcp_server import workflow_actions

    result = workflow_actions()
    import json

    data = json.loads(result)
    assert "actions" in data
    action_names = {a["name"] for a in data["actions"]}
    assert "health_check" in action_names
    assert "workflow_run" in action_names


def test_workflow_show_function():
    """workflow_show() 应能查找工作流"""
    from ecos.mcp_server import workflow_show

    result = workflow_show("WORKFLOW-ECOS-DAILY-HEALTH")
    import json

    data = json.loads(result)
    assert "error" not in data, f"查找失败: {data.get('error')}"
    assert data.get("type") == "Workflow"
    assert data.get("name") == "每日健康巡检管线"


def test_workflow_validate_function():
    """workflow_validate() 应返回校验结果"""
    from ecos.mcp_server import workflow_validate

    result = workflow_validate("WORKFLOW-ECOS-DAILY-HEALTH")
    import json

    data = json.loads(result)
    assert "valid" in data or "error" in data


def test_workflow_logs_function():
    """workflow_logs() 应返回运行历史"""
    from ecos.mcp_server import workflow_logs

    result = workflow_logs(recent=3)
    import json

    data = json.loads(result)
    assert "runs" in data
