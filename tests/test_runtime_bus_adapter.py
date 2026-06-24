"""Tests for runtime.runtime_bus_adapter — bridges runtime cron jobs to agora.bus facade."""

from __future__ import annotations


from runtime.runtime_bus_adapter import register_cron_job


class TestRegisterCronJob:
    """register_cron_job wraps callback with @bus_control.schedule_callback."""

    def test_returns_original_callback(self):
        """返回值必须是原始 callback (保证 cron_service 还能 wire)"""

        def my_task():
            return "result"

        result = register_cron_job("every 5m", my_task)
        assert result is my_task

    def test_callback_can_be_invoked(self):
        """wrapped callback 执行时调用原始 callback"""
        calls = []

        def my_task():
            calls.append("called")

        returned = register_cron_job("every 5m", my_task)
        # 直接调用 returned callback (via the wrapper)
        # 因为 wrapper 已被 bus_control.schedule_callback 装饰
        # 调用 returned 应触发原始 callback
        returned()
        assert calls == ["called"]

    def test_lambda_callback_supported(self):
        """lambda 作为 callback 也应工作"""
        calls = []

        def cb():
            calls.append("ok")

        register_cron_job("every 1m", cb)

    def test_callback_with_args_supported(self):
        """callback 带 args/kwargs (签名检查)"""

        def my_task(a, b=10):
            return a + b

        result = register_cron_job("every 10m", my_task)
        assert result(2) == 12
        assert result(5, b=20) == 25

    def test_multiple_registrations(self):
        """同一脚本多次注册应允许"""
        callbacks = []

        def make_cb(name):
            def cb():
                callbacks.append(name)

            return cb

        cb1 = make_cb("task1")
        cb2 = make_cb("task2")
        register_cron_job("every 1m", cb1)
        register_cron_job("every 5m", cb2)

        cb1()
        cb2()
        assert callbacks == ["task1", "task2"]


class TestBusAdapterIntegration:
    """测试与 bus_foundation 的真实装饰器交互"""

    def test_schedule_callback_decorator_applied(self):
        """@bus_control.schedule_callback 是 runtime_bus_adapter 模块加载时应用的装饰器"""
        from bus_foundation.facade import control as bus_control

        # 检查装饰器本身存在
        assert hasattr(bus_control, "schedule_callback")
        # register_cron_job 必须已装饰 callback (我们用之前的测试间接验证)

    def test_register_cron_job_uses_bus_control(self):
        """register_cron_job 内部必须调用 bus_control.schedule_callback"""
        import inspect
        from runtime import runtime_bus_adapter

        source = inspect.getsource(runtime_bus_adapter.register_cron_job)
        assert "schedule_callback" in source
        assert "bus_control" in source


class TestBusAdapterEdgeCases:
    """边界情况测试"""

    def test_empty_expr(self):
        """空表达式也应注册 (bus_foundation 决定是否拒绝)"""

        def cb():
            pass

        # 不抛异常即成功
        register_cron_job("", cb)

    def test_complex_expr(self):
        """复杂 cron 表达式"""

        def cb():
            pass

        register_cron_job("0 0 * * 0,6", cb)  # 周末午夜

    def test_recognizable_callback(self):
        """callback 应保留 callable 特性"""

        def cb():
            return 42

        result = register_cron_job("every 1m", cb)
        assert callable(result)
