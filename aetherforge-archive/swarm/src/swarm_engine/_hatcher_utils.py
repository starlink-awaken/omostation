"""Pure utility functions extracted from hatcher_core.py (ARCH-003 SRP refactor).

Provides command building, env filtering, and handle registration helpers
that don't depend on instance state.
"""

from __future__ import annotations

import os
import shlex
import threading
from typing import Any

from ._compat import WorkerHandle


def build_command(template: str, task_prompt: str) -> list[str]:
    """Parse cli_command_template and inject task_prompt safely."""
    _SENTINEL = "___TASK_PROMPT_SENTINEL___"  # noqa: N806
    normalised = (
        template.replace("'{TASK_PROMPT}'", _SENTINEL)
        .replace('"{TASK_PROMPT}"', _SENTINEL)
        .replace("{TASK_PROMPT}", _SENTINEL)
    )
    base_parts = shlex.split(normalised)
    return [task_prompt if part == _SENTINEL else part for part in base_parts]


def build_env(env_whitelist: list[str]) -> dict[str, str]:
    """Build a minimal environment dict containing only whitelisted keys."""
    filtered: dict[str, str] = {}
    for key in env_whitelist:
        value = os.environ.get(key)
        if value is not None:
            filtered[key] = value
    if "PATH" not in filtered and "PATH" in os.environ:
        filtered["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    return filtered


def register_handle(handles: dict[str, WorkerHandle], lock: Any, handle: WorkerHandle) -> WorkerHandle:
    """Track a live worker handle under the shared handle registry."""
    with lock:
        handles[handle.worker_id] = handle
    return handle


def register_internal_thread_runtime(
    handles: dict[str, WorkerHandle],
    threads: dict[str, threading.Thread],
    cancel_events: dict[str, threading.Event],
    lock: Any,
    handle: WorkerHandle,
    thread: threading.Thread,
    cancel_event: threading.Event,
) -> WorkerHandle:
    """Track the handle plus thread-specific runtime state."""
    with lock:
        handles[handle.worker_id] = handle
        threads[handle.worker_id] = thread
        cancel_events[handle.worker_id] = cancel_event
    return handle
