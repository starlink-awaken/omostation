"""Hermes webhook service — receive and execute tasks from phone/IM.

Adapted from agentmesh gateway hermes/routes.ts.
Manages task lifecycle: receive, queue, execute, and return results.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

logger = logging.getLogger(__name__)

MAX_TASKS = 200


class HermesTask:
    """Represents a Hermes webhook task."""

    def __init__(
        self,
        task_id: str,
        prompt: str,
        model: str = "deepseek-chat",
    ) -> None:
        self.id = task_id
        self.prompt = prompt
        self.model = model
        self.status: str = "pending"
        self.result: str | None = None
        self.error: str | None = None
        self.created_at = int(time.time() * 1000)

    def to_dict(self) -> dict:
        return {
            "task_id": self.id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
        }


_tasks: dict[str, HermesTask] = {}


def get_hermes_tasks() -> list[HermesTask]:
    """Get all Hermes tasks, newest first."""
    return sorted(_tasks.values(), key=lambda t: t.created_at, reverse=True)


def _prune_old_tasks() -> None:
    if len(_tasks) <= MAX_TASKS:
        return
    sorted_tasks = sorted(_tasks.items(), key=lambda x: x[1].created_at)
    for task_id, _ in sorted_tasks[: len(_tasks) - MAX_TASKS]:
        _tasks.pop(task_id, None)


async def submit_hermes_task(
    prompt: str,
    task_id: str | None = None,
    model: str = "deepseek-chat",
) -> HermesTask:
    """Submit a new Hermes task for execution."""
    tid = task_id or str(uuid.uuid4())
    task = HermesTask(tid, prompt, model)
    _tasks[tid] = task
    _prune_old_tasks()

    logger.info("[Hermes] Task received: %s (prompt: %.100s)", tid, prompt)

    # Execute asynchronously
    asyncio.create_task(_execute_hermes_task(task))

    return task


def get_hermes_task(task_id: str) -> HermesTask | None:
    """Get a specific Hermes task by ID."""
    return _tasks.get(task_id)


def get_hermes_health() -> dict:
    """Get Hermes health status."""
    running = sum(1 for t in _tasks.values() if t.status in ("pending", "running"))
    completed = sum(1 for t in _tasks.values() if t.status == "completed")
    return {
        "status": "ok",
        "active_tasks": running,
        "completed_tasks": completed,
        "timestamp": int(time.time() * 1000),
    }


async def _execute_hermes_task(task: HermesTask) -> None:
    """Execute a Hermes task by calling the model provider."""
    from agora.agent_providers import (  # type: ignore[import-not-found]
        call_chat_completions,
        remap_model,
        resolve_provider,
    )

    task.status = "running"
    start = time.time()

    try:
        provider = resolve_provider(task.model)
        if not provider:
            raise RuntimeError("No available provider")

        model = remap_model(task.model, provider.name)
        resp = await call_chat_completions(
            provider,
            {
                "model": model,
                "messages": [{"role": "user", "content": task.prompt}],
                "max_tokens": 4000,
            },
        )

        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        task.result = content or "(empty response)"
        task.status = "completed"

        logger.info(
            "[Hermes] Task %s completed in %.0fms",
            task.id,
            (time.time() - start) * 1000,
        )
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        logger.error("[Hermes] Task %s failed: %s", task.id, e)
