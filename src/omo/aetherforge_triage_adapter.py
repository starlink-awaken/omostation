"""aetherforge_triage_adapter.py — omo ModelRouter → aetherforge triage server (HTTP).

守 CLAUDE.md (aetherforge): 跨层 (X 层 aetherforge → L2 omo) 走 HTTP (triage server),
   不直接 import aetherforge (避免绕 BOS/Agora 入口).
守 F11 (成本): cost_usd 从 consensus 响应读 + CostBudget 预算控制 (γ MVP).
守 F14 (断路器): CircuitBreaker 连续失败保护 (γ MVP, 参考 aetherforge circuit_breaker.py).
守 fabric 红线: server 不可用 / verdict=错误 / 超预算 / 断路器开 → 降级 StubModelRouter.

verdict → action 映射 (aetherforge 离散判定 → omo ModelDecision):
- 沉淀 → pass (入 KOS, 继续 journey)
- 提醒 → escalate (提醒类, 升级 Agent 注意)
- 丢弃 → human_veto (人工审, 守 F6)
- 错误/未知 → 降级 Stub

confidence 映射: consensus agreement (一致率 0-1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from omo.model_router import ModelDecision, ModelRouterProtocol, StubModelRouter

DEFAULT_TRIAGE_URL = "http://localhost:8095"


@dataclass
class CostBudget:
    """成本预算 (F11, omo 端轻量, 参考 aetherforge budget.py).

    累计 cost_estimate, 超预算 → 触发降级 (守 F11 成本控制).
    """

    max_budget: float = 1.0  # USD 累计上限
    accumulated: float = 0.0

    def consume(self, cost: float) -> bool:
        """消费成本, 返回是否在预算内 (False = 超预算)."""
        self.accumulated += cost
        return self.accumulated <= self.max_budget

    @property
    def exhausted(self) -> bool:
        return self.accumulated > self.max_budget


@dataclass
class CircuitBreaker:
    """断路器 (F14, omo 端轻量, 参考 aetherforge circuit_breaker.py).

    状态: CLOSED (正常) / OPEN (失败超阈值, 直接降级, 不再调 server).
    成功一次重置 (CLOSED). 简化版 (无 HALF_OPEN, omo 端够用).
    """

    max_failures: int = 3
    failure_count: int = 0
    state: str = "CLOSED"

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self.state = "OPEN"

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"

    @property
    def is_open(self) -> bool:
        return self.state == "OPEN"


class AetherforgeTriageAdapter:
    """omo ModelRouter → aetherforge triage server (HTTP, SOLID D 适配器).

    omo 端不 import aetherforge, 通过 HTTP 调 triage server (跨层解耦).
    server 不可用 / 错误 / 超预算 / 断路器开 → 降级 StubModelRouter (fabric 红线 + 渐进).
    γ MVP: CostBudget (F11) + CircuitBreaker (F14) 集成.
    """

    def __init__(
        self,
        *,
        server_url: str = DEFAULT_TRIAGE_URL,
        fallback: ModelRouterProtocol | None = None,
        timeout: float = 5.0,
        max_cost_budget: float = 1.0,
        max_failures: int = 3,
    ):
        self.server_url = server_url.rstrip("/")
        self.fallback = fallback or StubModelRouter()
        self.timeout = timeout
        self.cost_budget = CostBudget(max_budget=max_cost_budget)
        self.circuit_breaker = CircuitBreaker(max_failures=max_failures)

    def route(
        self, node: str, node_output: dict, *, scene_id: str
    ) -> ModelDecision:
        """ModelRouterProtocol 实现: 调 aetherforge consensus + 成本/断路器守约."""
        # 1. 断路器 OPEN → 直接降级 (F14, 不再调 server)
        if self.circuit_breaker.is_open:
            return self._fallback_route(
                node,
                node_output,
                scene_id,
                reason=f"circuit_breaker OPEN (failures={self.circuit_breaker.failure_count})",
            )

        # 2. 调 aetherforge consensus
        text = self._extract_text(node_output)
        try:
            resp = self._call_consensus(text)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            self.circuit_breaker.record_failure()
            return self._fallback_route(
                node, node_output, scene_id, reason=f"http error: {exc}"
            )

        if resp.get("verdict") in (None, "", "错误") or resp.get("error"):
            self.circuit_breaker.record_failure()
            return self._fallback_route(
                node,
                node_output,
                scene_id,
                reason=f"aetherforge verdict error: {resp.get('error') or resp.get('verdict')}",
            )

        # 3. 成本预算检查 (F11)
        cost = float(resp.get("cost_usd", 0.0))
        if not self.cost_budget.consume(cost):
            self.circuit_breaker.record_success()  # 调用成功 (但超预算)
            return self._fallback_route(
                node,
                node_output,
                scene_id,
                reason=(
                    f"cost budget exhausted "
                    f"({self.cost_budget.accumulated:.4f} > {self.cost_budget.max_budget})"
                ),
            )

        # 4. 成功: 重置断路器 + 映射决策
        self.circuit_breaker.record_success()
        return self._map_consensus(resp, node, scene_id)

    def _extract_text(self, node_output: dict) -> str:
        """从 node_output 提取分诊文本 (适配不同 scene node 结构)."""
        for key in ("text", "content", "doc", "draft", "title", "body"):
            val = node_output.get(key)
            if val:
                return str(val)
        # 序列化整个 output (保证有内容分诊)
        return json.dumps(node_output, ensure_ascii=False, default=str)

    def _call_consensus(self, text: str) -> dict:
        """HTTP POST /triage/consensus → aetherforge 两级共识."""
        url = f"{self.server_url}/triage/consensus"
        data = json.dumps({"text": text}).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _map_consensus(
        self, resp: dict, node: str, scene_id: str
    ) -> ModelDecision:
        """aetherforge consensus 响应 → omo ModelDecision."""
        verdict = str(resp.get("verdict", ""))
        agreement = float(resp.get("agreement", 0.0))
        cost = float(resp.get("cost_usd", 0.0))
        status = resp.get("status", "")

        # verdict → action 映射
        if verdict == "沉淀":
            action, confidence = "pass", agreement
        elif verdict == "提醒":
            action, confidence = "escalate", agreement
        elif verdict == "丢弃":
            action, confidence = "human_veto", 1.0 - agreement
        else:
            action, confidence = "human_veto", 0.0

        return ModelDecision(
            action=action,
            confidence=confidence,
            model_used=f"aetherforge-triage:{verdict}",
            cost_estimate=cost,  # 守 F11: 真实成本 (aetherforge tracker 记账)
            reason=(
                f"[{scene_id}/{node}] verdict={verdict} agreement={agreement:.2f}"
                f" status={status} (aetherforge consensus)"
            ),
        )

    def _fallback_route(
        self,
        node: str,
        node_output: dict,
        scene_id: str,
        *,
        reason: str,
    ) -> ModelDecision:
        """降级 StubModelRouter (fabric 红线: server 不可用/超预算/断路器开 不伪造)."""
        decision = self.fallback.route(node, node_output, scene_id=scene_id)
        # 标注降级原因 (audit trail)
        return ModelDecision(
            action=decision.action,
            confidence=decision.confidence,
            model_used=f"degraded→{decision.model_used}",
            cost_estimate=decision.cost_estimate,
            reason=f"{decision.reason} [降级: {reason}]",
        )


__all__ = [
    "DEFAULT_TRIAGE_URL",
    "AetherforgeTriageAdapter",
    "CircuitBreaker",
    "CostBudget",
]
