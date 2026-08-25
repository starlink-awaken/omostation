"""B.D.S.K. 虚拟董事会与 AetherForge (oMLXC edge compute) 深度协同与全链路 Smoke 测试。"""

from __future__ import annotations

import json
import re
import sys
import time
from hashlib import sha256
from pathlib import Path
import pytest
import yaml

from agora.mcp.bos_resolver import list_services
from agora.mcp.bos_router import bos_router
from agora.mcp.resolver.services import _fallback_services
from agora.mcp.resolver.services_types import (
    BOS_URI_DOMAIN_PATTERN,
    BOS_URI_DOMAINS,
    BosService,
)
from agora.server.tools_bos import persona_bdsk_evaluate
from agora.server.tools_bos import bdsk


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
    assert "bos://compute/aetherforge/infer" in target_service.get("description", "")


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
async def test_bdsk_evaluate_routes_once_through_aetherforge_compute(monkeypatch):
    """Persona evaluation must be computed through the canonical BOS URI."""
    calls = []

    async def fake_resolve(uri, **kwargs):
        calls.append((uri, kwargs))
        payload = {
            "verdict": "REVIEW_REQUIRED",
            "risk_score": 41,
            "recommendation": "Require human review before execution.",
            "board_reviews": {
                role: {"opinion": f"{role} evidence"}
                for role in ("builder", "devil", "sage", "keeper")
            },
            "debate_log": [],
        }
        return {
            "status": "ok",
            "result": {"choices": [{"message": {"content": json.dumps(payload)}}]},
        }

    monkeypatch.setattr("agora.server.tools_bos.bdsk._invoke_compute", fake_resolve)
    res_deep = await persona_bdsk_evaluate(
        topic="引入边缘 MLX 计算网关执行推理分析",
        mode="deep",
        context="高敏感医疗与公文数据分析场景",
    )
    assert res_deep.get("status") == "ok"
    assert res_deep.get("proof_state") == "proven"
    assert res_deep.get("compute_uri") == "bos://compute/aetherforge/infer"
    assert res_deep.get("verdict") == "REVIEW_REQUIRED"
    assert res_deep.get("risk_score") == 41
    assert res_deep.get("topic_digest") == (
        "sha256:" + sha256("引入边缘 MLX 计算网关执行推理分析".encode()).hexdigest()
    )
    assert res_deep.get("context_digest") == (
        "sha256:" + sha256("高敏感医疗与公文数据分析场景".encode()).hexdigest()
    )
    assert "topic" not in res_deep
    assert "context" not in res_deep
    assert "高敏感医疗与公文数据分析场景" not in json.dumps(
        res_deep, ensure_ascii=False
    )
    reviews = res_deep.get("board_reviews", {})
    assert set(reviews) == {"builder", "devil", "sage", "keeper"}
    assert len(calls) == 1
    assert calls[0][0] == "bos://compute/aetherforge/infer"
    assert "引入边缘 MLX" in calls[0][1]["prompt"]


@pytest.mark.asyncio
async def test_bdsk_evaluate_compute_failure_is_not_proven(monkeypatch):
    async def fake_resolve(_uri, **_kwargs):
        return {"status": "error", "error": "daemon unavailable"}

    monkeypatch.setattr("agora.server.tools_bos.bdsk._invoke_compute", fake_resolve)
    res_fast = await persona_bdsk_evaluate(
        topic="紧急对齐 ADR-0300 规范文案",
        mode="fast",
    )
    assert res_fast.get("status") == "error"
    assert res_fast.get("proof_state") == "not_proven"
    assert res_fast.get("verdict") == "NOT_PROVEN"
    assert res_fast.get("compute_uri") == "bos://compute/aetherforge/infer"
    assert "daemon unavailable" not in str(res_fast)


