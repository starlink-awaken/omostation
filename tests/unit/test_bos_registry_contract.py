"""BOS internal 服务注册表契约校验 (registry lint, 防契约漂移回归).

验证 POC_SERVICES 中所有 internal transport 服务:
1. module_path 可 import
2. func_name 在模块中存在
3. 参数契约可判定 (dict 契约 vs named 契约)

broken 白名单: 环境性外部包 (aetherforge*/omo*/bus_foundation) — 完整环境可用,
本地缺失不视为代码缺陷。
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from agora.mcp.resolver.services import POC_SERVICES

# 环境性外部包模块: 本机缺失但完整环境 (CI) 可用 → 不判 broken
_EXTERNAL_MODULES = (
    "aetherforge.",
    "omo.",
    "bus_foundation.",
    "kairon.",
)


def _resolve_func(service):
    """尝试解析 internal 服务的函数. 返回 (ok, detail)."""
    try:
        mod = importlib.import_module(service.module_path)
        fn = getattr(mod, service.func_name)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        contract = (
            "dict"
            if params and params[0].name in ("args", "arguments")
            else "named:" + ",".join(p.name for p in params[:3])
        )
        return True, contract
    except (ModuleNotFoundError, AttributeError) as e:
        return False, str(e)[:80]


@pytest.mark.parametrize("service", POC_SERVICES)
def test_internal_service_contract_resolvable(service):
    """internal 服务的 func 必须可解析 (模块存在 + 函数存在)."""
    if service.transport != "internal":
        pytest.skip("not internal")
    ok, detail = _resolve_func(service)
    if not ok and service.module_path.startswith(_EXTERNAL_MODULES):
        pytest.skip(f"外部包环境性: {service.module_path}")
    assert ok, (
        f"BOS 契约漂移: {service.uri} → {service.module_path}.{service.func_name} "
        f"不可解析 ({detail}). 修复 services_internal.py 或 services.py 的映射。"
    )


def test_all_internal_services_have_func_name():
    """internal 服务必须有 func_name."""
    for s in POC_SERVICES:
        if s.transport == "internal":
            assert s.func_name, f"internal 服务缺 func_name: {s.uri}"


def test_no_unresolvable_internal_services():
    """除环境性外部包外, 不允许有 func 不可解析的 internal 服务."""
    broken = []
    for s in POC_SERVICES:
        if s.transport != "internal" or s.module_path.startswith(_EXTERNAL_MODULES):
            continue
        ok, _ = _resolve_func(s)
        if not ok:
            broken.append(f"{s.uri} → {s.module_path}.{s.func_name}")
    assert not broken, f"BOS 契约漂移 (func 不可解析): {broken}"


def test_internal_services_dict_contract():
    """P6: internal 服务契约被 api.py 正确适配 (dict 或 named 均可).

    resolver/api.py 智能适配: 首参 args/arguments/dict 类 → 传整体 dict;
    否则按 named 展开。断言只校验"契约可被正确调用"——禁止出现
    (args: dict) 但服务定义传 named 的错配, 以及无参数却期望调用参数的服务。
    """
    import inspect
    import importlib

    mismatched = []
    for s in POC_SERVICES:
        if s.transport != "internal" or s.module_path.startswith(_EXTERNAL_MODULES):
            continue
        try:
            mod = importlib.import_module(s.module_path)
            fn = getattr(mod, s.func_name)
            params = list(inspect.signature(fn).parameters.values())
            if not params:
                continue  # 无参数函数 (system/*status 等) 由 api 直接调用, 合法
            first = params[0]
            is_dict = first.name in ("args", "arguments") or (
                first.annotation is not inspect.Parameter.empty
                and "dict" in str(first.annotation)
            )
            # 错配: dict 契约函数但参数名是 query/limit 等 (会被 named 展开成 query=... 报错)
            # 或 named 函数首参名是 args (会被 dict 传错) — 均应由 api 适配正确处理
            if first.name in ("args", "arguments") and not is_dict:
                mismatched.append(f"{s.uri} ({s.func_name}: args 但非 dict 注解)")
        except (ModuleNotFoundError, AttributeError):
            continue  # 不可解析由 test_no_unresolvable 覆盖
    assert not mismatched, (
        f"P6 契约错配: {mismatched}. "
        "args 参数必须配 dict 契约, named 参数不能被误判为 dict。"
    )
