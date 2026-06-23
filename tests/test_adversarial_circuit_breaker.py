from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

# Mock l0_audit before importing ecos.workflow to prevent import errors in test environment
l0_audit_mock = MagicMock()
sys.modules["l0_audit"] = l0_audit_mock

import httpx  # noqa: E402
import subprocess  # noqa: E402
from ecos.workflow.executor import execute_m1_workflow  # noqa: E402


def test_swarm_backend_no_circuit_breaker_delay_accumulation():
    """对抗性验证：模拟 Agora 网关宕机并挂起（网络超时），校验是否由于缺乏熔断器导致步骤延迟累加"""

    # 1. 备份原始 subprocess 行为，防止影响其他部分
    original_run = subprocess.run
    subprocess_calls = []

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "aetherforge" in cmd_str:
            subprocess_calls.append(cmd_str)
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout='{"goal": "test", "status": "success", "result": "mock local CLI fallback success"}',
                stderr=''
            )
        return original_run(cmd, *args, **kwargs)

    # 2. 构造 3 个步骤的 Swarm 后端工作流
    mock_workflow = {
        "type": "Workflow",
        "id": "workflow-adversarial-test",
        "name": "Adversarial Swarm Test Workflow",
        "domain": "capability",
        "layer": "L0",
        "bos_uri": "bos://ecos/workflow/adversarial-test",
        "execution": {
            "backend": "swarm",
            "mode": "sequential",
        },
        "steps": [
            {
                "order": 1,
                "name": "Step-1",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            },
            {
                "order": 2,
                "name": "Step-2",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            },
            {
                "order": 3,
                "name": "Step-3",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            }
        ]
    }

    # 3. 模拟 Agora HTTP 握手丢包或响应挂起，每次调用均耗费 1.5 秒延时，最后触发 ConnectTimeout
    def mock_post_with_delay(*args, **kwargs):
        time.sleep(1.5)  # 模拟网络等待和握手延时
        raise httpx.ConnectTimeout("Gateway connection timed out")

    # 4. Patch 并执行测试
    with patch("httpx.Client") as mock_client_cls, \
         patch("subprocess.run", side_effect=mock_run), \
         patch("ecos.workflow.executor.load_workflow", return_value=mock_workflow):

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = mock_post_with_delay

        start_time = time.time()
        result = execute_m1_workflow("workflow-adversarial-test")
        duration = time.time() - start_time

        print(f"\n[Adversarial Results] Workflow execution duration: {duration:.2f}s")
        print(f"[Adversarial Results] Subprocess fallback calls: {len(subprocess_calls)}")
        
        # 验证是否全部优雅降级成功
        assert result["failed"] == 0
        assert result["passed"] == 3
        
        # 对抗性断言：如果降级有智能熔断器（或者针对 Agora 状态有 TTL 缓存），
        # 在第一步发生超时（1.5s）并熔断后，后续的步骤 2 和步骤 3 应该瞬时熔断，
        # 直接使用本地 CLI 降级。因此总时间应该显著小于 3.0s（即 1.5s 超时 + 本地运行延时）。
        # 如果总时间 >= 4.0s，则说明每一次请求都傻傻地等待了 1.5s，耗时发生了无防备的累加！
        assert duration < 3.0, (
            f"熔断降级时延严重累加！总耗时为 {duration:.2f}s。当 Agora 网格假死时，"
            f"多个执行步骤会导致严重的系统挂起挂死（每一步都遭遇 {1.5}s 延时，未熔断）。"
        )


def test_agora_backend_unnecessary_probe_delay():
    """对抗性验证：在 Agora 网关持续宕机时，agora 后端每次健康检查探针依然会产生 2.0 秒阻塞，缺乏全局熔断状态的零延迟缓存机制"""
    
    # 构造 3 个步骤的 Agora 后端工作流
    mock_workflow = {
        "type": "Workflow",
        "id": "workflow-agora-adversarial-test",
        "name": "Adversarial Agora Test Workflow",
        "domain": "capability",
        "layer": "L0",
        "bos_uri": "bos://ecos/workflow/agora-adversarial-test",
        "execution": {
            "backend": "agora",
            "mode": "sequential",
            "timeout": 10,
        },
        "steps": [
            {
                "order": 1,
                "name": "Step-1",
                "action": "research"
            }
        ]
    }

    # 模拟健康探针 get 挂起 2.0s 超时
    def mock_get_with_delay(*args, **kwargs):
        time.sleep(2.0)
        raise httpx.ConnectTimeout("Agora health probe timed out")

    # 模拟默认后端的回退
    mock_default_executor = MagicMock(return_value={"steps": [{"name": "Step-1", "status": "ok"}], "passed": 1, "failed": 0})

    with patch("httpx.Client") as mock_client_cls, \
         patch("ecos.workflow.backend_registry._default_executor", mock_default_executor), \
         patch("ecos.workflow.executor.load_workflow", return_value=mock_workflow):

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = mock_get_with_delay

        # 连续执行 2 次工作流。如果拥有全局熔断/不可达状态缓存（例如 10 秒 TTL 缓存），
        # 第一次执行将花费 2.0s 等待探测，并记录 Agora 不可用；
        # 第二次执行应瞬间判定 Agora 不可用并直接 fallback，用时应趋近于 0（< 0.1s）。
        # 如果第二次执行依然等待了 2.0s，则说明缺乏状态缓存！
        
        start_time_1 = time.time()
        execute_m1_workflow("workflow-agora-adversarial-test")
        duration_1 = time.time() - start_time_1

        start_time_2 = time.time()
        execute_m1_workflow("workflow-agora-adversarial-test")
        duration_2 = time.time() - start_time_2

        print(f"\n[Adversarial Results Agora] Run 1 duration: {duration_1:.2f}s")
        print(f"[Adversarial Results Agora] Run 2 duration: {duration_2:.2f}s")

        assert duration_2 < 0.2, (
            f"缺乏不可达状态的缓存熔断！第二次运行仍然被挂起探测了 {duration_2:.2f}s。"
            f"当 Agora 持续宕机时，每次运行都将增加不必要的网络超时开销。"
        )

