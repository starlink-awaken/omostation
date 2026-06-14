"""L1 运行时层 — 跨机通信协议

实现多机协作的运行时组件：
- CommunicationProtocol: 跨机通信协议
- StateSyncService: 状态同步服务
- FailoverExecutor: 故障转移执行器
- LoadBalancerExecutor: 负载均衡执行器
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


class ProtocolType(Enum):
    """协议类型"""
    TCP = "tcp"
    WEBSOCKET = "websocket"
    HTTP = "http"


class MessageType(Enum):
    """消息类型"""
    SYNC = "sync"
    HEARTBEAT = "heartbeat"
    TASK_ASSIGN = "task_assign"
    TASK_COMPLETE = "task_complete"
    FAILOVER = "failover"


@dataclass
class Message:
    """消息"""
    message_id: str
    message_type: MessageType
    source: str
    target: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CommunicationProtocol:
    """跨机通信协议
    
    L1 运行时: 实现跨机消息传递
    """
    
    def __init__(self, node_id: str, protocol_type: ProtocolType = ProtocolType.TCP):
        self.node_id = node_id
        self.protocol_type = protocol_type
        self.connections: dict[str, Any] = {}
        self.message_handlers: dict[MessageType, Callable] = {}
    
    def register_handler(self, message_type: MessageType, handler: Callable) -> None:
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
    
    def send(self, target: str, message: Message) -> bool:
        """发送消息"""
        # 简化实现：记录消息
        if target not in self.connections:
            self.connections[target] = []
        self.connections[target].append(message)
        return True
    
    def receive(self) -> Optional[Message]:
        """接收消息"""
        # 简化实现：返回空
        return None
    
    def broadcast(self, message: Message) -> bool:
        """广播消息"""
        for target in list(self.connections.keys()):
            self.send(target, message)
        return True
    
    def get_connections(self) -> list[str]:
        """获取连接列表"""
        return list(self.connections.keys())


class StateSyncService:
    """状态同步服务
    
    L1 运行时: 实现跨机状态同步
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.local_state: dict[str, Any] = {}
        self.sync_history: list[dict[str, Any]] = []
    
    def set_state(self, key: str, value: Any) -> None:
        """设置本地状态"""
        self.local_state[key] = value
    
    def get_state(self, key: str) -> Any:
        """获取本地状态"""
        return self.local_state.get(key)
    
    def sync_from(self, remote_state: dict[str, Any]) -> dict[str, Any]:
        """从远程同步状态"""
        changes = {}
        for key, value in remote_state.items():
            if key not in self.local_state or self.local_state[key] != value:
                self.local_state[key] = value
                changes[key] = value
        
        # 记录同步历史
        self.sync_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changes": list(changes.keys()),
        })
        
        return changes
    
    def get_sync_history(self) -> list[dict[str, Any]]:
        """获取同步历史"""
        return self.sync_history


class FailoverExecutor:
    """故障转移执行器
    
    L1 运行时: 执行故障转移操作
    """
    
    def __init__(self):
        self.failover_count: int = 0
        self.last_failover: Optional[datetime] = None
    
    def execute(self, source: str, target: str) -> bool:
        """执行故障转移"""
        self.failover_count += 1
        self.last_failover = datetime.now(timezone.utc)
        return True
    
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "failover_count": self.failover_count,
            "last_failover": self.last_failover.isoformat() if self.last_failover else None,
        }


class LoadBalancerExecutor:
    """负载均衡执行器
    
    L1 运行时: 执行负载均衡操作
    """
    
    def __init__(self):
        self.request_count: int = 0
        self.node_requests: dict[str, int] = {}
    
    def route(self, target: str) -> str:
        """路由请求"""
        self.request_count += 1
        self.node_requests[target] = self.node_requests.get(target, 0) + 1
        return target
    
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "request_count": self.request_count,
            "node_requests": self.node_requests,
        }
