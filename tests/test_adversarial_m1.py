"""M1 Agora MCP 跨层通信重构 — 对抗性测试、压力校验与降级测试

测试覆盖:
1. 网络异常降级：网格不通 (ConnectionRefused)、超时 (Timeout)、HTTP 错误状态码 (500/502)、非 JSON 返回。
2. 代理故障降级：全局代理无法连接时，工作流是否安全降级、零崩溃。
3. 压力校验与熔断拦截：高频调用下，熔断器能否秒级反应，防止重复请求，多线程并发下无竞争死锁。
"""

from __future__ import annotations

import os
import time
import threading
import pytest
import httpx
from unittest.mock import patch

from ecos.workflow.agora_mcp_backend import execute
from ecos.workflow import circuit_breaker as cb


@pytest.fixture(autouse=True)
def clean_cb():
    """每次测试前复位熔断器和清除可能影响测试的代理环境变量"""
    cb.reset_all()
    # 备份环境变量
    old_http = os.environ.get("HTTP_PROXY")
    old_https = os.environ.get("HTTPS_PROXY")
    old_all = os.environ.get("ALL_PROXY")

    yield

    cb.reset_all()
    # 还原环境变量
    if old_http:
        os.environ["HTTP_PROXY"] = old_http
    elif "HTTP_PROXY" in os.environ:
        del os.environ["HTTP_PROXY"]

    if old_https:
        os.environ["HTTPS_PROXY"] = old_https
    elif "HTTPS_PROXY" in os.environ:
        del os.environ["HTTPS_PROXY"]

    if old_all:
        os.environ["ALL_PROXY"] = old_all
    elif "ALL_PROXY" in os.environ:
        del os.environ["ALL_PROXY"]


# ── 1. 网络异常测试集 ─────────────────────────────────────────────────────────


def test_agora_connection_refused_fallback():
    """测试 Agora 物理上未启动/无法建立连接 (ConnectionRefusedError) -> 优雅降级且记录熔断"""
    # 模拟 httpx.Client 抛出 ConnectError
    with (
        patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")),
        patch(
            "ecos.workflow.agora_mcp_backend._unavailable_result"
        ) as mock_unavailable,
    ):
        mock_unavailable.return_value = {
            "mode": "unavailable",
            "error_code": "BACKEND_UNAVAILABLE",
            "steps": [],
        }

        node = {
            "name": "test-workflow",
            "steps": [{"name": "s1", "action": "health_check"}],
            "execution": {"backend": "agora"},
        }

        result = execute(node, {})

        # 验证不可用状态并触发熔断
        mock_unavailable.assert_called_once()
        assert result["mode"] == "unavailable"
        assert result["error_code"] == "BACKEND_UNAVAILABLE"

        # 验证熔断器状态已变更为 TRIPPED (不可用)
        assert cb.is_available("agora", "mcp-gateway") is False


def test_agora_timeout_fallback():
    """测试 Agora 请求超时 (httpx.TimeoutException) -> 优雅降级且记录熔断"""
    with (
        patch(
            "httpx.Client.get", side_effect=httpx.ConnectTimeout("Connection timed out")
        ),
        patch(
            "ecos.workflow.agora_mcp_backend._unavailable_result"
        ) as mock_unavailable,
    ):
        mock_unavailable.return_value = {
            "mode": "unavailable",
            "error_code": "BACKEND_UNAVAILABLE",
            "steps": [],
        }
        node = {"steps": [{"name": "s1", "action": "health_check"}]}

        execute(node, {})

        mock_unavailable.assert_called_once()
        assert cb.is_available("agora", "mcp-gateway") is False


def test_agora_http_error_code_fallback():
    """测试 Agora 网关返回 500/502 错误 -> 优雅降级且记录熔断"""
    # 构造一个 502 Bad Gateway mock 响应
    mock_resp = httpx.Response(status_code=502, text="Bad Gateway")

    with (
        patch("httpx.Client.get", return_value=mock_resp),
        patch(
            "ecos.workflow.agora_mcp_backend._unavailable_result"
        ) as mock_unavailable,
    ):
        mock_unavailable.return_value = {
            "mode": "unavailable",
            "error_code": "BACKEND_UNAVAILABLE",
            "steps": [],
        }
        node = {"steps": [{"name": "s1", "action": "health_check"}]}

        execute(node, {})

        mock_unavailable.assert_called_once()
        assert cb.is_available("agora", "mcp-gateway") is False


