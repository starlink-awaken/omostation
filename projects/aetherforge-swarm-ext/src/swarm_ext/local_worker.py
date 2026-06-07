from __future__ import annotations

# ruff: noqa: RUF002

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Local Worker ≡ Worker
# 内涵 ≝ {Local, Worker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LocalWorker)}
# 功能 ⊢ {Local_Worker, Init_Local, Validate_Worker}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import asyncio
import contextlib
import json
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict

_log = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PYTHON_SANDBOX_RUNNER = """from __future__ import annotations
import json
import sys

from .organs.security_utils import safe_exec_sandbox
from typing import Any


def _json_safe(value):
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


payload = json.loads(sys.stdin.read())
exec_result = safe_exec_sandbox(payload["code"], capture_stdout=True)
response = {
    "success": exec_result["success"],
    "output": exec_result["output"],
    "result": _json_safe(exec_result["result"]),
    "error": exec_result["error"],
}
sys.stdout.write(json.dumps(response))
"""

TaskPayload = dict[str, object]
TaskResult = dict[str, object]
TaskIntent = object


class _SandboxResponse(TypedDict):
    success: bool
    output: Any
    result: Any
    error: Any


class TaskRecordProtocol(Protocol):
    task_id: str
    intent: str


class TaskStoreProtocol(Protocol):
    def get_retryable_tasks(self) -> list[TaskRecordProtocol]: ...

    def transition(self, task_id: str, new_state: Any, **kwargs: Any) -> None: ...

    def claim_next_priority(self, worker_id: str) -> TaskRecordProtocol | None: ...

    async def wait_for_task(self, timeout: float = 5.0) -> bool: ...

    def schedule_retry(self, task_id: str) -> bool: ...


@dataclass
class LocalWorkerConfig:
    """Configuration for the local task worker."""

    poll_interval: float = 2.0
    max_concurrent: int = 4
    task_timeout: float = 120.0
    db_path: str = ""


