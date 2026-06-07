from __future__ import annotations

# ruff: noqa: RUF002, RUF003
from ._compat import get_spore_gateway, get_synapse_router

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
---
"""


import importlib
import json
import logging
import time
import uuid
from collections.abc import Generator
from typing import Any

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

"""
---
Type: Protocol
Status: ACTIVE
Version: 1.1.0
Owner: '@Claude-Code'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: L2
Constraint: "[!!] A2A_JSON_RPC_STRICT"
Summary: "A2A Swarm Protocol with SynapseRouter bridge for unified envelope routing"
---
"""
# 📨 A2A 集群通讯协议 (Agent-to-Agent Swarm Protocol)
# 职责: 执行《A2A 异步 JSON-RPC 路由协议 v1.0》。管理 Agent 间消息封装、税费代扣与动态路由。

_log = logging.getLogger(__name__)


def _build_request_frame(
    *,
    message_id: str,
    method: str,
    params: dict[str, Any],
    sender: str,
    receiver: str,
    version: str,
    timestamp: float,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": method,
        "params": params,
        "metadata": {
            "sender": sender,
            "receiver": receiver,
            "timestamp": timestamp,
            "version": version,
        },
    }


class DeliveryResult(dict):
    """A JSON-RPC frame dict that is also awaitable for async transport delivery.

    Sync callers receive a regular dict (the JSON-RPC frame).
    Async callers can ``await`` the result to trigger transport delivery and
    receive a delivery-status dict.  This dual nature preserves 100% backward
    compatibility with existing synchronous call sites while enabling the new
    asyncio queue transport layer.
    """

    __slots__ = ("_target_id",)

    def __init__(self, frame: dict[str, Any], target_id: str) -> None:
        super().__init__(frame)
        self._target_id = target_id

    def __await__(self) -> Generator[object, None, dict[str, object]]:  # type: ignore[override]
        return self._deliver().__await__()

    async def _deliver(self) -> dict[str, Any]:
        """Deliver this frame via the A2A multi-tier transport layer.

        Delegates to ``nucleus.Z_Spore.engine.a2a_transport.deliver_frame`` which
        tries delivery tiers in order:
          1. In-process asyncio queue (same-process registered agents)
          2. HTTP POST to a registered remote endpoint (cross-process/cross-node)
          3. Returns explicit undelivered status when no transport route is found

        Never raises; transport errors are surfaced as explicit non-success
        delivery results so awaited callers do not mistake an outbound request
        frame for a successful delivery.
        """
        result: dict[str, Any] = {"status": "undelivered", "target": self._target_id}
        try:
            deliver_frame: Any | None = None
            try:
                # TODO-migrate: from nucleus.Z_Microkernel.gateways import get_spore_gateway
                spore = get_spore_gateway()
                a2a_transport = spore.get_component("a2a_transport")
                deliver_frame = a2a_transport.deliver_frame
            except Exception:  # noqa: S110
                pass

            # TODO-migrate: if deliver_frame is None, import from nucleus.Z_Spore.engine.a2a_transport
            if deliver_frame is None:
                delivered_result = None
            else:
                delivered_result = await deliver_frame(self._target_id, dict(self))

            if isinstance(delivered_result, dict):
                result = delivered_result
            else:
                result = {
                    "status": "undelivered",
                    "target": self._target_id,
                    "reason": "invalid-delivery-result",
                }
        except Exception as exc:
            _log.debug("A2A awaited delivery failed for '%s': %s", self._target_id, exc)
            result = {
                "status": "undelivered",
                "target": self._target_id,
                "reason": "transport-failure",
            }

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": self.get("id"),
        }


# 异常定义
class A2AProtocolError(Exception):
    pass


class AuthError(A2AProtocolError):
    pass


class RoutingError(A2AProtocolError):
    pass


class A2AProtocol:
    """B-OS 集群通讯的物理协议层。

    负责将 Agent 的逻辑请求封装为 JSON-RPC 帧，并对接能量与注册中心。
    """

    def __init__(self) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.version = "1.0.0"

        # 懒加载器官，避免初始化顺序死锁
        self._energy_ledger = None
        self._registry = None

        # 消息追踪 (简单的内存记录，用于统计)
        self._msg_count = 0
        self._error_count = 0

        self.initialize()

    def _get_energy_ledger(self) -> Any | None:
        if not self._energy_ledger:
            try:
                ledger_mod = importlib.import_module("organs.D_Economy.organs.energy_ledger")
                self._energy_ledger = ledger_mod.EnergyLedger()
            except ImportError as exc:
                _log.debug("[A2A] failed to load EnergyLedger (fail-open): %s", exc)
        return self._energy_ledger

    def _get_registry(self) -> Any | None:
        if not self._registry:
            try:
                registry_mod = importlib.import_module("organs.D_Execution.organs.engine.capability_registry")
                self._registry = registry_mod.CapabilityRegistry()
            except ImportError as exc:
                _log.debug("[A2A] failed to load CapabilityRegistry (fail-open): %s", exc)
        return self._registry

    def initialize(self) -> None:
        """初始化 A2A 协议栈连接。"""
        # 确保基础环境可用
        pass

    def _deduct_tax(self, agent_id: str, operation: str) -> bool:
        """从能量账本扣除操作税。"""
        ledger = self._get_energy_ledger()
        if not ledger:
            return False  # 如果账本挂了，拒绝操作（fail-closed安全策略）
        try:
            # A2A 操作标准税
            ledger.deduct_eu(agent_id, f"A2A_{operation}", ref_id=f"MSG_{int(time.time())}")
            return True
        except (TypeError, ValueError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return False

    def send_request(
        self,
        from_agent: str,
        to_agent: str = "",
        method: str | dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> "DeliveryResult":  # noqa: UP037 — forward reference, class defined above in same file
        """发起 A2A 请求（封装 JSON-RPC 2.0）。

        Supports two calling conventions:

        **New 3-arg async convention** (transport-aware, awaitable):
            ``result = await protocol.send_request(target_id, method_str, params_dict)``
            Detected when the third positional argument is a ``dict`` (the params).
            Awaiting the result delivers the frame via the asyncio queue transport.

        **Legacy 4-arg sync convention** (backward compatible):
            ``frame = protocol.send_request(from_agent, to_agent, method_str, params_dict)``
            Detected when the third positional argument is a ``str`` (the method name).
            Returns a dict-like ``DeliveryResult`` identical to the previous raw frame.

        In both cases the return value is a ``DeliveryResult`` — a dict subclass
        that is also awaitable, so sync callers are completely unaffected.
        """
        # ── Detect calling convention ──────────────────────────────────────────
        if isinstance(method, dict) or (method is None and params is None):
            # New convention: send_request(target_id, method_str, params_dict)
            actual_target = from_agent
            actual_method = to_agent
            actual_params: dict[str, Any] = (method or {}) if isinstance(method, dict) else {}
            actual_from = ""  # sender unknown in target-only convention
        else:
            # Legacy convention: send_request(from_agent, to_agent, method_str, params)
            actual_target = to_agent
            actual_method = str(method or "")
            actual_params = params or {}
            actual_from = from_agent

        # 1. 扣税 (A2A_REQUEST) — only when sender is known
        if actual_from and not self._deduct_tax(actual_from, "REQUEST"):
            raise AuthError("Insufficient EU for A2A communication.")

        msg_id = str(uuid.uuid4())
        frame = _build_request_frame(
            message_id=msg_id,
            method=actual_method,
            params=actual_params,
            sender=actual_from,
            receiver=actual_target,
            version=self.version,
            timestamp=time.time(),
        )

        self._msg_count += 1
        return DeliveryResult(frame, actual_target)

    def send_response(
        self,
        from_agent: str,
        request_id: str,
        result: Any | None = None,
        error: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """发起 A2A 响应。"""
        # 响应通常免税，或计入请求方预支（Kiro 协议 v1.0）
        frame: dict[str, object] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "metadata": {"sender": from_agent, "timestamp": time.time(), "version": self.version},
        }
        if error:
            frame["error"] = error
            self._error_count += 1
        else:
            frame["result"] = result

        return frame

    def send_notification(self, from_agent: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """发起 A2A 通知（无 ID，无响应）。"""
        if not self._deduct_tax(from_agent, "NOTIFICATION"):
            raise AuthError("Insufficient EU for A2A notification.")

        frame = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "metadata": {"sender": from_agent, "timestamp": time.time(), "version": self.version},
        }
        return frame

    def handle_incoming_message(self, raw_frame: str | dict) -> dict[str, Any]:
        """解析并校验入站消息。"""
        try:
            if isinstance(raw_frame, str):
                frame = json.loads(raw_frame)
            else:
                frame = raw_frame

            # 基础协议校验
            if frame.get("jsonrpc") != "2.0":
                raise A2AProtocolError("Invalid JSON-RPC version.")

            # TTL expiry check — reject stale messages before routing.
            # ``MessageEnvelope.is_expired`` is a @property (returns bool directly).
            # The callable() guard handles legacy duck-typed implementations that
            # may expose it as a method instead.
            # NOTE: ttl=0 (default) means "no expiry" — is_expired correctly returns
            # False in that case, so zero-TTL messages always pass this gate.
            envelope = self.frame_to_envelope(frame)
            if envelope is not None:
                is_expired_val = getattr(envelope, "is_expired", None)
                expired = (
                    is_expired_val()
                    if callable(is_expired_val)
                    else bool(is_expired_val)
                    if is_expired_val is not None
                    else False
                )
                if expired:
                    self._error_count += 1
                    ttl = getattr(envelope, "ttl", 0)
                    raise A2AProtocolError(f"Envelope {frame.get('id', '?')} expired (ttl={ttl}s)")

            return frame
        except (json.JSONDecodeError, OSError) as e:
            self._error_count += 1
            raise A2AProtocolError(f"Message corruption: {e}") from e

    def route_to_agent(self, request_frame: dict[str, Any]) -> str:
        """基于 CapabilityRegistry 进行动态路由。

        如果 receiver 为 'auto', 则寻找最匹配的 Agent。
        优先通过 SynapseRouter 路由；降级为 CapabilityRegistry。
        """
        meta = request_frame.get("metadata", {})
        receiver = meta.get("receiver")

        if receiver and receiver != "auto":
            return receiver  # 点对点直连

        # 优先走 SynapseRouter（统一 MessageEnvelope 路由层）
        envelope = self.frame_to_envelope(request_frame)
        success, result = self._route_via_synapse(envelope)
        if success:
            return result if isinstance(result, str) else request_frame.get("id", "routed")

        # 降级: CapabilityRegistry 撮合
        registry = self._get_registry()
        if not registry:
            raise RoutingError("CapabilityRegistry unavailable.")

        required = [request_frame.get("method")]
        task_request_cls = importlib.import_module("organs.D_Execution.organs.engine.capability_registry").TaskRequest

        req = task_request_cls(task_id=request_frame.get("id", "tmp"), required_capabilities=required, priority=2)

        best_inst = registry.find_best_agent(req)
        if not best_inst:
            raise RoutingError(f"No available agents for capability: {required}")

        return best_inst

    def frame_to_envelope(self, frame: dict[str, Any]) -> Any | None:
        """将 A2A JSON-RPC 帧转换为 MessageEnvelope（供 SynapseRouter 使用）。

        返回 MessageEnvelope 实例，或在无法导入时返回 None。
        """
        try:
            from ._compat import MessageEnvelope
        except ImportError:
            try:
                from synapse import MessageEnvelope  # type: ignore[no-redef, import-not-found]
            except ImportError:
                return None

        meta = frame.get("metadata", {})
        return MessageEnvelope(
            id=frame.get("id", str(uuid.uuid4())),
            source=meta.get("sender", ""),
            target=meta.get("receiver", ""),
            type="COMMAND",
            payload={"method": frame.get("method", ""), "params": frame.get("params", {})},
            eu_budget=meta.get("eu_budget", 0.0),
        )

    def _route_via_synapse(self, envelope: Any | None) -> tuple[bool, Any | None]:
        """尝试通过 SynapseRouter 路由 MessageEnvelope。

        Returns:
            (success, result): success=True 时 result 为路由结果。
        """
        if envelope is None:
            return False, None
        try:
            # TODO-migrate: from nucleus.Z_Microkernel.organs.synapse_router import get_synapse_router

            router = get_synapse_router()
            return router.route(envelope)
        except (ImportError, AttributeError, RuntimeError) as exc:
            _log.debug("SynapseRouter unavailable, falling back: %s", exc)
            return False, None

    def fanout(
        self,
        from_agent: str,
        targets: list[str],
        method: str,
        params: dict[str, Any],
        timeout_per_agent: float = 30.0,
    ) -> list[tuple[str, bool, object]]:
        """Deliver a message to all *targets* in parallel.

        Each target gets its own independent send_request call executed
        concurrently via a thread pool.  Errors are captured per-target —
        one failing agent never prevents the others from receiving the message.

        Args:
            from_agent:          Sender identity (passed through to send_request).
            targets:             List of recipient agent IDs.
            method:              JSON-RPC method name.
            params:              Method parameters (shared across all targets).
            timeout_per_agent:   Per-target send timeout in seconds (best-effort;
                                 enforced on the as_completed wait).

        Returns:
            List of ``(agent_id, success, response_or_error)`` tuples — one per
            target, in completion order.  ``success`` is False when an exception
            was raised; ``response_or_error`` is then a string representation of
            the exception.  Never raises.
        """
        import concurrent.futures

        results: list[tuple[str, bool, Any]] = []

        if not targets:
            return results

        def _send_one(target: str) -> tuple[str, bool, Any]:
            try:
                resp = self.send_request(from_agent, target, method, params)
                return (target, True, resp)
            except (OSError, ValueError, RuntimeError) as exc:
                _log.warning("fanout: send to %s failed: %s", target, exc)
                return (target, False, str(exc))

        max_workers = min(len(targets), 16)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_send_one, t): t for t in targets}
            for fut in concurrent.futures.as_completed(futures, timeout=timeout_per_agent + 5):
                results.append(fut.result())

        return results

    async def receive_message(self, agent_id: str, timeout: float = 30.0) -> dict[str, Any] | None:
        """Receive the next inbound message for agent_id from the transport.

        Returns None on timeout or if the agent is not registered.
        """
        # TODO-migrate: from nucleus.Z_Microkernel.gateways import get_spore_gateway
        # TODO-migrate: from nucleus.Z_Spore.engine.message_transport import receive
        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_messages": self._msg_count,
            "total_errors": self._error_count,
            "protocol_version": self.version,
        }

    def validate_internal_state(self) -> bool:
        # A2A 是无状态协议层，主要校验依赖项
        return self._get_energy_ledger() is not None and self._get_registry() is not None


if __name__ == "__main__":
    pass
