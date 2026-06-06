"""
---
Type: Organ
Status: Active
Layer: L3
Summary: WebSocket server for real-time bidirectional communication with BOS clients.
Owner: bos-core
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
---
"""

from __future__ import annotations

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Ws Server ≡ Server
# 内涵 ≝ {Ws, Server}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, WsServer)}
# 功能 ⊢ {Ws_Server, Init_Ws, Validate_Server}
# =============================================================================
import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, NoReturn, Protocol, cast

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

from .auth_models import AuthenticatedUser, AuthenticationError
from .oauth2_server import OAuth2Server

if TYPE_CHECKING:
    from websockets.asyncio.server import Server as WebSocketServer
    from websockets.asyncio.server import ServerConnection as WebSocketServerProtocol
    from websockets.typing import Data, Subprotocol
else:
    type WebSocketServer = Any
    type WebSocketServerProtocol = Any
    type Data = str | bytes
    type Subprotocol = str


def _missing_serve(*args: Any, **kwargs: Any) -> NoReturn:
    raise RuntimeError("websockets library not installed")


_RuntimeConnectionClosed: type[Exception] = Exception

try:
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosed as _ImportedConnectionClosed

    WEBSOCKETS_AVAILABLE = True
except ImportError:  # pragma: no cover
    WEBSOCKETS_AVAILABLE = False
    serve = _missing_serve
else:
    _RuntimeConnectionClosed = _ImportedConnectionClosed


type JSONDict = dict[str, Any]


class _HandshakeRequest(Protocol):
    headers: Mapping[str, str]


type EventHandler = Callable[["WebSocketConnection", JSONDict], object]


@dataclass
class WebSocketConnection:
    """
    WebSocket 连接信息

    Attributes:
        connection_id: 连接 ID
        websocket: WebSocket 对象
        user: 认证用户
        connected_at: 连接时间
        last_activity: 最后活动时间
        channels: 订阅的频道
    """

    connection_id: int
    websocket: WebSocketServerProtocol
    user: AuthenticatedUser
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    channels: set[str] = field(default_factory=set)

    def update_activity(self) -> None:
        """更新最后活动时间"""
        self.last_activity = datetime.now()


@dataclass
class WebSocketEvent:
    """
    WebSocket 事件定义

    Attributes:
        type: 事件类型
        data: 事件数据
        channel: 频道 (可选)
        timestamp: 时间戳
    """

    type: str
    data: dict[str, Any]
    channel: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> JSONDict:
        """转换为字典"""
        return {
            "type": self.type,
            "data": self.data,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())


