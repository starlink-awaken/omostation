from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: L3
Summary: Integration hub for GitHub webhooks, Slack bots and other third-party service adapters.
Owner: bos-core
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Integrations ≡ Module
# 内涵 ≝ {Integrations}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, Integrations)}
# 功能 ⊢ {Init_Integrations, Execute_Integrations, Validate_Integrations}
# =============================================================================
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from collections.abc import Callable  # noqa: E402
from typing import Any  # noqa: E402

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

# =============================================================================
# D-Gateway External Service Integrations
# =============================================================================
# GitHub Webhook and Slack Bot integrations
# =============================================================================

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

HANDLER_DISPATCH_EXCEPTIONS = (KeyError, TypeError, ValueError)
SLACK_API_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    TypeError,
    ValueError,
    json.JSONDecodeError,
)
if AIOHTTP_AVAILABLE:
    SLACK_API_EXCEPTIONS = (aiohttp.ClientError, *SLACK_API_EXCEPTIONS)

# =============================================================================
# GitHub Webhook Handler
# =============================================================================


class GitHubWebhookHandler:
    """
    GitHub Webhook 处理器

    支持的 Webhook 事件:
    - push: 代码推送
    - pull_request: PR 事件
    - issues: Issue 事件
    - issue_comment: Issue 评论
    - workflow_run: GitHub Actions 工作流运行

    特性:
    - HMAC 签名验证
    - 事件路由
    - 命令解析 (@sharedbrain)
    """

    def __init__(self, secret: str) -> None:
        """
        初始化 GitHub Webhook 处理器

        Args:
            secret: GitHub Webhook 密钥
        """
        self.status = "active"
        self._secret = secret.encode()
        self._event_handlers: dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认事件处理器"""
        self._event_handlers = {
            "push": self._handle_push,
            "pull_request": self._handle_pull_request,
            "issues": self._handle_issues,
            "issue_comment": self._handle_issue_comment,
            "workflow_run": self._handle_workflow_run,
        }

    def verify_signature(self, payload: bytes, signature: str, event_type: str) -> bool:
        """
        验证 GitHub 签名

        Args:
            payload: 请求体
            signature: GitHub 签名 (sha256=xxx)
            event_type: 事件类型

        Returns:
            验证是否通过
        """
        if not signature or not signature.startswith("sha256="):
            return False

        # 构建签名字符串
        sig_basestring = f"{event_type}.{payload.decode()}"
        expected_signature = (
            "sha256="
            + hmac.new(
                self._secret, sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        return hmac.compare_digest(signature, expected_signature)

    async def handle_webhook(
        self,
        event_type: str,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        """
        处理 Webhook

        Args:
            event_type: 事件类型 (X-GitHub-Event)
            payload: 事件数据
            signature: GitHub 签名 (X-Hub-Signature-256)
            raw_body: 原始请求体 (用于签名验证)

        Returns:
            处理结果
        """
        # 验证签名 (如果提供)
        if signature and raw_body:
            if not self.verify_signature(raw_body, signature, event_type):
                logger.warning("GitHub webhook signature verification failed")
                return {
                    "status": "rejected",
                    "reason": "Invalid signature",
                    "code": "signature_mismatch",
                }

        # 路由到事件处理器
        handler = self._event_handlers.get(event_type)
        if handler:
            try:
                result = await handler(payload)
                return {"status": "processed", "event": event_type, "result": result}
            except HANDLER_DISPATCH_EXCEPTIONS as e:
                logger.exception(f"Error handling GitHub webhook {event_type}: {e}")
                return {"status": "error", "event": event_type, "error": str(e)}

        # 未知事件类型
        return {
            "status": "ignored",
            "reason": f"Unknown event type: {event_type}",
            "code": "unknown_event",
        }

    def register_handler(self, event_type: str, handler: Callable[..., object]) -> None:
        """
        注册事件处理器

        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        self._event_handlers[event_type] = handler

    async def _handle_push(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 Push 事件"""
        repo = payload.get("repository", {}).get("full_name", "unknown")
        branch = payload.get("ref", "").replace("refs/heads/", "")
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "unknown")

        return {
            "event": "push",
            "repo": repo,
            "branch": branch,
            "commits_count": len(commits),
            "pusher": pusher,
            "commit_shas": [
                c.get("id", "")[:7] for c in commits[:5]
            ],  # 最近 5 个 commit
        }

    async def _handle_pull_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 Pull Request 事件"""
        action = payload.get("action", "unknown")
        pr_number = payload.get("number")
        repo = payload.get("repository", {}).get("full_name", "unknown")
        pr_title = payload.get("pull_request", {}).get("title", "")
        author = payload.get("pull_request", {}).get("user", {}).get("login", "unknown")

        return {
            "event": "pull_request",
            "action": action,
            "repo": repo,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "author": author,
        }

    async def _handle_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 Issues 事件"""
        action = payload.get("action", "unknown")
        issue_number = payload.get("issue", {}).get("number")
        issue_title = payload.get("issue", {}).get("title", "")
        author = payload.get("issue", {}).get("user", {}).get("login", "unknown")
        repo = payload.get("repository", {}).get("full_name", "unknown")

        return {
            "event": "issues",
            "action": action,
            "repo": repo,
            "issue_number": issue_number,
            "issue_title": issue_title,
            "author": author,
        }

    async def _handle_issue_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 Issue 评论事件"""
        action = payload.get("action")
        comment = payload.get("comment", {}).get("body", "")
        author = payload.get("comment", {}).get("user", {}).get("login", "unknown")
        issue_number = payload.get("issue", {}).get("number")
        repo = payload.get("repository", {}).get("full_name", "unknown")

        # 检查是否是 @sharedbrain 命令
        if comment.startswith("@sharedbrain"):
            return await self._handle_command(
                comment, {"repo": repo, "issue_number": issue_number, "author": author}
            )

        return {
            "event": "issue_comment",
            "action": action,
            "repo": repo,
            "issue_number": issue_number,
            "comment_author": author,
        }

    async def _handle_workflow_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 GitHub Actions 工作流运行事件"""
        action = payload.get("action", "unknown")
        workflow = payload.get("workflow", {}).get("name", "unknown")
        run_number = payload.get("workflow_run", {}).get("run_number")
        status = payload.get("workflow_run", {}).get("status")
        conclusion = payload.get("workflow_run", {}).get("conclusion")
        repo = payload.get("repository", {}).get("full_name", "unknown")

        return {
            "event": "workflow_run",
            "action": action,
            "repo": repo,
            "workflow": workflow,
            "run_number": run_number,
            "status": status,
            "conclusion": conclusion,
        }

    async def _handle_command(
        self, command: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        处理 SharedBrain 命令

        Args:
            command: 命令文本 (包含 @sharedbrain)
            context: 上下文信息

        Returns:
            命令处理结果
        """
        parts = command.split()
        cmd_parts = parts[0].replace("@sharedbrain/", "").split()
        cmd = cmd_parts[0] if cmd_parts else "help"
        args = parts[1:]

        # 内置命令处理
        commands = {
            "help": lambda ctx, a: {
                "command": "help",
                "message": self._get_help_message(),
            },
            "status": lambda ctx, a: {"command": "status", "repo": ctx.get("repo")},
            "info": lambda ctx, a: {"command": "info", "context": ctx},
        }

        handler = commands.get(cmd)
        if handler:
            result = (
                await handler(context, args)
                if asyncio.iscoroutinefunction(handler)
                else handler(context, args)
            )
            return {"status": "command_processed", **result}

        return {
            "status": "command_unknown",
            "command": cmd,
            "message": f"Unknown command: {cmd}",
        }

    def _get_help_message(self) -> str:
        """获取帮助消息"""
        return """SharedBrain GitHub Bot Commands:
- @sharedbrain/help - Show this help message
- @sharedbrain/status - Check system status
- @sharedbrain/info - Show context information
"""


# =============================================================================
# Slack Bot Handler
# =============================================================================


class SlackBotHandler:
    """
    Slack Bot 处理器

    功能:
    1. 接收 Slack 事件
    2. 处理 Slash 命令
    3. 发送消息到 Slack
    4. 交互式组件处理

    支持的事件:
    - url_verification: Slack URL 验证
    - message: 消息事件
    - slash_command: Slash 命令
    - block_actions: 交互组件动作
    """

    def __init__(self, bot_token: str, signing_secret: str) -> None:
        """
        初始化 Slack Bot 处理器

        Args:
            bot_token: Slack Bot Token (xoxb-...)
            signing_secret: Slack 签名密钥
        """
        self.status = "active"
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._base_url = "https://slack.com/api"
        self._event_handlers: dict[str, Callable] = {}
        self._slash_commands: dict[str, Callable] = {}

        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not installed. Slack API calls disabled.")

    def verify_signature(self, timestamp: str, signature: str, body: bytes) -> bool:
        """
        验证 Slack 签名

        Args:
            timestamp: 请求时间戳 (X-Slack-Request-Timestamp)
            signature: Slack 签名 (X-Slack-Signature)
            body: 原始请求体

        Returns:
            验证是否通过
        """
        # 验证时间戳 (5 分钟窗口)
        current_time = int(time.time())
        try:
            request_time = int(timestamp)
            if abs(current_time - request_time) > 300:
                logger.warning("Slack request timestamp out of window")
                return False
        except (ValueError, TypeError):
            return False

        # 验证签名
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected_signature = (
            "v0="
            + hmac.new(
                self._signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        return hmac.compare_digest(signature, expected_signature)

    async def handle_event(
        self, event: dict[str, Any], raw_body: bytes | None = None
    ) -> dict[str, Any]:
        """
        处理 Slack 事件

        Args:
            event: 事件数据
            raw_body: 原始请求体 (用于签名验证)

        Returns:
            处理结果
        """
        event_type: str | None = event.get("type")
        if not event_type:
            return {"status": "ignored", "reason": "Missing event type"}

        # URL 验证 (挑战响应)
        if event_type == "url_verification":
            return {"challenge": event.get("challenge")}

        # 路由到事件处理器
        handler = self._event_handlers.get(event_type)
        if handler:
            try:
                result = await handler(event)
                return {"status": "processed", "event": event_type, "result": result}
            except HANDLER_DISPATCH_EXCEPTIONS as e:
                logger.exception(f"Error handling Slack event {event_type}: {e}")
                return {"status": "error", "event": event_type, "error": str(e)}

        # 默认忽略未知事件
        return {"status": "ignored", "event_type": event_type}

    async def handle_interactive(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        处理交互式组件 (按钮点击等)

        Args:
            payload: 回调 payload

        Returns:
            处理结果
        """
        action_type = payload.get("type")

        if action_type == "block_actions":
            return await self._handle_block_actions(payload)
        elif action_type == "view_submission":
            return await self._handle_view_submission(payload)
        else:
            return {"status": "ignored", "action_type": action_type}

    async def _handle_block_actions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理按钮点击等交互动作"""
        actions = payload.get("actions", [])
        user = payload.get("user", {})
        channel = payload.get("channel", {})

        results = []
        for action in actions:
            action_id = action.get("action_id")
            action_value = action.get("value") or action.get("selected_option", {}).get(
                "value"
            )

            results.append(
                {
                    "action_id": action_id,
                    "action_value": action_value,
                    "user": user.get("username"),
                    "channel": channel.get("id") if channel else None,
                }
            )

        return {"status": "processed", "type": "block_actions", "actions": results}

    async def _handle_view_submission(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理视图提交"""
        view = payload.get("view", {})
        state_values = view.get("state", {}).get("values", {})
        user = payload.get("user", {})

        return {
            "status": "processed",
            "type": "view_submission",
            "user": user.get("username"),
            "state_values": state_values,
        }

    def register_event_handler(
        self, event_type: str, handler: Callable[..., object]
    ) -> None:
        """注册事件处理器"""
        self._event_handlers[event_type] = handler

    def register_slash_command(
        self, command: str, handler: Callable[..., object]
    ) -> None:
        """
        注册 Slash 命令处理器

        Args:
            command: 命令名称 (不带 /)
            handler: 处理函数
        """
        self._slash_commands[command] = handler

    async def _send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """
        发送消息到 Slack

        Args:
            channel: 频道 ID 或名称
            text: 消息文本
            blocks: 消息块 (可选)
            thread_ts: 线程时间戳 (用于回复线程)

        Returns:
            API 响应
        """
        if not AIOHTTP_AVAILABLE:
            return {"status": "error", "error": "aiohttp not installed"}

        payload: dict[str, Any] = {"channel": channel, "text": text}

        if blocks:
            payload["blocks"] = blocks

        if thread_ts:
            payload["thread_ts"] = thread_ts

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._bot_token}"},
                    json=payload,
                ) as response:
                    result = await response.json()
                    return result
        except SLACK_API_EXCEPTIONS as e:
            logger.exception(f"Error sending Slack message: {e}")
            return {"status": "error", "error": str(e)}

    async def send_ephemeral(
        self,
        channel: str,
        user: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        发送临时消息 (仅用户可见)

        Args:
            channel: 频道 ID 或名称
            user: 用户 ID
            text: 消息文本
            blocks: 消息块 (可选)

        Returns:
            API 响应
        """
        if not AIOHTTP_AVAILABLE:
            return {"status": "error", "error": "aiohttp not installed"}

        payload: dict[str, Any] = {"channel": channel, "user": user, "text": text}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/chat.postEphemeral",
                    headers={"Authorization": f"Bearer {self._bot_token}"},
                    json=payload,
                ) as response:
                    result = await response.json()
                    return result
        except SLACK_API_EXCEPTIONS as e:
            logger.exception(f"Error sending Slack ephemeral message: {e}")
            return {"status": "error", "error": str(e)}


# =============================================================================
# Integration Hub (统一集成中心)
# =============================================================================


class IntegrationHub:
    """
    外部服务集成中心

    统一管理所有外部服务集成:
    - GitHub Webhooks
    - Slack Bot
    - 其他未来集成
    """

    def __init__(self) -> None:
        """初始化集成中心"""
        self.status = "active"
        self._integrations: dict[str, Any] = {}

    def register_integration(self, name: str, handler: Any) -> None:
        """
        注册集成处理器

        Args:
            name: 集成名称
            handler: 处理器实例
        """
        self._integrations[name] = handler
        logger.info(f"Registered integration: {name}")

    def get_integration(self, name: str) -> Any | None:
        """获取集成处理器"""
        return self._integrations.get(name)

    def list_integrations(self) -> list[str]:
        """列出所有已注册的集成"""
        return list(self._integrations.keys())

    async def process_event(
        self, source: str, event_type: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """
        处理外部事件

        Args:
            source: 事件来源 (github, slack, etc.)
            event_type: 事件类型
            payload: 事件数据
            **kwargs: 额外参数

        Returns:
            处理结果
        """
        handler = self.get_integration(source)
        if not handler:
            return {
                "status": "unknown_source",
                "source": source,
                "error": f"Integration not found: {source}",
            }

        if hasattr(handler, "handle_webhook"):
            return await handler.handle_webhook(event_type, payload, **kwargs)
        elif hasattr(handler, "handle_event"):
            return await handler.handle_event(payload, **kwargs)
        else:
            return {
                "status": "error",
                "error": f"Handler {source} has no handle method",
            }


# 全局单例
_global_integration_hub: IntegrationHub | None = None


def get_integration_hub() -> IntegrationHub:
    """获取全局集成中心实例"""
    global _global_integration_hub
    if _global_integration_hub is None:
        _global_integration_hub = IntegrationHub()
    return _global_integration_hub


# ========== async 导入支持 ==========
try:
    import asyncio
except ImportError:  # pragma: no cover
    import types as _types

    class _FakeAsyncioModule(_types.ModuleType):  # type: ignore[misc]
        """Fallback when asyncio is unavailable."""

        @staticmethod
        def iscoroutinefunction(func: object) -> bool:
            return False

    asyncio = _FakeAsyncioModule("asyncio")