class LocalWorker:
    """Lightweight local worker that polls TaskStore and executes tasks.

    Supports three task types dispatched via the ``type`` key inside
    the JSON-encoded ``intent`` field of a :class:`TaskRecord`:

    * ``shell``  – run a subprocess command
    * ``python`` – execute a Python snippet
    * ``echo``   – return the input verbatim (useful for testing)
    """

    def __init__(self, config: LocalWorkerConfig | None = None) -> None:
        self._config = config or LocalWorkerConfig()
        self._running = False
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        self._tasks: set[asyncio.Task[None]] = set()
        self._store: TaskStoreProtocol | None = None
        self._poll_task: asyncio.Task[None] | None = None

    # -- store access (lazy) ------------------------------------------------

    def _get_store(self) -> TaskStoreProtocol:
        if self._store is None:
            from .organs.engine.task_store import TaskStore  # type: ignore[import-not-found]

            db = self._config.db_path or ":memory:"
            self._store = TaskStore(db_path=db)
        return self._store

    @property
    def store(self) -> TaskStoreProtocol:
        return self._get_store()

    @store.setter
    def store(self, value: TaskStoreProtocol) -> None:
        self._store = value

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the worker polling loop."""
        self._running = True
        _log.info(
            "LocalWorker starting (poll=%.1fs, concurrency=%d)",
            self._config.poll_interval,
            self._config.max_concurrent,
        )
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        _log.info("LocalWorker stopped")

    # -- polling -------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._poll_and_execute()
            except (OSError, KeyError, ValueError):
                _log.exception("Error in poll cycle")
            await self._get_store().wait_for_task(timeout=self._config.poll_interval)

    async def _poll_and_execute(self) -> None:
        """Poll for pending and retryable tasks by priority and execute them."""
        from .organs.engine.task_store import TaskState

        store = self._get_store()

        available = self._config.max_concurrent - len(self._tasks)
        if available <= 0:
            return

        # First pick up retryable tasks whose next_retry_at has passed
        retryable = store.get_retryable_tasks()
        worker_id = f"local-{id(self)}"
        for record in retryable[:available]:
            store.transition(record.task_id, TaskState.running, worker_id=worker_id)
            intent, payload = self._parse_intent(record.intent)
            task = asyncio.create_task(
                self._run_task(record.task_id, intent, payload),
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        available = self._config.max_concurrent - len(self._tasks)
        for _ in range(available):
            record: TaskRecordProtocol | None = store.claim_next_priority(worker_id)
            if record is None:
                break
            intent, payload = self._parse_intent(record.intent)
            task = asyncio.create_task(
                self._run_task(record.task_id, intent, payload),
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    # -- intent parsing ------------------------------------------------------

    @staticmethod
    def _parse_intent(raw: str) -> tuple[TaskIntent, TaskPayload]:
        """Parse a JSON intent string into *(type, payload)*.

        Expected format: ``{"type": "shell", "command": "..."}``
        Falls back to treating the raw string as an ``echo`` task with
        the full intent as the message, so legacy plain-text tasks
        are completed instead of sent to dead-letter.
        """
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                task_type = data.pop("type", "echo")
                return task_type, data
        except (json.JSONDecodeError, TypeError):
            pass
        # Legacy plain-text intent — treat as echo so the task completes
        return "echo", {"message": raw}

    # -- execution -----------------------------------------------------------

    async def _run_task(self, task_id: str, intent: TaskIntent, payload: TaskPayload) -> None:
        from .organs.engine.task_store import TaskState

        store = self._get_store()
        async with self._semaphore:
            try:
                result = await self._execute_task(task_id, intent, payload)
                store.transition(
                    task_id,
                    TaskState.completed,
                    result=json.dumps(result),
                )
            except (OSError, KeyError, ValueError, RuntimeError, TimeoutError) as exc:
                _log.error("Task %s failed: %s", task_id, exc)
                store.transition(task_id, TaskState.failed, error=str(exc))
                store.schedule_retry(task_id)

    async def _execute_task(self, task_id: str, intent: TaskIntent, payload: TaskPayload) -> TaskResult:
        """Execute a single task based on its type."""
        _log.info("Executing task %s (type=%s)", task_id, intent)
        timeout_val = payload.pop("timeout", self._config.task_timeout)
        timeout = float(timeout_val) if isinstance(timeout_val, (int, float, str)) else self._config.task_timeout

        handlers: dict[str, Callable[[], Awaitable[TaskResult]]] = {
            "shell": lambda: self._execute_shell(
                str(payload.get("command", "")),
                timeout,
            ),
            "python": lambda: self._execute_python(str(payload.get("code", "")), timeout),
            "echo": lambda: self._execute_echo(str(payload.get("message", ""))),
            "llm": lambda: self._execute_llm(
                str(payload.get("prompt", "")),
                system=str(payload.get("system", "")),
                model=str(payload.get("model", "")),
            ),
        }

        handler = handlers.get(intent) if isinstance(intent, str) else None
        if handler is None:
            msg = f"Unknown task type: {intent}"
            raise ValueError(msg)
        return await handler()

    async def _execute_shell(self, command: str, timeout: float) -> TaskResult:
        """Execute a shell command via subprocess with timeout."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            msg = f"Shell command timed out after {timeout}s"
            raise TimeoutError(msg) from None

        stdout_str = stdout.decode(errors="replace").strip() if stdout else ""
        stderr_str = stderr.decode(errors="replace").strip() if stderr else ""

        if proc.returncode != 0:
            msg = f"Command failed (rc={proc.returncode}): {stderr_str}"
            raise RuntimeError(msg)

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": proc.returncode,
        }

    async def _execute_python(self, code: str, timeout: float) -> TaskResult:
        """Execute Python code in a sandboxed subprocess with timeout enforcement."""
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{_PROJECT_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(_PROJECT_ROOT)
        )
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _PYTHON_SANDBOX_RUNNER,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_PROJECT_ROOT),
            env=env,
        )
        payload = json.dumps({"code": code}).encode("utf-8")
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            msg = f"Python code timed out after {timeout}s"
            raise TimeoutError(msg) from None

        stdout_str = stdout.decode(errors="replace") if stdout else ""
        stderr_str = stderr.decode(errors="replace").strip() if stderr else ""
        if proc.returncode != 0:
            msg = stderr_str or stdout_str or "Python subprocess execution failed"
            raise RuntimeError(msg)

        try:
            exec_result = json.loads(stdout_str or "{}")
        except json.JSONDecodeError as exc:
            msg = f"Python execution returned invalid sandbox payload: {stdout_str}"
            raise RuntimeError(msg) from exc
        if not isinstance(exec_result, dict):
            msg = f"Python execution returned non-object sandbox payload: {stdout_str}"
            raise RuntimeError(msg)

        raw_success = exec_result.get("success")
        if not isinstance(raw_success, bool):
            msg = "Python execution returned invalid sandbox payload: field 'success' must be bool"
            raise RuntimeError(msg)
        if not raw_success:
            raw_error = exec_result.get("error")
            msg = str(raw_error) if isinstance(raw_error, str) and raw_error else "Python execution failed"
            raise RuntimeError(msg)

        raw_output = exec_result.get("output", "")
        raw_result = exec_result.get("result")
        return {
            "stdout": str(raw_output).strip(),
            "result": raw_result,
        }

    async def _execute_echo(self, message: str) -> TaskResult:
        """Simple echo handler for testing."""
        return {"echo": message}

    async def _execute_llm(self, prompt: str, system: str = "", model: str = "") -> TaskResult:
        """Execute an LLM prompt via the best available provider.

        Uses ``LLMProviderFactory.get_best_available()`` which returns the
        highest-priority provider that is currently available:
          ollama (local, free) → deepseek (cheap) → anthropic → openai → gemini → mock

        The actual LLM call is offloaded to a thread pool to avoid blocking the
        asyncio event loop.
        """
        import asyncio

        from .organs.llm.provider import LLMRequest  # type: ignore[import-not-found]
        from .organs.llm.provider_factory import (  # type: ignore[import-not-found]
            get_default_factory,
        )

        factory = get_default_factory()
        request = LLMRequest(
            prompt=prompt,
            system=system,
            model=model,
            temperature=0.3,
            max_tokens=4096,
        )
        try:
            # ── Model-aware provider routing ──
            # If the user specified a model name, match it to a provider.
            # Otherwise fall back to priority order (ollama → deepseek → ...).
            from .organs.llm.provider import LLMProvider

            model_lower = model.lower().strip() if model else ""

            def _match_provider(name: str) -> LLMProvider | None:
                try:
                    return factory.get_provider(name)
                except KeyError:
                    return None

            provider: LLMProvider | None = None

            # ── If model name is specified, use model-aware routing ──
            if "deepseek" in model_lower:
                provider = _match_provider("deepseek")
            elif model_lower.startswith("gpt") or model_lower.startswith("o"):
                provider = _match_provider("openai")
            elif "claude" in model_lower:
                provider = _match_provider("anthropic")
            elif "gemini" in model_lower:
                provider = _match_provider("gemini")

            # ── If no explicit model match, use quota-aware priority ──
            if provider is None or not provider.is_available():
                from .organs.llm.quota_router import (  # type: ignore[import-not-found]
                    get_quota_aware_priority,
                )

                for pname in get_quota_aware_priority():
                    candidate = _match_provider(pname)
                    if candidate is not None and candidate.is_available():
                        provider = candidate
                        _log.debug("Quota router selected: %s", pname)
                        break

            if provider is None:
                # Ultimate fallback
                provider = factory.get_best_available()

            provider_name = provider.provider_name

            if provider_name == "ollama":
                # Ollama via subprocess curl — avoids thread-safety issues with
                # requests.Session() inside the asyncio event loop.
                import json as _json

                payload = {
                    "model": request.model or provider.default_model,
                    "prompt": request.prompt,
                    "stream": False,
                }
                if request.system:
                    payload["system"] = request.system
                proc = await asyncio.create_subprocess_exec(
                    "curl",
                    "-s",
                    "--max-time",
                    "180",
                    f"{provider._base_url}/api/generate",
                    "-d",
                    _json.dumps(payload),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                raw = stdout.decode().strip()
                if not raw:
                    err = stderr.decode().strip() if stderr else "empty response from Ollama"
                    raise RuntimeError(f"Ollama curl returned empty: {err}")
                try:
                    data = _json.loads(raw)
                except _json.JSONDecodeError as exc:
                    raise RuntimeError(f"Ollama JSON parse error: {exc} | raw={raw[:200]}") from exc
                from .organs.llm.provider import LLMResponse

                response = LLMResponse(
                    content=data.get("response", "").strip(),
                    model=data.get("model", provider.default_model),
                    provider="ollama",
                    input_tokens=data.get("prompt_eval_count", 0),
                    output_tokens=data.get("eval_count", 0),
                )
            else:
                response = await asyncio.to_thread(provider.generate, request)
            return {
                "response": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
            }
        except RuntimeError as exc:
            _log.error("LLM execution failed: %s", exc)
            raise