class WSServer:
    """
    WebSocket 服务器

    功能:
    1. 连接管理 - 维护客户端连接
    2. 事件推送 - 广播和单播事件
    3. 心跳检测 - 保持连接活跃
    4. 认证集成 - WebSocket 握手认证
    5. 频道订阅 - 基于频道的消息路由
    """

    def __init__(
        self,
        oauth2_server: OAuth2Server,
        host: str = "0.0.0.0",  # noqa: S104
        port: int = 8765,
        ping_interval: int = 30,
        ping_timeout: int = 10,
    ) -> None:
        """
        初始化 WebSocket 服务器

        Args:
            oauth2_server: OAuth2 服务器实例
            host: 监听地址
            port: 监听端口
            ping_interval: 心跳间隔 (秒)
            ping_timeout: 心跳超时 (秒)
        """
        self._oauth2_server = oauth2_server
        self._host = host
        self._port = port
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout

        # 连接存储
        self._connections: dict[int, WebSocketConnection] = {}
        self._user_connections: dict[str, set[int]] = {}  # user_id -> connection_ids
        self._channel_subscribers: dict[str, set[int]] = {}  # channel -> connection_ids

        # 事件处理器
        self._event_handlers: dict[str, list[EventHandler]] = {}

        # 运行状态
        self._running = False
        self._server: WebSocketServer | None = None

    async def start(self) -> None:  # pragma: no cover
        """
        Start the WebSocket server.

        Uses ``websockets.serve`` to start the server; runs until stopped.
        """
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not installed. Cannot start WebSocket server.")
            raise RuntimeError("websockets library not installed")

        self._running = True

        server = await serve(
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            subprotocols=[
                cast(Subprotocol, "graphql-ws"),
                cast(Subprotocol, "json"),
            ],
        )
        self._server = cast(WebSocketServer, server)

        logger.info(f"WebSocket server started on ws://{self._host}:{self._port}")

        # 运行直到停止
        await self._server.wait_closed()

    async def stop(self) -> None:  # pragma: no cover
        """Stop the WebSocket server and close all connections."""
        self._running = False

        # 关闭所有连接
        close_tasks = []
        for conn_id in list(self._connections.keys()):
            close_tasks.append(self._close_connection(conn_id, 1001, "Server shutting down"))

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("WebSocket server stopped")

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:  # pragma: no cover
        """
        处理客户端连接

        Args:
            websocket: WebSocket 连接对象
            path: 连接路径
        """
        connection_id = id(websocket)
        connection: WebSocketConnection | None = None

        try:
            # 1. 认证握手
            auth_token = self._extract_auth_token(websocket)
            if auth_token:
                try:
                    user = self._oauth2_server.validate_token(auth_token)

                    connection = WebSocketConnection(connection_id=connection_id, websocket=websocket, user=user)

                    # 注册连接
                    self._register_connection(connection)

                    logger.info(f"User {user.user_id} connected via WebSocket ({connection_id})")

                    # 发送欢迎消息
                    await self._send_message(
                        websocket,
                        WebSocketEvent(
                            type="connected",
                            data={
                                "connection_id": connection_id,
                                "user_id": user.user_id,
                                "timestamp": datetime.now().isoformat(),
                            },
                        ),
                    )

                except AuthenticationError as e:
                    logger.warning(f"WebSocket authentication failed: {e}")
                    await websocket.close(1008, f"Authentication failed: {e}")
                    return
            else:
                await websocket.close(1008, "Authentication required")
                return

            # 2. 处理消息
            async for message in websocket:
                await self._handle_message(connection, message)

        except _RuntimeConnectionClosed as e:
            close_code = getattr(e, "code", "unknown")
            logger.info(f"WebSocket connection closed naturally: {connection_id} (code={close_code})")
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
        finally:
            # 3. 清理连接
            if connection:
                self._cleanup_connection(connection_id)

    async def _handle_message(self, connection: WebSocketConnection, message: Data) -> None:
        """
        处理客户端消息

        Args:
            connection: WebSocket 连接
            message: 消息内容
        """
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")

            data = json.loads(message)
            event_type = data.get("type")

            # 更新活动时间
            connection.update_activity()

            # 处理特殊事件类型
            if event_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    self._subscribe_to_channel(connection.connection_id, channel)
                    await self._send_message(
                        connection.websocket,
                        WebSocketEvent(type="subscribed", data={"channel": channel}),
                    )
                return

            if event_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    self._unsubscribe_from_channel(connection.connection_id, channel)
                    await self._send_message(
                        connection.websocket,
                        WebSocketEvent(type="unsubscribed", data={"channel": channel}),
                    )
                return

            # 调用事件处理器
            handlers = self._event_handlers.get(event_type, [])
            for handler in handlers:
                try:
                    result = handler(connection, data)
                    if inspect.isawaitable(result):
                        await cast(Awaitable[object], result)
                except Exception as e:
                    logger.exception(f"Event handler error: {e}")

        except (UnicodeDecodeError, json.JSONDecodeError):
            await self._send_message(
                connection.websocket,
                WebSocketEvent(type="error", data={"message": "Invalid JSON", "code": "invalid_json"}),
            )

    @staticmethod
    def _get_request_headers(websocket: WebSocketServerProtocol) -> Mapping[str, str]:
        """Return handshake headers across websocket implementations."""
        legacy_headers = getattr(websocket, "request_headers", None)
        if isinstance(legacy_headers, Mapping):
            return cast(Mapping[str, str], legacy_headers)

        request = getattr(websocket, "request", None)
        headers = getattr(request, "headers", None)
        if isinstance(headers, Mapping):
            return cast(Mapping[str, str], headers)

        return {}

    def _register_connection(self, connection: WebSocketConnection) -> None:
        """注册连接"""
        self._connections[connection.connection_id] = connection

        # 注册用户连接映射
        user_id = connection.user.user_id
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(connection.connection_id)

    def _cleanup_connection(self, connection_id: int) -> None:
        """清理连接"""
        connection = self._connections.pop(connection_id, None)
        if connection:
            # 清理用户连接映射
            user_id = connection.user.user_id
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

            # 清理频道订阅
            for channel in list(connection.channels):
                self._unsubscribe_from_channel(connection_id, channel)

            logger.info(f"WebSocket connection cleaned up: {connection_id}")

    async def _close_connection(self, connection_id: int, code: int = 1000, reason: str = "") -> None:
        """关闭连接"""
        connection = self._connections.get(connection_id)
        if connection:
            try:
                await connection.websocket.close(code, reason)
            except (OSError, RuntimeError) as e:
                logger.warning(f"Error closing connection {connection_id}: {e}")

    def _extract_auth_token(self, websocket: WebSocketServerProtocol) -> str | None:
        """从握手请求提取令牌"""
        headers = self._get_request_headers(websocket)
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    async def _send_message(self, websocket: WebSocketServerProtocol, event: WebSocketEvent) -> None:
        """发送消息"""
        try:
            await websocket.send(event.to_json())
        except _RuntimeConnectionClosed:
            pass
        except (OSError, RuntimeError) as e:
            logger.warning(f"Error sending message: {e}")

    # ========== 公共 API ==========

    async def broadcast(self, event_type: str, data: JSONDict, channel: str | None = None) -> None:
        """
        广播事件给所有连接

        Args:
            event_type: 事件类型
            data: 事件数据
            channel: 频道 (可选，如果指定则只广播给该频道的订阅者)
        """
        event = WebSocketEvent(type=event_type, data=data, channel=channel)
        message = event.to_json()

        disconnected: list[int] = []

        if channel:
            # 广播给频道订阅者
            subscriber_ids = self._channel_subscribers.get(channel, set())
            targets = [(cid, self._connections[cid]) for cid in subscriber_ids if cid in self._connections]
        else:
            # 广播给所有连接
            targets = list(self._connections.items())

        for connection_id, connection in targets:
            try:
                await connection.websocket.send(message)
            except _RuntimeConnectionClosed:
                disconnected.append(connection_id)
            except (OSError, RuntimeError) as e:
                logger.warning(f"Error broadcasting to {connection_id}: {e}")

        # 清理断开的连接
        for connection_id in disconnected:
            self._cleanup_connection(connection_id)

    async def send_to_user(self, user_id: str, event_type: str, data: JSONDict) -> None:
        """
        发送事件给指定用户

        Args:
            user_id: 用户 ID
            event_type: 事件类型
            data: 事件数据
        """
        event = WebSocketEvent(type=event_type, data=data)
        message = event.to_json()

        connection_ids = self._user_connections.get(user_id, set())
        disconnected: list[int] = []

        for connection_id in connection_ids:
            connection = self._connections.get(connection_id)
            if connection:
                try:
                    await connection.websocket.send(message)
                except _RuntimeConnectionClosed:
                    disconnected.append(connection_id)
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Error sending to user {user_id} conn {connection_id}: {e}")

        # 清理断开的连接
        for connection_id in disconnected:
            self._cleanup_connection(connection_id)

    async def send_to_channel(self, channel: str, event_type: str, data: JSONDict) -> None:
        """
        发送事件给指定频道

        Args:
            channel: 频道名称
            event_type: 事件类型
            data: 事件数据
        """
        event = WebSocketEvent(type=event_type, data=data, channel=channel)
        message = event.to_json()

        subscriber_ids = self._channel_subscribers.get(channel, set())
        disconnected: list[int] = []

        for connection_id in subscriber_ids:
            connection = self._connections.get(connection_id)
            if connection:
                try:
                    await connection.websocket.send(message)
                except _RuntimeConnectionClosed:
                    disconnected.append(connection_id)
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Error sending to channel {channel} conn {connection_id}: {e}")

        # 清理断开的连接
        for connection_id in disconnected:
            self._cleanup_connection(connection_id)

    def _subscribe_to_channel(self, connection_id: int, channel: str) -> None:
        """订阅频道"""
        connection = self._connections.get(connection_id)
        if connection:
            connection.channels.add(channel)

            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()
            self._channel_subscribers[channel].add(connection_id)

            logger.info(f"Connection {connection_id} subscribed to channel {channel}")

    def _unsubscribe_from_channel(self, connection_id: int, channel: str) -> None:
        """Unsubscribe *connection_id* from *channel*.

        Works even when the connection has already been removed from
        ``_connections`` (e.g. during cleanup).
        """
        # Update connection's own channel set only if it's still registered.
        connection = self._connections.get(connection_id)
        if connection:
            connection.channels.discard(channel)

        # Always clean the subscriber index regardless.
        if channel in self._channel_subscribers:
            self._channel_subscribers[channel].discard(connection_id)
            if not self._channel_subscribers[channel]:
                del self._channel_subscribers[channel]

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """
        注册事件处理器

        Args:
            event_type: 事件类型
            handler: 处理函数 (async 或 sync)
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)

    def get_user_connections(self, user_id: str) -> int:
        """获取用户的连接数"""
        return len(self._user_connections.get(user_id, set()))

    def get_channel_subscribers(self, channel: str) -> int:
        """获取频道订阅者数量"""
        return len(self._channel_subscribers.get(channel, set()))

    def get_stats(self) -> dict[str, int | bool]:
        """获取服务器统计信息"""
        return {
            "total_connections": len(self._connections),
            "unique_users": len(self._user_connections),
            "total_channels": len(self._channel_subscribers),
            "running": self._running,
        }


# 全局单例 (可选)
_global_ws_server: WSServer | None = None


def get_ws_server(oauth2_server: OAuth2Server | None = None) -> WSServer:
    """获取全局 WebSocket 服务器实例"""
    global _global_ws_server
    if _global_ws_server is None:
        from .oauth2_server import get_oauth2_server

        _global_ws_server = WSServer(oauth2_server=oauth2_server or get_oauth2_server())
    return _global_ws_server
