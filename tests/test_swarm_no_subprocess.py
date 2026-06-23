from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock l0_audit before importing ecos.workflow to prevent import errors in test environment
l0_audit_mock = MagicMock()
sys.modules["l0_audit"] = l0_audit_mock

import subprocess  # noqa: E402
from ecos.workflow.executor import execute_m1_workflow  # noqa: E402


def test_ecos_workflow_no_aetherforge_subprocess():
    """验证在执行带有 Swarm 步骤的工作流时，决不产生针对 aetherforge 的 direct subprocess 调用"""
    
    # 1. 备份并包装原始的 Popen
    original_popen = subprocess.Popen
    detected_violations = []

    def mock_popen(args, *pargs, **kwargs):
        # 将 args 转化为字符串进行分析
        cmd_str = " ".join(args) if isinstance(args, list) else str(args)
        
        # 2. 检查是否命中了 AetherForge 遗留子进程调用的黑名单
        if any(keyword in cmd_str for keyword in ["aetherforge", "swarm_engine/cli.py", "swarm_engine.cli"]):
            violation_msg = f"检测到违规的子进程直调: {cmd_str}"
            detected_violations.append(violation_msg)
            raise AssertionError(violation_msg)
            
        return original_popen(args, *pargs, **kwargs)

    # 3. 构造 Mock M1 工作流定义
    # 模拟包含 aetherforge 步骤的工作流节点
    mock_workflow_node = {
        "type": "Workflow",
        "id": "workflow-swarm-test",
        "name": "Swarm Test Workflow",
        "domain": "capability",
        "layer": "L0",
        "bos_uri": "bos://ecos/workflow/swarm-test",
        "execution": {
            "backend": "swarm",  # 执行后端为 swarm
            "mode": "sequential",
        },
        "steps": [
            {
                "order": 1,
                "name": "Execute-Agent-Research",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            }
        ]
    }

    # 4. Mock 外部 HTTP 调用与系统 Popen
    with patch("httpx.Client") as mock_client_cls, \
         patch("subprocess.Popen", side_effect=mock_popen), \
         patch("ecos.workflow.executor.load_workflow", return_value=mock_workflow_node):

        # Mock Client 实例
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        
        # Mock Agora 成功路由 RPC 响应
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "status": "ok",
            "result": {
                "status": "success",
                "result": "Swarm RPC executed successfully via Agora"
            }
        }
        mock_client.post.return_value = mock_post_resp

        # 5. 执行工作流
        result = execute_m1_workflow("workflow-swarm-test")
        print("DEBUG RESULT:", result)

        # 6. 断言结果
        # 确保没有发生任何 subprocess 违规直调
        assert len(detected_violations) == 0, "发现子进程直调违规:\n" + "\n".join(detected_violations)
        assert result["failed"] == 0
        assert result["passed"] == 1
        
        # 确保 RPC 调用确实被发送到了 Agora Gateway
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        post_json = call_kwargs.get("json", {})
        
        # 校验 RPC 请求的工具名与传参格式
        assert post_json.get("name") == "resolve_bos_uri"
        assert post_json.get("arguments", {}).get("uri") == "bos://capability/swarm/run"
        # 还要验证 trust_env=False 是否传给了 httpx.Client
        mock_client_cls.assert_called_once_with(trust_env=False, timeout=120.0)


def test_ecos_workflow_swarm_fallback_to_subprocess():
    """验证在 Agora Gateway 不可用时，能够优雅降级到原有的 subprocess 调用"""
    
    # 1. 备份并包装原始的 subprocess.run
    original_run = subprocess.run
    subprocess_called = []

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "aetherforge" in cmd_str:
            subprocess_called.append(cmd_str)
            # 返回一个 CompletedProcess 实例
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout='{"goal": "test", "status": "success", "result": "mock subprocess output"}',
                stderr=''
            )
        return original_run(cmd, *args, **kwargs)

    mock_workflow_node = {
        "type": "Workflow",
        "id": "workflow-swarm-test",
        "name": "Swarm Test Workflow",
        "domain": "capability",
        "layer": "L0",
        "bos_uri": "bos://ecos/workflow/swarm-test",
        "execution": {
            "backend": "swarm",
            "mode": "sequential",
        },
        "steps": [
            {
                "order": 1,
                "name": "Execute-Agent-Research",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            }
        ]
    }

    # Mock 外部 HTTP 调用抛出 ConnectError
    with patch("httpx.Client") as mock_client_cls, \
         patch("subprocess.run", side_effect=mock_run), \
         patch("ecos.workflow.executor.load_workflow", return_value=mock_workflow_node):

        # 让 httpx.Client() 发送请求时抛出 ConnectionError 模拟 Gateway 关闭
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        import httpx
        mock_client.post.side_effect = httpx.ConnectError("Gateway connection refused")

        # 5. 执行工作流
        result = execute_m1_workflow("workflow-swarm-test")
        print("DEBUG FALLBACK RESULT:", result)

        # 6. 断言结果
        # 确保虽然 Agora RPC 失败，但工作流依靠降级成功运行，并且调用了 subprocess
        assert len(subprocess_called) > 0
        assert result["failed"] == 0
        assert result["passed"] == 1
