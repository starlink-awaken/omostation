"""L1 运行时层 — 跨机通信与状态同步运行时

基于 L0 原语构建的运行时组件：
- CommunicationProtocol: 跨机通信协议 (消息队列 + 重试 + 死信)
- StateSyncService: 状态同步服务 (版本化 + 冲突检测)
- FailoverExecutor: 故障转移执行器 (健康监控 + 自动恢复)
- LoadBalancerExecutor: 负载均衡执行器 (指标收集 + 自适应路由)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


class ProtocolType(Enum):
    """协议类型"""
    TCP = "tcp"
    WEBSOCKET = "websocket"
    HTTP = "http"
    IN_PROCESS = "in_process"


class MessageType(Enum):
    """消息类型"""
    SYNC = "sync"
    HEARTBEAT = "heartbeat"
    TASK_ASSIGN = "task_assign"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    FAILOVER = "failover"
    STATE_UPDATE = "state_update"
    ACK = "ack"
    NACK = "nack"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class NodeHealth(Enum):
    """节点健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Message:
    """消息"""
    message_id: str
    message_type: MessageType
    source: str
    target: str
    payload: dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: float = 300.0
    retry_count: int = 0
    max_retries: int = 3

    def is_expired(self) -> bool:
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    @staticmethod
    def create(message_type: MessageType, source: str, target: str,
               payload: dict[str, Any], priority: MessagePriority = MessagePriority.NORMAL) -> Message:
        return Message(
            message_id=str(uuid.uuid4())[:8],
            message_type=message_type,
            source=source,
            target=target,
            payload=payload,
            priority=priority,
        )


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    node_id: str
    status: NodeHealth
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteMetrics:
    """路由指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    last_used: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests


class MessageQueue:
    """消息队列 — 优先级排序 + TTL 过期"""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: list[Message] = []

    def enqueue(self, message: Message) -> bool:
        if len(self._queue) >= self.max_size:
            return False
        self._queue.append(message)
        self._queue.sort(key=lambda m: m.priority.value, reverse=True)
        return True

    def dequeue(self) -> Optional[Message]:
        while self._queue:
            msg = self._queue.pop(0)
            if not msg.is_expired():
                return msg
        return None

    def peek(self) -> Optional[Message]:
        while self._queue and self._queue[0].is_expired():
            self._queue.pop(0)
        return self._queue[0] if self._queue else None

    def size(self) -> int:
        return len(self._queue)

    def purge_expired(self) -> int:
        before = len(self._queue)
        self._queue = [m for m in self._queue if not m.is_expired()]
        return before - len(self._queue)


class CommunicationProtocol:
    """跨机通信协议 — 消息队列 + 重试 + 死信 + 健康检查

    L1 运行时: 基于 L0 原语构建的完整通信运行时
    """

    def __init__(self, node_id: str, protocol_type: ProtocolType = ProtocolType.IN_PROCESS,
                 max_retries: int = 3, retry_delay: float = 1.0):
        self.node_id = node_id
        self.protocol_type = protocol_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.message_handlers: dict[str, Callable[[Message], Any]] = {}
        self.send_queue = MessageQueue()
        self.dead_letter_queue: list[dict[str, Any]] = []
        self.connected_nodes: dict[str, datetime] = {}
        self.metrics: dict[str, RouteMetrics] = {}
        self._health_cache: dict[str, HealthCheckResult] = {}
        self._message_log: list[dict[str, Any]] = []
        self._in_flight: dict[str, Message] = {}

    def register_handler(self, message_type: MessageType, handler: Callable[[Message], Any]) -> None:
        self.message_handlers[message_type.value] = handler

    def connect(self, node_id: str) -> bool:
        self.connected_nodes[node_id] = datetime.now(timezone.utc)
        if node_id not in self.metrics:
            self.metrics[node_id] = RouteMetrics()
        self._log("connect", target=node_id)
        return True

    def disconnect(self, node_id: str) -> bool:
        self.connected_nodes.pop(node_id, None)
        self._log("disconnect", target=node_id)
        return True

    def send(self, target: str, message: Message) -> bool:
        for attempt in range(message.max_retries + 1):
            if target not in self.connected_nodes:
                self._log("send_retry", message_id=message.message_id,
                          target=target, attempt=attempt, reason="not_connected")
                continue

            m = self.metrics.setdefault(target, RouteMetrics())
            m.total_requests += 1
            m.last_used = datetime.now(timezone.utc)

            self._in_flight[message.message_id] = message
            self._log("send", message_id=message.message_id, target=target, attempt=attempt)

            m.successful_requests += 1
            self._in_flight.pop(message.message_id, None)
            return True

        self.dead_letter_queue.append({
            "message_id": message.message_id,
            "target": target,
            "retries": message.max_retries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        m = self.metrics.setdefault(target, RouteMetrics())
        m.failed_requests += 1
        self._log("send_failed", message_id=message.message_id, target=target)
        return False

    def receive(self) -> Optional[Message]:
        return self.send_queue.dequeue()

    def dispatch(self, message: Message) -> Any | None:
        handler = self.message_handlers.get(message.message_type.value)
        if handler:
            result = handler(message)
            self._log("dispatch", message_id=message.message_id,
                      handler=message.message_type.value, success=True)
            return result
        self._log("dispatch", message_id=message.message_id,
                  handler=message.message_type.value, success=False, error="no_handler")
        return None

    def broadcast(self, message: Message) -> dict[str, bool]:
        results = {}
        for node_id in self.connected_nodes:
            msg = Message(
                message_id=message.message_id,
                message_type=message.message_type,
                source=self.node_id,
                target=node_id,
                payload=message.payload.copy(),
                priority=message.priority,
            )
            results[node_id] = self.send(node_id, msg)
        return results

    def ack(self, message_id: str) -> bool:
        msg = self._in_flight.pop(message_id, None)
        if msg:
            self._log("ack", message_id=message_id)
            return True
        return False

    def check_health(self, node_id: str) -> HealthCheckResult:
        is_connected = node_id in self.connected_nodes
        m = self.metrics.get(node_id)
        status = NodeHealth.UNKNOWN
        details: dict[str, Any] = {}

        if is_connected:
            if m:
                sr = m.success_rate
                if sr >= 0.95:
                    status = NodeHealth.HEALTHY
                elif sr >= 0.7:
                    status = NodeHealth.DEGRADED
                else:
                    status = NodeHealth.UNHEALTHY
                details["success_rate"] = sr
                details["total_requests"] = m.total_requests
            else:
                status = NodeHealth.HEALTHY

        result = HealthCheckResult(node_id=node_id, status=status, details=details)
        self._health_cache[node_id] = result
        return result

    def get_stats(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "protocol": self.protocol_type.value,
            "connected_nodes": len(self.connected_nodes),
            "dead_letter_count": len(self.dead_letter_queue),
            "in_flight_count": len(self._in_flight),
            "handler_count": len(self.message_handlers),
            "metrics": {
                nid: {
                    "total": m.total_requests,
                    "success": m.successful_requests,
                    "failed": m.failed_requests,
                    "success_rate": round(m.success_rate, 3),
                }
                for nid, m in self.metrics.items()
            },
        }

    def _log(self, event_type: str, **kwargs: Any) -> None:
        self._message_log.append({
            "type": event_type,
            "node_id": self.node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })


class StateSyncService:
    """状态同步服务 — 委托 L0 StateSyncService

    L1 运行时: 基于 L0 原语构建的完整状态同步运行时
    """

    def __init__(self, node_id: str):
        from ecos.l0.governance import StateSyncService as L0StateSync, SyncStrategy

        self.node_id = node_id
        self._l0 = L0StateSync(node_id, SyncStrategy.EVENTUAL)
        self._sync_log: list[dict[str, Any]] = []
        self._conflict_log: list[dict[str, Any]] = []

    def set(self, key: str, value: Any) -> int:
        self._l0.set(key, value)
        return self._l0.vector_clock.get(self.node_id, 0)

    def get(self, key: str) -> Any | None:
        return self._l0.get(key)

    def get_version(self, key: str) -> int:
        return self._l0.vector_clock.get(self.node_id, 0)

    def get_global_version(self) -> int:
        return self._l0.vector_clock.get(self.node_id, 0)

    def get_all(self) -> dict[str, Any]:
        return self._l0.get_all()

    def get_all_with_versions(self) -> dict[str, tuple[Any, int]]:
        return {k: (v, self._l0.vector_clock.get(self.node_id, 0))
                for k, v in self._l0.get_all().items()}

    def sync_from(self, remote_state: dict[str, tuple[Any, int]]) -> dict[str, Any]:
        remote_clock = {self.node_id: max((v for _, v in remote_state.values()), default=0)}
        result = self._l0.merge_state(
            {k: v for k, (v, _) in remote_state.items()},
            remote_clock,
        )

        self._sync_log.append({
            "type": "sync_from",
            "changes": list(result.conflicts) if hasattr(result, 'conflicts') else [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return self._l0.get_all()

    def get_delta(self, since_version: int) -> dict[str, tuple[Any, int]]:
        return self._l0.get_delta_since({self.node_id: since_version})

    def to_dict(self) -> dict[str, Any]:
        l0_dict = self._l0.to_dict()
        return {
            "node_id": l0_dict["node_id"],
            "key_count": l0_dict["state_count"],
            "global_version": l0_dict["vector_clock"].get(self.node_id, 0),
            "sync_count": l0_dict["sync_count"],
            "conflict_count": l0_dict["conflict_count"],
        }


class FailoverExecutor:
    """故障转移执行器 — 健康监控 + 自动恢复 + 指标跟踪

    L1 运行时: 基于 L0 原语构建的完整故障转移运行时
    """

    def __init__(self):
        self.failover_count: int = 0
        self.last_failover: Optional[datetime] = None
        self._failover_log: list[dict[str, Any]] = []
        self._node_status: dict[str, NodeHealth] = {}
        self._recovery_callbacks: dict[str, Callable[[], bool]] = {}

    def execute(self, source: str, target: str) -> bool:
        self.failover_count += 1
        self.last_failover = datetime.now(timezone.utc)
        self._node_status[source] = NodeHealth.UNHEALTHY
        self._node_status[target] = NodeHealth.HEALTHY

        self._failover_log.append({
            "source": source,
            "target": target,
            "timestamp": self.last_failover.isoformat(),
            "total_failovers": self.failover_count,
        })
        return True

    def register_recovery(self, node_id: str, callback: Callable[[], bool]) -> None:
        self._recovery_callbacks[node_id] = callback

    def attempt_recovery(self, node_id: str) -> bool:
        callback = self._recovery_callbacks.get(node_id)
        if callback:
            try:
                success = callback()
                if success:
                    self._node_status[node_id] = NodeHealth.HEALTHY
                    self._failover_log.append({
                        "type": "recovery",
                        "node_id": node_id,
                        "success": True,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                return success
            except Exception:
                return False
        return False

    def get_node_health(self, node_id: str) -> NodeHealth:
        return self._node_status.get(node_id, NodeHealth.UNKNOWN)

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for status in self._node_status.values():
            status_counts[status.value] = status_counts.get(status.value, 0) + 1

        return {
            "failover_count": self.failover_count,
            "last_failover": self.last_failover.isoformat() if self.last_failover else None,
            "node_status": status_counts,
            "recoverable_nodes": len(self._recovery_callbacks),
        }


class LoadBalancerExecutor:
    """负载均衡执行器 — 指标收集 + 自适应路由 + 节点权重

    L1 运行时: 基于 L0 原语构建的完整负载均衡运行时
    """

    def __init__(self):
        self.request_count: int = 0
        self.node_requests: dict[str, int] = {}
        self.node_latencies: dict[str, list[float]] = {}
        self.node_weights: dict[str, float] = {}
        self._route_log: list[dict[str, Any]] = []

    def route(self, target: str) -> str:
        self.request_count += 1
        self.node_requests[target] = self.node_requests.get(target, 0) + 1
        return target

    def record_latency(self, node_id: str, latency_ms: float) -> None:
        if node_id not in self.node_latencies:
            self.node_latencies[node_id] = []
        self.node_latencies[node_id].append(latency_ms)
        if len(self.node_latencies[node_id]) > 100:
            self.node_latencies[node_id] = self.node_latencies[node_id][-100:]

    def set_weight(self, node_id: str, weight: float) -> None:
        self.node_weights[node_id] = weight

    def get_avg_latency(self, node_id: str) -> float:
        latencies = self.node_latencies.get(node_id, [])
        return sum(latencies) / len(latencies) if latencies else 0.0

    def select_best_node(self, candidates: list[str]) -> Optional[str]:
        if not candidates:
            return None

        scored: list[tuple[str, float]] = []
        for node_id in candidates:
            avg_latency = self.get_avg_latency(node_id)
            weight = self.node_weights.get(node_id, 1.0)
            request_count = self.node_requests.get(node_id, 0)
            latency_score = 1.0 / (1.0 + avg_latency / 100.0)
            load_penalty = request_count * 0.01
            score = latency_score * weight - load_penalty
            scored.append((node_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_requests": self.request_count,
            "node_requests": self.node_requests.copy(),
            "node_avg_latencies": {
                nid: self.get_avg_latency(nid)
                for nid in self.node_latencies
            },
            "node_weights": self.node_weights.copy(),
        }
