"""Agent adapter types and base implementations.

Provides the abstract agent interface and concrete adapters for Claude Code,
OpenClaw, and generic process-based agents.
Adapted from agentmesh gateway adapters/*.ts.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class AgentMessage:
    """Minimal agent message for adapter invocation."""

    def __init__(
        self,
        id: str = "",
        type: str = "request",
        source: str = "",
        target: str = "",
        correlation_id: str = "",
        timestamp: int = 0,
        payload: dict[str, Any] | None = None,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.type = type
        self.source = source
        self.target = target
        self.correlation_id = correlation_id
        self.timestamp = timestamp
        self.payload = payload or {}
        self.result = result
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items() if v is not None
        }


class AgentAdapter(ABC):
    """Abstract base for an agent adapter."""

    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def type(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]: ...

    @abstractmethod
    async def invoke(self, request: AgentMessage) -> AgentMessage: ...

    async def invoke_stream(
        self, request: AgentMessage
    ) -> AsyncGenerator[AgentMessage]:
        """Default stream: yield the single response."""
        yield await self.invoke(request)

    @abstractmethod
    async def health(self) -> bool: ...


import uuid
from collections.abc import AsyncGenerator


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Anthropic Claude Code CLI."""

    def __init__(self, cli_path: str = "claude") -> None:
        self._cli_path = cli_path

    @property
    def id(self) -> str:
        return "claude-code"

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def type(self) -> str:
        return "claude-code"

    @property
    def capabilities(self) -> list[str]:
        return [
            "code-generation", "code-review", "debugging",
            "refactoring", "documentation", "file-operations",
        ]

    async def invoke(self, request: AgentMessage) -> AgentMessage:
        task = str(request.payload.get("task", ""))
        corr = request.correlation_id or str(uuid.uuid4())
        timeout = request.payload.get("options", {}).get("timeout", 300)

        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path, "-p",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(task.encode()), timeout=timeout
            )
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                result=stdout.decode(),
            )
        except (TimeoutError, FileNotFoundError, Exception) as e:
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                error={"code": "EXECUTION_ERROR", "message": str(e)},
            )

    async def health(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False


class OpenClawAdapter(AgentAdapter):
    """Adapter for OpenClaw browser automation CLI."""

    def __init__(self, cli_path: str = "openclaw") -> None:
        self._cli_path = cli_path

    @property
    def id(self) -> str:
        return "openclaw"

    @property
    def name(self) -> str:
        return "OpenClaw"

    @property
    def type(self) -> str:
        return "openclaw"

    @property
    def capabilities(self) -> list[str]:
        return ["browser-automation", "web-scraping", "form-filling", "ui-testing"]

    async def invoke(self, request: AgentMessage) -> AgentMessage:
        task = str(request.payload.get("task", ""))
        corr = request.correlation_id or str(uuid.uuid4())
        timeout = request.payload.get("options", {}).get("timeout", 300)

        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path, "--task", task,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                result=stdout.decode(),
            )
        except Exception as e:
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                error={"code": "EXECUTION_ERROR", "message": str(e)},
            )

    async def health(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path, "--version",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False


class ProcessAdapter(AgentAdapter):
    """Adapter for generic process-based agents."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: list[str],
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._id = agent_id
        self._name = name
        self._capabilities = capabilities
        self._command = command
        self._args = args or []
        self._env = env

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return "process"

    @property
    def capabilities(self) -> list[str]:
        return self._capabilities

    async def invoke(self, request: AgentMessage) -> AgentMessage:
        task = str(request.payload.get("task", ""))
        corr = request.correlation_id or str(uuid.uuid4())
        timeout = request.payload.get("options", {}).get("timeout", 300)

        try:
            proc = await asyncio.create_subprocess_exec(
                self._command, *self._args, task,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**__import__("os").environ, **(self._env or {})},
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                result=stdout.decode(),
            )
        except Exception as e:
            return AgentMessage(
                id=str(uuid.uuid4()),
                type="response",
                source=self.id,
                target=request.source,
                correlation_id=corr,
                timestamp=int(__import__("time").time() * 1000),
                error={"code": "EXECUTION_ERROR", "message": str(e)},
            )

    async def health(self) -> bool:
        for flag in ("--version", "-v"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._command, flag,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.wait(), timeout=5)
                if proc.returncode == 0:
                    return True
            except Exception:
                pass  # version check failed, try next flag
        return False