def test_agora_invalid_json_fallback():
    """测试 Agora 返回了非 JSON 格式的异常数据 (例如 HTTP 200 但返回的是 HTML) -> 优雅捕获、记录为错误步骤且不崩溃"""
    # 如果 health 过了，但执行工具时接口返回了非 JSON 格式
    mock_health = httpx.Response(status_code=200, json={"status": "ok"})
    mock_call_bad = httpx.Response(status_code=200, text="<html>Error</html>")

    # 模拟 post 方法
    with (
        patch("httpx.Client.get", return_value=mock_health),
        patch("httpx.Client.post", return_value=mock_call_bad),
    ):
        node = {
            "name": "test-workflow",
            "steps": [{"name": "s1", "action": "health_check"}],
            "execution": {"backend": "agora"},
        }

        # 执行，即使解析 JSON 抛异常，也会被捕获，不应该导致崩溃，而应该是标记 step 错误
        result = execute(node, {})

        assert "steps" in result
        step_res = result["steps"][0]
        assert step_res["status"] == "error"
        assert "Expecting value" in step_res["error"]


# ── 2. 代理故障测试集 ─────────────────────────────────────────────────────────


def test_global_proxy_invalid_fallback():
    """测试全局代理环境变量指向无效代理 -> httpx 因设置 trust_env=False 能够直接避开代理并正常运行，即使代理挂掉也不受影响"""
    # 模拟全局代理挂载到一个无法连接的地址
    os.environ["HTTP_PROXY"] = (
        "http://192.0.2.1:8888"  # 192.0.2.0/24 为 RFC5737 测试保留网段，物理上绝不可达
    )
    os.environ["HTTPS_PROXY"] = "http://192.0.2.1:8888"

    # 这里的 get/post 请求由于 trust_env=False 应该直接绕开代理，依然正常尝试连接 localhost。
    # 此时 localhost 没有开启 Agora，因此还是抛出 ConnectError 并降级。
    # 重点验证：虽然设置了错误的代理，但是程序由于 trust_env=False 不会在连接代理时无限卡死，而是秒级抛出 localhost ConnectError 并优雅降级

    start_time = time.time()
    node = {
        "name": "test-workflow",
        "steps": [{"name": "s1", "action": "health_check"}],
        "execution": {"backend": "agora"},
    }

    # 执行
    result = execute(node, {})
    elapsed = time.time() - start_time

    # 验证在 3 秒之内就做出了 ConnectionRefusedError 响应并 fallback，没有被 192.0.2.1 的代理超时（默认 10s+）卡死。
    # 本地 health_check 可能因为 ~/.ecos/scripts/ecos-health-check.py 未安装而返回 failed；这里验证的是代理绕过和优雅降级。
    assert elapsed < 3.0
    assert result["steps"] == []
    assert result["mode"] == "unavailable"
    assert result["error_code"] == "BACKEND_UNAVAILABLE"


# ── 3. 压力校验与熔断器拦截测试集 ──────────────────────────────────────────────────


def test_high_frequency_circuit_breaker_stress():
    """压力校验：当后台持续不可用时，连续调用 100 次，只有第 1 次实际发起 HTTP 请求，其余 99 次必须被熔断器秒级拦截，实现 O(1) 效率降级"""

    call_count = 0

    def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("Simulated Down")

    with (
        patch("httpx.Client.get", side_effect=fake_get),
        patch("ecos.workflow.agora_mcp_backend._fallback_default") as mock_fallback,
    ):
        mock_fallback.return_value = {
            "mode": "unavailable",
            "error_code": "BACKEND_UNAVAILABLE",
            "steps": [],
        }
        node = {"steps": [{"name": "s1", "action": "health_check"}]}

        # 连续调用 100 次
        start_time = time.time()
        for _ in range(100):
            execute(node, {})
        duration = time.time() - start_time

        # 1. 验证实际上只发起了 1 次网络调用，后续 99 次直接阻断 fallback
        assert call_count == 1
        # 2. 验证整个 100 次耗时非常低 (毫秒级，远小于网络 IO 探测时间)
        assert duration < 0.1


def test_concurrent_multithread_safety():
    """并发测试：多线程并发执行工作流，检查熔断器与状态变量在多线程下是否安全，有无竞争或死锁"""

    exceptions = []

    def worker():
        try:
            node = {
                "name": "test-workflow",
                "steps": [{"name": "s1", "action": "health_check"}],
                "execution": {"backend": "agora"},
            }
            # 并发执行，此时可能会触发熔断或从熔断中读取状态
            execute(node, {})
        except Exception as e:
            exceptions.append(e)

    # 创建 20 个并发线程
    threads = [threading.Thread(target=worker) for _ in range(20)]

    # 启动所有线程
    for t in threads:
        t.start()

    # 等待结束
    for t in threads:
        t.join()

    # 检查是否有任何未捕获的异常抛出导致崩溃
    assert len(exceptions) == 0
