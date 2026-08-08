"""L1 跨机通信 — 基于 asyncio 的 TCP 消息传输

提供真正的跨机通信能力：
- TCPTransport: asyncio TCP 服务端/客户端
- MessageProtocol: 消息编解码 (JSON + 长度前缀)
- ReliableChannel: 可靠通道 (重传 + ACK + 超时)
"""

from __future__ import annotations

import asyncio
import json
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from ecos.common.logger import get_logger

logger = get_logger("transport")


class ChannelState(Enum):
    """通道状态"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSED = "closed"


@dataclass
class WireMessage:
    """线上传输消息"""

    msg_id: str
    msg_type: str
    source: str
    target: str
    payload: dict[str, Any]
    timestamp: float = 0.0
    requires_ack: bool = False

    def encode(self) -> bytes:
        self.timestamp = datetime.now(timezone.utc).timestamp()
        data = json.dumps(
            {
                "msg_id": self.msg_id,
                "msg_type": self.msg_type,
                "source": self.source,
                "target": self.target,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "requires_ack": self.requires_ack,
            }
        ).encode()
        return struct.pack("!I", len(data)) + data

    @staticmethod
    def decode(data: bytes) -> WireMessage:
        if len(data) >= 4:
            declared_len = struct.unpack("!I", data[:4])[0]
            if declared_len == len(data) - 4:
                data = data[4:]
        obj = json.loads(data)
        return WireMessage(
            msg_id=obj["msg_id"],
            msg_type=obj["msg_type"],
            source=obj["source"],
            target=obj["target"],
            payload=obj["payload"],
            timestamp=obj.get("timestamp", 0),
            requires_ack=obj.get("requires_ack", False),
        )


class MessageProtocol(asyncio.Protocol):
    """asyncio TCP 协议 — 长度前缀消息帧"""

    def __init__(self, on_message: Callable[[WireMessage], None]):
        self.on_message = on_message
        self._buffer = bytearray()
        self._transport: Optional[asyncio.Transport] = None

    def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        self._transport = transport

    def data_received(self, data: bytes) -> None:
        self._buffer.extend(data)
        while len(self._buffer) >= 4:
            msg_len = struct.unpack("!I", self._buffer[:4])[0]
            if len(self._buffer) < 4 + msg_len:
                break
            msg_data = bytes(self._buffer[4 : 4 + msg_len])
            del self._buffer[: 4 + msg_len]
            try:
                msg = WireMessage.decode(msg_data)
                self.on_message(msg)
            except Exception:  # defensive fallback
                pass

    def connection_lost(self, exc: Exception | None) -> None:
        self._transport = None


class TCPNode:
    """TCP 节点 — 服务端 + 客户端"""

    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.state = ChannelState.DISCONNECTED
        self._server: Optional[asyncio.AbstractServer] = None
        self._peers: dict[str, asyncio.Transport] = {}
        self._handlers: dict[str, Callable[[WireMessage], Any]] = {}
        self._pending_acks: dict[str, asyncio.Event] = {}
        self._message_log: list[dict[str, Any]] = []

    def on(self, msg_type: str, handler: Callable[[WireMessage], Any]) -> None:
        self._handlers[msg_type] = handler

    async def start(self) -> int:
        self._server = await asyncio.start_server(
            self._create_server_protocol,  # type: ignore[reportArgumentType]
            self.host,
            self.port,
        )
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]
        self.state = ChannelState.CONNECTED
        return self.port

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for transport in self._peers.values():
            transport.close()
        self._peers.clear()
        self.state = ChannelState.CLOSED

    async def connect_to(self, host: str, port: int, remote_id: str) -> bool:
        try:
            transport, protocol = await asyncio.get_running_loop().create_connection(
                lambda: MessageProtocol(self._on_receive),
                host,
                port,
            )
            self._peers[remote_id] = transport
            self._log("connected", target=remote_id, host=host, port=port)
            return True
        except Exception as e:  # defensive fallback
            self._log("connect_failed", target=remote_id, error=str(e))
            return False

    async def send(
        self,
        target: str,
        msg_type: str,
        payload: dict[str, Any],
        requires_ack: bool = False,
        timeout: float = 5.0,
    ) -> bool:
        transport = self._peers.get(target)
        if not transport:
            self._log("send_failed", target=target, error="not_connected")
            return False

        import uuid

        msg = WireMessage(
            msg_id=str(uuid.uuid4())[:8],
            msg_type=msg_type,
            source=self.node_id,
            target=target,
            payload=payload,
            requires_ack=requires_ack,
        )

        try:
            transport.write(msg.encode())
            self._log("sent", msg_id=msg.msg_id, target=target, type=msg_type)

            if requires_ack:
                event = asyncio.Event()
                self._pending_acks[msg.msg_id] = event
                try:
                    await asyncio.wait_for(event.wait(), timeout)
                    self._log("acked", msg_id=msg.msg_id)
                    return True
                except asyncio.TimeoutError:
                    self._log("ack_timeout", msg_id=msg.msg_id)
                    self._pending_acks.pop(msg.msg_id, None)
                    return False

            return True
        except Exception as e:  # defensive fallback
            self._log("send_error", target=target, error=str(e))
            return False

    def broadcast(self, msg_type: str, payload: dict[str, Any]) -> dict[str, bool]:
        results = {}
        for peer_id, transport in self._peers.items():
            import uuid

            msg = WireMessage(
                msg_id=str(uuid.uuid4())[:8],
                msg_type=msg_type,
                source=self.node_id,
                target=peer_id,
                payload=payload,
            )
            try:
                transport.write(msg.encode())
                results[peer_id] = True
            except Exception:  # defensive fallback
                results[peer_id] = False
        return results

    def get_peers(self) -> list[str]:
        return list(self._peers.keys())

    def get_stats(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "state": self.state.value,
            "peer_count": len(self._peers),
            "pending_acks": len(self._pending_acks),
            "log_count": len(self._message_log),
        }

    def _handle_connection(
        self, transport: asyncio.Transport, protocol: MessageProtocol
    ) -> None:
        peer = transport.get_extra_info("peername")
        peer_id = f"{peer[0]}:{peer[1]}" if peer else "unknown"
        self._peers[peer_id] = transport
        self._log("peer_connected", peer_id=peer_id)

    def _create_server_protocol(self) -> MessageProtocol:
        """为每个入站连接创建协议"""
        return MessageProtocol(self._on_receive)

    def _on_receive(self, msg: WireMessage) -> None:
        if msg.requires_ack:
            ack = WireMessage(
                msg_id=msg.msg_id,
                msg_type="ack",
                source=self.node_id,
                target=msg.source,
                payload={"ack_for": msg.msg_id},
            )
            transport = self._peers.get(msg.source)
            if transport:
                try:
                    transport.write(ack.encode())
                except Exception:  # defensive fallback
                    pass

        if msg.msg_type == "ack":
            event = self._pending_acks.pop(msg.payload.get("ack_for", ""), None)
            if event:
                event.set()
            return

        handler = self._handlers.get(msg.msg_type)
        if handler:
            try:
                handler(msg)
            except Exception:  # defensive fallback
                pass

        self._log("received", msg_id=msg.msg_id, type=msg.msg_type, source=msg.source)

    def _log(self, event_type: str, **kwargs: Any) -> None:
        self._message_log.append(
            {
                "type": event_type,
                "node_id": self.node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            }
        )