@pytest.mark.asyncio
async def test_bdsk_private_inputs_are_rejected_before_compute(
    monkeypatch, caplog, tmp_path
):
    calls = []

    async def fake_resolve(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("privacy rejection must happen before compute")

    monkeypatch.setattr("agora.server.tools_bos.bdsk._invoke_compute", fake_resolve)
    private_inputs = [
        "/Users/example/private/board-proposal.md",
        "/opt/team/board-proposal.md",
        "/srv/board-proposal.md",
        "/a",
        "/",
        r"C:\\Users\\example\\private.txt",
        r"D:\\board\\proposal.txt",
        r"\\server\share\proposal.txt",
        "//server/share/proposal.txt",
        "sk-test-PRIVATE_SENTINEL_123456",
        "credential=PRIVATE_SENTINEL_DO_NOT_PERSIST",
        "topic-with-control\x00byte",
        "x" * 4_001,
    ]
    for private_input in private_inputs:
        result = await persona_bdsk_evaluate(private_input, context=private_input)
        serialized = json.dumps(result, ensure_ascii=False)
        assert result["status"] == "error"
        assert result["proof_state"] == "not_proven"
        assert result["error_code"] == "privacy_rejected"
        # Tiny paths such as "/" and "/a" are substrings of the canonical
        # compute URI, so resolver_calls=0 is their non-disclosure observable.
        if len(private_input) > 3:
            assert private_input not in serialized

    assert calls == []
    assert not list(tmp_path.iterdir())
    captured = caplog.text
    for private_input in private_inputs:
        assert private_input not in captured


@pytest.mark.asyncio
@pytest.mark.parametrize("echo_field", ["recommendation", "opinion", "token"])
async def test_bdsk_compute_output_cannot_echo_private_inputs(
    monkeypatch, caplog, tmp_path, echo_field
):
    topic = "board proposal PRIVATE_TOPIC_NONCE"
    context = "private context PRIVATE_CONTEXT_NONCE"

    async def fake_resolve(_uri, **_kwargs):
        recommendation = "Require bounded human review."
        opinions = {
            role: {"opinion": f"{role} evidence"}
            for role in ("builder", "devil", "sage", "keeper")
        }
        if echo_field == "recommendation":
            recommendation = f"Repeat: {topic}"
        elif echo_field == "opinion":
            opinions["devil"]["opinion"] = f"Leak: {context}"
        else:
            opinions["keeper"]["opinion"] = "sk-test-OUTPUT_SENTINEL_123456"
        payload = {
            "verdict": "REVIEW_REQUIRED",
            "risk_score": 50,
            "recommendation": recommendation,
            "board_reviews": opinions,
        }
        return {
            "status": "ok",
            "result": {"choices": [{"message": {"content": json.dumps(payload)}}]},
        }

    monkeypatch.setattr(bdsk, "_invoke_compute", fake_resolve)
    result = await persona_bdsk_evaluate(topic=topic, context=context)
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["status"] == "error"
    assert result["proof_state"] == "not_proven"
    assert result["error_code"] == "unsafe_compute_response"
    assert topic not in serialized
    assert context not in serialized
    assert "OUTPUT_SENTINEL_123456" not in serialized
    assert not list(tmp_path.iterdir())
    assert topic not in caplog.text
    assert context not in caplog.text


@pytest.mark.asyncio
async def test_bdsk_real_stdio_timeout_is_bounded_and_enforced(monkeypatch):
    """The persona's timeout must reach the real subprocess adapter."""
    service = BosService(
        uri="bos://compute/aetherforge/infer",
        domain="compute",
        package="aetherforge",
        action="infer",
        transport="stdio",
        command=[sys.executable, "-c", "import time; time.sleep(1)"],
    )
    monkeypatch.setattr(bdsk, "_COMPUTE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(bdsk, "_get_service", lambda _uri: service)

    started = time.monotonic()
    result = await persona_bdsk_evaluate(topic="random low sensitivity timeout nonce")
    elapsed = time.monotonic() - started

    assert elapsed < 0.8
    assert result["status"] == "error"
    assert result["proof_state"] == "not_proven"
    assert result["error_code"] == "compute_unavailable"


@pytest.mark.asyncio
async def test_bdsk_timeout_is_propagated_to_adapter_and_payload(monkeypatch):
    service = BosService(
        uri="bos://compute/aetherforge/infer",
        domain="compute",
        package="aetherforge",
        action="infer",
        transport="stdio",
        command=["aetherforge.cli"],
    )
    captured = {}

    class CapturingAdapter:
        def call(self, actual_service, **payload):
            captured["service"] = actual_service
            captured["payload"] = payload
            return {"status": "error"}

    def fake_adapter_factory(*, timeout):
        captured["adapter_timeout"] = timeout
        return CapturingAdapter()

    monkeypatch.setattr(bdsk, "_get_service", lambda _uri: service)
    monkeypatch.setattr(bdsk, "_get_stdio_adapter", fake_adapter_factory)

    result = await bdsk._invoke_compute(
        "bos://compute/aetherforge/infer", prompt="low sensitivity nonce"
    )

    assert result["status"] == "error"
    assert captured["service"] is service
    assert captured["adapter_timeout"] == 120.0
    assert captured["payload"]["timeout"] == 120.0
