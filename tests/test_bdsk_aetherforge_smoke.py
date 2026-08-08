"""B.D.S.K. 虚拟董事会与 AetherForge (oMLXC edge compute) 深度协同与全链路 Smoke 测试。"""

from __future__ import annotations

import re
from pathlib import Path
import pytest
import yaml

from agora.mcp.bos_resolver import list_services
from agora.mcp.bos_router import bos_router
from agora.mcp.resolver.services import _fallback_services
from agora.mcp.resolver.services_types import BOS_URI_DOMAIN_PATTERN, BOS_URI_DOMAINS
from agora.server.tools_bos import persona_bdsk_evaluate


def test_aetherforge_compute_domain_and_fallback_services():
    """验证 compute 域正式纳入 BOS 体系且 AetherForge 端点在静态 fallback 注册表中零遗漏。"""
    assert "compute" in BOS_URI_DOMAINS
    assert "persona" in BOS_URI_DOMAINS

    pattern = re.compile(BOS_URI_DOMAIN_PATTERN)
    assert pattern.match("compute")
    assert pattern.match("persona")

    fallback_uris = [s.uri for s in _fallback_services()]
    assert "bos://persona/bdsk/evaluate" in fallback_uris
    assert "bos://compute/aetherforge/infer" in fallback_uris
    assert "bos://compute/aetherforge/mesh" in fallback_uris
    assert "bos://compute/aetherforge/profile" in fallback_uris

    for service in _fallback_services():
        if service.uri == "bos://compute/aetherforge/infer":
            assert service.domain == "compute"
            assert service.package == "aetherforge"
            assert service.transport == "stdio"
            assert "aetherforge.cli" in service.command


def test_bdsk_evaluate_yaml_active_route():
    """验证 bos-services.yaml 中 bos://persona/bdsk/evaluate 的 i0_route 已经由 pending 升级为 active。"""
    cfg_file = Path(__file__).resolve().parents[1] / "etc" / "bos-services.yaml"
    assert cfg_file.exists()
    data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    services = data.get("services", [])

    target_service = None
    for s in services:
        if s.get("uri") == "bos://persona/bdsk/evaluate":
            target_service = s
            break

    assert target_service is not None, (
        "未在 bos-services.yaml 中找到 bos://persona/bdsk/evaluate"
    )
    assert target_service.get("i0_route") == "active", "i0_route 应激活为 active"
    assert target_service.get("transport") == "internal"
    assert target_service.get("module_path") == "agora.server.tools_bos"


def test_bos_router_resolves_aetherforge_and_bdsk():
    """验证 BOSRouter 针对 AetherForge 和 B.D.S.K. 服务能准确完成 O(k) 前缀路由发现。"""
    bos_router.seed_from_poc(list_services())

    route_eval = bos_router.resolve("bos://persona/bdsk/evaluate")
    assert route_eval is not None
    assert route_eval["config"]["domain"] == "persona"
    assert route_eval["config"]["action"] == "evaluate"

    route_infer = bos_router.resolve("bos://compute/aetherforge/infer")
    assert route_infer is not None
    assert route_infer["config"]["domain"] == "compute"
    assert route_infer["config"]["action"] == "infer"

    route_mesh = bos_router.resolve("bos://compute/aetherforge/mesh")
    assert route_mesh is not None
    assert route_mesh["config"]["domain"] == "compute"


@pytest.mark.asyncio
async def test_bdsk_evaluate_deep_and_fast_modes():
    """测试 @Builder/@Devil/@Sage/@Keeper 4角对不同研发决策场景的并发审查。"""
    res_deep = await persona_bdsk_evaluate(
        topic="引入边缘 MLX 计算网关执行推理分析",
        mode="deep",
        context="高敏感医疗与公文数据分析场景",
    )
    assert res_deep.get("status") == "ok"
    assert res_deep.get("verdict") in ("PROCEED_WITH_GUARDRAILS", "APPROVED")
    reviews = res_deep.get("board_reviews", {})
    assert "builder" in reviews
    assert "devil" in reviews
    assert "sage" in reviews
    assert "keeper" in reviews

    res_fast = await persona_bdsk_evaluate(
        topic="紧急对齐 ADR-0300 规范文案",
        mode="fast",
    )
    assert res_fast.get("status") == "ok"
    assert res_fast.get("verdict") == "PROCEED_FAST"
