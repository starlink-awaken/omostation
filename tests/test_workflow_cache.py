"""Workflow Cache — 步骤级缓存测试"""

from __future__ import annotations

import time
from unittest.mock import patch


from ecos.workflow import cache


def _cleanup() -> None:
    """每次测试前清理缓存，避免测试间污染"""
    cache.invalidate_all()


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def test_cache_miss_on_empty() -> None:
    """空缓存时 get 返回 None"""
    assert cache.get("wf-test", 0) is None


def test_cache_set_and_get() -> None:
    """写入后能正确读取"""
    result = {"passed": True, "summary": "ok", "data": {"key": "val"}}
    cache.set("wf-setget", 0, result, ttl=60)
    got = cache.get("wf-setget", 0)
    assert got is not None
    assert got["passed"] is True
    assert got["summary"] == "ok"
    assert got["data"]["key"] == "val"


def test_cache_returns_copy() -> None:
    """get 返回的是副本，修改副本不影响缓存"""
    result = {"passed": True, "summary": "original"}
    cache.set("wf-copy", 0, result, ttl=60)
    got = cache.get("wf-copy", 0)
    got["summary"] = "modified"  # type: ignore[reportOptionalSubscript]
    second = cache.get("wf-copy", 0)
    assert second["summary"] == "original"  # type: ignore[reportOptionalSubscript]


def test_cache_ttl_expiry() -> None:
    """TTL 过期后返回 None"""
    result = {"passed": True}
    cache.set("wf-ttl", 0, result, ttl=1)  # 1秒 TTL
    assert cache.get("wf-ttl", 0) is not None
    time.sleep(1.1)
    assert cache.get("wf-ttl", 0) is None


def test_cache_zero_ttl_not_stored() -> None:
    """TTL=0 时不缓存"""
    result = {"passed": True}
    cache.set("wf-zerottl", 0, result, ttl=0)
    assert cache.get("wf-zerottl", 0) is None


def test_cache_multi_step() -> None:
    """多步骤缓存独立"""
    cache.set("wf-multi", 0, {"passed": True, "summary": "step0"}, ttl=60)
    cache.set("wf-multi", 1, {"passed": True, "summary": "step1"}, ttl=60)
    cache.set("wf-multi", 2, {"passed": False, "summary": "step2"}, ttl=60)

    step0 = cache.get("wf-multi", 0)
    step1 = cache.get("wf-multi", 1)
    step2 = cache.get("wf-multi", 2)

    assert step0["summary"] == "step0"  # type: ignore[reportOptionalSubscript]
    assert step1["summary"] == "step1"  # type: ignore[reportOptionalSubscript]
    assert step2["summary"] == "step2"  # type: ignore[reportOptionalSubscript]
    assert step2["passed"] is False  # type: ignore[reportOptionalSubscript]


def test_cache_params_differentiation() -> None:
    """相同工作流+不同 params 产生不同缓存键"""
    result = {"passed": True}
    cache.set("wf-params", 0, result, ttl=60, params={"model": "gpt4"})
    assert cache.get("wf-params", 0, params={"model": "claude"}) is None
    assert cache.get("wf-params", 0, params={"model": "gpt4"}) is not None


def test_cache_invalidate_workflow() -> None:
    """按工作流名批量清除"""
    cache.set("wf-a", 0, {"passed": True}, ttl=60)
    cache.set("wf-a", 1, {"passed": True}, ttl=60)
    cache.set("wf-b", 0, {"passed": True}, ttl=60)

    cleared = cache.invalidate("wf-a")
    assert cleared == 2

    assert cache.get("wf-a", 0) is None
    assert cache.get("wf-a", 1) is None
    assert cache.get("wf-b", 0) is not None


def test_cache_invalidate_all() -> None:
    """全量清除"""
    cache.set("wf-x", 0, {"passed": True}, ttl=60)
    cache.set("wf-y", 0, {"passed": True}, ttl=60)

    cleared = cache.invalidate_all()
    assert cleared == 2

    assert cache.get("wf-x", 0) is None
    assert cache.get("wf-y", 0) is None


def test_cache_status_output() -> None:
    """status() 返回正确格式"""
    cache.set("wf-st", 0, {"passed": True}, ttl=120)
    cache.set("wf-st", 1, {"passed": False}, ttl=60)

    s = cache.status()
    assert s["total_entries"] == 2
    assert len(s["entries"]) == 2
    for e in s["entries"]:
        assert "key" in e
        assert "age_s" in e
        assert "ttl_s" in e
        assert "remaining_s" in e
        assert e["remaining_s"] >= 0


