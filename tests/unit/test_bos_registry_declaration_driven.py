"""4.1 声明驱动测试 — 从 bos-services.yaml 自动校验所有 active internal 服务.

声明驱动: 任何新增的 internal 服务声明 (status=active) 自动被本测试覆盖 —
校验 func 可解析 + 参数契约 (dict 或 named 被 api 智能适配). 防"声明但不可执行"回归.
外部包 (aetherforge/omo/bus_foundation/kairon) 环境性跳过.
"""

from __future__ import annotations

import importlib
import inspect

import pytest
import yaml

from agora.mcp.resolver.services import POC_SERVICES

_EXTERNAL = ("aetherforge.", "omo.", "bus_foundation.", "kairon.")


def _declared_internal_services() -> list[tuple[str, str, str]]:
    """从 bos-services.yaml 提取 active internal 服务 (uri, module_path, func_name)."""
    services = []
    for s in POC_SERVICES:
        if s.transport == "internal" and s.func_name:
            if s.module_path.startswith(_EXTERNAL):
                continue  # 外部包环境性
            services.append((s.uri, s.module_path, s.func_name))
    return services


@pytest.mark.parametrize("uri,module_path,func_name", _declared_internal_services())
def test_declared_internal_func_resolvable(uri, module_path, func_name):
    """声明驱动的 func 可解析校验."""
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    assert callable(fn), f"{module_path}.{func_name} 不可调用"


@pytest.mark.parametrize("uri,module_path,func_name", _declared_internal_services())
def test_declared_internal_contract_compatible(uri, module_path, func_name):
    """声明驱动的契约校验: 首参 dict (args/arguments) 或被 api named 适配."""
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    params = list(inspect.signature(fn).parameters.values())
    if not params:
        return  # 无参函数合法
    first = params[0]
    # 合法契约: 首参 args/arguments (dict) 或 named 参数 (api 按 kwargs 展开)
    assert first.name not in ("args", "arguments") or (
        first.annotation is inspect.Parameter.empty or "dict" in str(first.annotation)
    ), f"{uri} args 参数但非 dict 注解"


def test_declaration_vs_execution_gap_closed():
    """DECL_EXEC_GAP 闭环: 除外部包外, 无 active internal 服务不可解析."""
    broken = []
    for uri, module_path, func_name in _declared_internal_services():
        try:
            importlib.import_module(module_path)
        except ModuleNotFoundError:
            broken.append(f"{uri} (module {module_path} 缺失)")
    assert not broken, f"声明但不可执行: {broken}"
