"""跨包集成测试 — 验证核心包间交互是否正常。

测试会跳过未安装的包（非关键失败），只验证已安装包的基本可导入性。
"""

from __future__ import annotations

import importlib

import pytest


def _import(module: str):
    """尝试导入，skip 如果不可用。"""
    try:
        return importlib.import_module(module)
    except ImportError:
        pytest.skip(f"{module} not installed")


def test_core_models():
    from core_models.entity import Entity

    assert Entity is not None


def test_llm_gateway():
    m = _import("llm_gateway.provider")
    assert m.MockLLMProvider().provider_name == "mock"


def test_shared_lib():
    m = _import("kairon_lib.core.events")
    assert hasattr(m, "EventBusProtocol")


def test_codeanalyze():
    m = _import("codeanalyze.mcp")
    assert hasattr(m, "FORMAT_VERSION")


def test_agora():
    m = _import("agora.service_base")
    assert hasattr(m, "Service")


def test_cron_service():
    m = _import("cron_service.server")
    assert hasattr(m, "app")


def test_eidos():
    m = _import("eidos")
    assert m is not None


def test_kos():
    m = _import("kos")
    assert m is not None


def test_sophia():
    _import("sophia")


def test_minerva():
    _import("minerva")


def test_iris():
    _import("iris")


def test_symphony_protocol():
    _import("symphony_protocol")


def test_llm_gateway_adapters():
    """验证 LLM 统一适配器可导入。"""
    _import("llm_gateway.providers.legacy_ontoderive_adapter")
    _import("llm_gateway.providers.legacy_minerva_adapter")
    _import("llm_gateway.providers.legacy_ssot_adapter")