def test_cache_empty_status() -> None:
    """空缓存的 status"""
    s = cache.status()
    assert isinstance(s["total_entries"], int)
    assert isinstance(s["entries"], list)


def test_executor_cache_hit_in_m1_workflow() -> None:
    """execute_m1_workflow 缓存命中时跳过 backend"""
    from ecos.workflow.executor import execute_m1_workflow

    # 先手动写入缓存
    cached_result = {
        "workflow": "test-exec-cache",
        "display": "Test",
        "source": "test",
        "steps": [{"name": "cached-step", "status": "ok"}],
        "passed": 1,
        "failed": 0,
    }
    cache.set("test-exec-cache", 0, cached_result, ttl=60, params=None)

    with (
        patch("ecos.workflow.executor.load_workflow") as mock_load,
        patch("ecos.workflow.executor.resolve") as mock_resolve,
        patch("ecos.workflow.executor.validate_workflow") as mock_val,
        patch("ecos.workflow.executor.X2BudgetDeducer.check_budget") as mock_budget,
    ):
        # Mock load_workflow to return a workflow with cache_ttl
        mock_load.return_value = {
            "name": "test-exec-cache",
            "steps": [{"name": "s1", "action": "echo"}],
            "execution": {"cache_ttl": 300},
        }
        mock_val.return_value = []
        mock_budget.return_value = {"ok": True, "budget": {}}

        # 缓存命中后不应调用 resolve
        result = execute_m1_workflow("test-exec-cache")

    mock_resolve.assert_not_called()
    assert result["workflow"] == "test-exec-cache"
    assert result["steps"][0]["name"] == "cached-step"


def test_executor_cache_miss_calls_backend() -> None:
    """缓存未命中时正常调用 backend"""
    from ecos.workflow.executor import execute_m1_workflow

    with (
        patch("ecos.workflow.executor.load_workflow") as mock_load,
        patch("ecos.workflow.executor.resolve") as mock_resolve,
        patch("ecos.workflow.executor.validate_workflow") as mock_val,
        patch("ecos.workflow.executor.X2BudgetDeducer.check_budget") as mock_budget,
    ):
        mock_load.return_value = {
            "name": "test-no-cache",
            "steps": [{"name": "s1", "action": "echo"}],
            "execution": {},  # 无 cache_ttl
        }
        mock_val.return_value = []
        mock_budget.return_value = {"ok": True, "budget": {}}
        mock_resolve.return_value = lambda wf, params: {
            "steps": [{"name": "fresh-step", "status": "ok"}],
            "passed": 1,
            "failed": 0,
        }

        result = execute_m1_workflow("test-no-cache")

    assert mock_resolve.called
    assert result["passed"] == 1


def test_executor_writes_cache_after_backend() -> None:
    """执行完成后，如果 M1 配置了 cache_ttl，写入缓存"""
    from ecos.workflow.executor import execute_m1_workflow

    with (
        patch("ecos.workflow.executor.load_workflow") as mock_load,
        patch("ecos.workflow.executor.resolve") as mock_resolve,
        patch("ecos.workflow.executor.validate_workflow") as mock_val,
        patch("ecos.workflow.executor.X2BudgetDeducer.check_budget") as mock_budget,
        patch("ecos.workflow.executor.X2BudgetDeducer.deduct"),
        patch("ecos.workflow.executor.check_execution_result"),
        patch("ecos.workflow.executor.X3CostRecorder.record"),
        patch("ecos.workflow.executor.generate_m0_snapshot"),
        patch("ecos.workflow.executor.log_operation"),
    ):
        mock_load.return_value = {
            "name": "m1-cache-test",
            "steps": [{"name": "s1", "action": "echo"}],
            "execution": {"cache_ttl": 300},
        }
        mock_val.return_value = []
        mock_budget.return_value = {"ok": True, "budget": {}}
        mock_resolve.return_value = lambda wf, params: {
            "steps": [{"name": "s1", "status": "ok", "summary": "done"}],
            "passed": 1,
            "failed": 0,
        }

        execute_m1_workflow("m1-cache-test")

    # 确认缓存已写入
    cached = cache.get("m1-cache-test", 0)
    assert cached is not None
    assert cached["passed"] == 1
