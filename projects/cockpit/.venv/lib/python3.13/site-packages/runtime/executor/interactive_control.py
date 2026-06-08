"""Interactive control with user-in-the-loop — pause, resume, checkpoint, rollback.

Migrated from agentmesh interactive-control.ts.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CommandType(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    CHECKPOINT = "checkpoint"
    ROLLBACK = "rollback"
    SET_PRIORITY = "set-priority"
    STATUS = "status"


class CommandStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class PriorityLevel(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ControlCommand:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    type: CommandType = CommandType.STATUS
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    status: CommandStatus = CommandStatus.PENDING
    result: Any = None
    error: str | None = None


@dataclass
class InteractiveStatus:
    project_id: str | None = None
    project_name: str | None = None
    current_phase: str | None = None
    is_paused: bool = False
    pause_reason: str | None = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    uptime_ms: float = 0.0
    command_history_count: int = 0
    pending_commands: int = 0
    last_checkpoint_at: float | None = None


class ControlDelegate:
    """Abstract delegate for orchestrator operations.

    Implement this to bridge InteractiveController with your orchestrator.
    """

    def pause_project(self, reason: str) -> None: ...
    def resume_project(self) -> None: ...
    def checkpoint(self, description: str | None = None) -> None: ...
    def rollback(self, checkpoint_id: str) -> None: ...
    def get_status(self) -> InteractiveStatus: ...  # type: ignore[empty-body]


class InteractiveController:
    """Provide real-time interactive control over running projects.

    Wraps a ControlDelegate to add pause/resume with reason tracking,
    priority management, manual checkpoints, and command queuing.
    """

    def __init__(self, delegate: ControlDelegate) -> None:
        self._delegate = delegate
        self._created_at = time.monotonic()
        self._paused = False
        self._pause_reason: str | None = None
        self._priority = PriorityLevel.NORMAL
        self._last_checkpoint_at: float | None = None
        self._command_history: list[ControlCommand] = []
        self._command_queue: list[ControlCommand] = []

    # -- Pause / Resume ---------------------------------------------------

    def pause(self, reason: str) -> ControlCommand:
        cmd = self._build_cmd(CommandType.PAUSE, {"reason": reason})
        if self._paused:
            return self._fail_cmd(cmd, "Project is already paused")
        try:
            self._delegate.pause_project(reason)
            self._paused = True
            self._pause_reason = reason
            return self._complete_cmd(cmd)
        except Exception as exc:
            return self._fail_cmd(cmd, str(exc))

    def resume(self) -> ControlCommand:
        cmd = self._build_cmd(CommandType.RESUME)
        if not self._paused:
            return self._fail_cmd(cmd, "Project is not paused")
        try:
            self._delegate.resume_project()
            self._paused = False
            self._pause_reason = None
            return self._complete_cmd(cmd)
        except Exception as exc:
            return self._fail_cmd(cmd, str(exc))

    def is_paused(self) -> bool:
        return self._paused

    # -- Priority ---------------------------------------------------------

    def set_priority(self, level: PriorityLevel) -> None:
        self._priority = level

    def get_priority(self) -> PriorityLevel:
        return self._priority

    # -- Checkpoint / Rollback -------------------------------------------

    def create_checkpoint(self, description: str | None = None) -> ControlCommand:
        cmd = self._build_cmd(CommandType.CHECKPOINT, {"description": description})
        try:
            self._delegate.checkpoint(description)
            self._last_checkpoint_at = time.time()
            return self._complete_cmd(cmd)
        except Exception as exc:
            return self._fail_cmd(cmd, str(exc))

    def rollback_to(self, checkpoint_id: str) -> ControlCommand:
        cmd = self._build_cmd(CommandType.ROLLBACK, {"checkpoint_id": checkpoint_id})
        try:
            self._delegate.rollback(checkpoint_id)
            return self._complete_cmd(cmd)
        except Exception as exc:
            return self._fail_cmd(cmd, str(exc))

    # -- Status -----------------------------------------------------------

    def get_status(self) -> InteractiveStatus:
        status = self._delegate.get_status()
        status.is_paused = self._paused
        status.pause_reason = self._pause_reason
        status.priority = self._priority
        status.uptime_ms = (time.monotonic() - self._created_at) * 1000
        status.command_history_count = len(self._command_history)
        status.pending_commands = len(self._command_queue)
        status.last_checkpoint_at = self._last_checkpoint_at
        return status

    def uptime(self) -> float:
        return (time.monotonic() - self._created_at) * 1000

    # -- Command History --------------------------------------------------

    def get_command_history(self, limit: int | None = None) -> list[ControlCommand]:
        if limit is None:
            return list(self._command_history)
        return list(reversed(self._command_history))[:limit]

    # -- Command Queue ----------------------------------------------------

    def queue_command(self, cmd_type: CommandType, payload: dict | None = None) -> ControlCommand:
        cmd = ControlCommand(
            type=cmd_type,
            payload=payload or {},
            status=CommandStatus.PENDING,
        )
        self._command_queue.append(cmd)
        return cmd

    async def execute_queue(self) -> list[ControlCommand]:
        pending = list(self._command_queue)
        self._command_queue.clear()
        results: list[ControlCommand] = []
        for cmd in pending:
            cmd.status = CommandStatus.EXECUTING
            results.append(self._dispatch(cmd))
        return results

    # -- Internal ---------------------------------------------------------

    def _build_cmd(self, cmd_type: CommandType, payload: dict | None = None) -> ControlCommand:
        cmd = ControlCommand(
            type=cmd_type,
            payload=payload or {},
            status=CommandStatus.EXECUTING,
        )
        self._command_history.append(cmd)
        return cmd

    @staticmethod
    def _complete_cmd(cmd: ControlCommand, result: Any = None) -> ControlCommand:
        cmd.status = CommandStatus.COMPLETED
        cmd.result = result
        return cmd

    @staticmethod
    def _fail_cmd(cmd: ControlCommand, error: str) -> ControlCommand:
        cmd.status = CommandStatus.FAILED
        cmd.error = error
        return cmd

    def _dispatch(self, cmd: ControlCommand) -> ControlCommand:
        self._command_history.append(cmd)
        payload = cmd.payload or {}
        try:
            if cmd.type == CommandType.PAUSE:
                reason = payload.get("reason", "Queued pause")
                if self._paused:
                    return self._fail_cmd(cmd, "Project is already paused")
                self._delegate.pause_project(reason)
                self._paused = True
                self._pause_reason = reason
                return self._complete_cmd(cmd)
            elif cmd.type == CommandType.RESUME:
                if not self._paused:
                    return self._fail_cmd(cmd, "Project is not paused")
                self._delegate.resume_project()
                self._paused = False
                self._pause_reason = None
                return self._complete_cmd(cmd)
            elif cmd.type == CommandType.CHECKPOINT:
                self._delegate.checkpoint(payload.get("description"))
                self._last_checkpoint_at = time.time()
                return self._complete_cmd(cmd)
            elif cmd.type == CommandType.ROLLBACK:
                self._delegate.rollback(payload.get("checkpoint_id", ""))
                return self._complete_cmd(cmd)
            elif cmd.type == CommandType.SET_PRIORITY:
                level = PriorityLevel(payload.get("level", "normal"))
                self._priority = level
                return self._complete_cmd(cmd, {"priority": level.value})
            elif cmd.type == CommandType.STATUS:
                return self._complete_cmd(cmd, self.get_status())
            else:
                return self._fail_cmd(cmd, f"Unknown command type: {cmd.type}")
        except Exception as exc:
            return self._fail_cmd(cmd, str(exc))
