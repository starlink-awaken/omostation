from __future__ import annotations

from ._compat import ProjectPaths, WorkerHandle, WorkerState

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Core ≡ Module
# 内涵 ≝ {Core}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Core)}
# 功能 ⊢ {Init_Core, Execute_Core, Validate_Core}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import logging
import os
import shlex
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from threading import RLock
from typing import Any

from ._events import (  # type: ignore[import-not-found]
    _DEFAULT_HATCH_TIMEOUT_S,
    _PROCESS_POLL_INTERVAL_S,
    _emit_hatcher_event,
)
from .exceptions import HatchError, HatchTimeoutError  # type: ignore[import-not-found]
from .organs.engine.agent_cli_bootstrap import (  # type: ignore[import-not-found]
    build_agent_cli_handle,
    inject_agent_cli_soul_env,
    prepare_agent_cli_bootstrap,
    resolve_agent_cli_command,
    spawn_agent_cli_process,
)
from .organs.engine.hatch_runtime import (  # type: ignore[import-not-found]
    WorkerProcessExitedError,
    WorkerProcessStartTimeoutError,
    build_active_worker_handle,
    inject_soul_env,
    spawn_worker_process,
    wait_for_worker_process_start,
)
from .organs.engine.hatcher_events import (  # type: ignore[import-not-found]
    emit_worker_hatched,
    emit_worker_terminated,
)
from .organs.engine.retry_policy import (  # type: ignore[import-not-found]
    RetryExhaustedError,
    RetryPolicy,
    RetryState,
)
from .organs.engine.task_store import TaskState, TaskStore  # type: ignore[import-not-found]
from .thread_worker import _thread_worker  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

_project_root = str(ProjectPaths.ROOT)


class Hatcher:
    """
    Spawns CLI-based Swarm Workers as secure subprocesses.

    Responsibilities:
    - Parse the ``cli_command_template`` from a spore config.
    - Inject ONLY the env vars listed in ``env_whitelist`` from the current OS env.
    - Launch the process with :class:`subprocess.Popen`.
    - Verify the process is alive within ``hatch_timeout_s``.
    - Return a :class:`WorkerHandle` in ``ACTIVE`` state.

    Security invariant (enforced by membrane_audit_hook):
        This module MUST remain inside ``D-Execution/organs/engine/`` so that the
        audit hook's authorized-path check passes for ``subprocess.Popen`` calls.
    """

    def __init__(self, task_store: TaskStore | None = None) -> None:
        self._lock = RLock()
        self._handles: dict[str, WorkerHandle] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._retry_states: dict[str, RetryState] = {}
        self._retry_policy: RetryPolicy | None = None
        self._task_store: TaskStore | None = task_store
        self.initialize()

    # ─── IOrgan ───────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        super().initialize()
        logger.info("[Hatcher] Initialized.")
        _emit_hatcher_event("hatcher.initialized", {"status": "ready"})

    def shutdown(self) -> None:
        """Terminate all managed workers on shutdown."""
        with self._lock:
            for handle in list(self._handles.values()):
                try:
                    self._terminate_process(handle, reason="Hatcher.shutdown")
                except (TypeError, ValueError, AttributeError) as exc:
                    logger.warning(f"[Hatcher] Shutdown cleanup error for {handle.worker_id}: {exc}")
        super().shutdown()
        _emit_hatcher_event("hatcher.shutdown", {"status": "terminated"})

    # ─── Public API ───────────────────────────────────────────────────────────

    def hatch(
        self,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> WorkerHandle:
        """Spawn a new Worker subprocess from a spore template."""
        spore_id = spore_config.get("id", "unknown")
        handler_type = spore_config.get("handler_type", "cli_subprocess")
        hatch_timeout = float(spore_config.get("hatch_timeout_s", _DEFAULT_HATCH_TIMEOUT_S))
        effective_policy = retry_policy or self._retry_policy

        logger.info(f"[Hatcher] Hatching spore='{spore_id}' handler='{handler_type}' eu={eu_budget}")

        try:
            handle = self._dispatch_hatch(
                handler_type, spore_config, task_prompt, eu_budget, hatch_timeout, soul_context
            )
        except (HatchError, HatchTimeoutError) as exc:
            if effective_policy is not None:
                return self._handle_hatch_failure(
                    str(exc), spore_config, task_prompt, eu_budget, soul_context, effective_policy
                )
            raise

        if effective_policy is not None:
            with self._lock:
                self._retry_states[handle.worker_id] = RetryState(
                    attempt_count=0,
                    last_error="",
                    spore_config=dict(spore_config),
                    task_prompt=task_prompt,
                    eu_budget=eu_budget,
                    soul_context=soul_context,
                )
        return handle

    def _dispatch_hatch(
        self,
        handler_type: str,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        hatch_timeout: float,
        soul_context: dict | None,
    ) -> WorkerHandle:
        """Route to the correct handler-type spawner."""
        if handler_type == "cli_subprocess":
            return self._hatch_cli_subprocess(
                spore_config, task_prompt, eu_budget, hatch_timeout, soul_context=soul_context
            )
        elif handler_type == "internal_thread":
            return self._hatch_internal_thread(spore_config, task_prompt, eu_budget, soul_context=soul_context)
        elif handler_type == "agent_cli":
            return self._hatch_agent_cli(spore_config, task_prompt, eu_budget, soul_context=soul_context)
        else:
            spore_id = spore_config.get("id", "unknown")
            raise ValueError(
                f"[Hatcher] Unsupported handler_type='{handler_type}' for spore '{spore_id}'. "
                f"Supported types: 'cli_subprocess', 'internal_thread', 'agent_cli'."
            )

    # ── Async dispatch ────────────────────────────────────────────────────────

    async def dispatch_task_async(
        self,
        task: dict,
        worker_pool: Any | None = None,
    ) -> str:
        """Dispatch *task* through a :class:`WorkerPool` when available."""
        from .organs.engine.worker_pool import WorkerPool  # type: ignore[import-not-found]

        pool: WorkerPool | None = worker_pool if isinstance(worker_pool, WorkerPool) else None

        if pool is not None and pool.is_running:
            task_id = await pool.submit(task)
            logger.debug("[Hatcher] dispatch_task_async → pool task_id=%s", task_id)
            return task_id

        return await self._execute_locally(task)

    async def _execute_locally(self, task: dict) -> str:
        """Local fallback execution for dispatch_task_async."""
        try:
            import asyncio

            task_type = task.get("type", "passthrough")
            if task_type in ("passthrough",):
                payload = task.get("payload", task)
                await asyncio.sleep(0)
                return f"local:{payload!r}"
            from .organs.llm.provider import LLMRequest  # type: ignore[import-not-found]
            from .organs.llm.provider_factory import (  # type: ignore[import-not-found]
                get_default_factory,
            )

            if task_type in ("llm_generate", "async_llm_generate"):
                provider = get_default_factory().get_best_available()
                req_data = task.get("request", {})
                request = LLMRequest(prompt=req_data.get("prompt", "local-fallback"))
                response = await provider.async_generate(request)
                return f"local:{response.content}"
        except (ImportError, OSError, ValueError) as e:
            logger.warning("[Hatcher] _execute_locally error: %s", e)
        return f"local:unhandled-task-type={task_type!r}"

    def terminate(self, worker_id: str, reason: str = "explicit_terminate") -> None:
        """Gracefully terminate a managed worker."""
        with self._lock:
            handle = self._handles.get(worker_id)
            is_thread = worker_id in self._threads

        if handle is None:
            raise KeyError(f"[Hatcher] Unknown worker_id='{worker_id}'")

        if is_thread:
            self._terminate_thread(worker_id, reason=reason)
        else:
            self._terminate_process(handle, reason=reason)

    def cancel(self, worker_id: str) -> bool:
        """Request cancellation for a managed worker."""
        with self._lock:
            handle = self._handles.get(worker_id)
        if handle is None:
            return False

        with self._lock:
            cancel_event = self._cancel_events.get(worker_id)
        if cancel_event is not None:
            cancel_event.set()

        try:
            self.terminate(worker_id, reason="cancel")
        except KeyError:
            pass

        if self._task_store is not None:
            task_id = f"T-{worker_id[:8]}"
            try:
                self._task_store.transition(task_id, TaskState.cancelled)
            except KeyError:
                pass

        _emit_hatcher_event("hatcher.worker.cancelled", {"worker_id": worker_id})
        return True

    def drain_all(self, timeout: float = 30.0) -> None:
        """Cancel every managed worker and wait for completion."""
        with self._lock:
            worker_ids = list(self._handles.keys())

        for wid in worker_ids:
            self.cancel(wid)

        deadline = time.monotonic() + timeout
        for wid in worker_ids:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            with self._lock:
                thread = self._threads.get(wid)
            if thread is not None and thread.is_alive():
                thread.join(timeout=remaining)

        _emit_hatcher_event(
            "hatcher.drain_all",
            {"worker_count": len(worker_ids), "timeout": timeout},
        )
        logger.info("[Hatcher] drain_all complete — %d worker(s) cancelled.", len(worker_ids))

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _build_command(self, template: str, task_prompt: str) -> list[str]:
        """Parse cli_command_template and inject task_prompt safely."""
        _SENTINEL = "___TASK_PROMPT_SENTINEL___"  # noqa: N806
        normalised = (
            template.replace("'{TASK_PROMPT}'", _SENTINEL)
            .replace('"{TASK_PROMPT}"', _SENTINEL)
            .replace("{TASK_PROMPT}", _SENTINEL)
        )
        base_parts = shlex.split(normalised)
        return [task_prompt if part == _SENTINEL else part for part in base_parts]

    def _build_env(self, env_whitelist: list[str]) -> dict[str, str]:
        """Build a minimal environment dict containing only whitelisted keys."""
        filtered: dict[str, str] = {}
        for key in env_whitelist:
            value = os.environ.get(key)
            if value is not None:
                filtered[key] = value
        if "PATH" not in filtered and "PATH" in os.environ:
            filtered["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
        return filtered

    def _register_handle(self, handle: WorkerHandle) -> WorkerHandle:
        """Track a live worker handle under the shared handle registry."""
        with self._lock:
            self._handles[handle.worker_id] = handle
        return handle

    def _register_internal_thread_runtime(
        self,
        handle: WorkerHandle,
        thread: threading.Thread,
        cancel_event: threading.Event,
    ) -> WorkerHandle:
        """Track the handle plus thread-specific runtime state."""
        with self._lock:
            self._handles[handle.worker_id] = handle
            self._threads[handle.worker_id] = thread
            self._cancel_events[handle.worker_id] = cancel_event
        return handle

    def _hatch_cli_subprocess(
        self,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        hatch_timeout: float,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Core subprocess launch logic for cli_subprocess handler type."""
        template = spore_config.get("cli_command_template", "")
        if not template:
            raise ValueError(f"[Hatcher] Spore '{spore_config.get('id')}' is missing 'cli_command_template'.")

        cmd = self._build_command(template, task_prompt)
        env_whitelist: list[str] = spore_config.get("env_whitelist", [])
        env = self._build_env(env_whitelist)

        if soul_context:
            inject_soul_env(env, soul_context)
            logger.info(f"[Hatcher] Injecting soul context role_id={soul_context.get('role_id')!r} into worker env.")
        try:
            HoloMemoryInjector = __import__(  # noqa: N806
                "organs.D_Gateway.organs.holo_memory_injector", fromlist=["HoloMemoryInjector"]
            ).HoloMemoryInjector

            role_id = soul_context.get("role_id", "") if soul_context else ""
            task_intent = task_prompt[:200] if task_prompt else ""
            _mem_injector = HoloMemoryInjector()
            _mem_slices = _mem_injector.retrieve_for_role(role_id=role_id, task_intent=task_intent)
            if _mem_slices:
                env["BOS_MEMORY_CONTEXT"] = _mem_injector.serialize_for_env(_mem_slices)
                logger.debug("[Hatcher] Injected %d memory slice(s) into worker env.", len(_mem_slices))
        except ImportError as _exc:
            logger.debug("[Hatcher] HoloMemory injection skipped (non-fatal): %s", _exc)

        try:
            KnowledgeInjector = __import__(  # noqa: N806
                "organs.D_Gateway.organs.knowledge_injector", fromlist=["KnowledgeInjector"]
            ).KnowledgeInjector

            role_id = soul_context.get("role_id", "") if soul_context else ""
            _know_injector = KnowledgeInjector()
            _know_slices = _know_injector.get_static_knowledge(role_id)
            if _know_slices:
                env["BOS_KNOWLEDGE_CONTEXT"] = _know_injector.serialize_for_env(_know_slices)
                logger.debug("[Hatcher] Injected %d knowledge slice(s) into worker env.", len(_know_slices))
        except ImportError as _exc:
            logger.debug("[Hatcher] Knowledge injection skipped (non-fatal): %s", _exc)

        capabilities: list[str] = spore_config.get("capabilities", [])
        worker_id = f"worker_{spore_config.get('id', 'unknown')}_{uuid.uuid4().hex[:8]}"
        spore_id = spore_config.get("id", "unknown")

        self._inject_identity(worker_id=worker_id, spore_config=spore_config, env=env, soul_context=soul_context)

        logger.info(f"[Hatcher] Spawning worker={worker_id} cmd={cmd[0]!r} …")

        import sqlite3

        try:
            EnergyLedger = __import__(  # noqa: N806
                "organs.D_Economy.organs.energy_ledger",
                fromlist=["EnergyLedger"],
            ).EnergyLedger
            _ledger = EnergyLedger()
            _ledger._handle_consume(
                {
                    "agent_id": worker_id,
                    "amount": eu_budget,
                    "reason": f"swarm_hatch:{spore_id}",
                },
            )
            logger.info(f"[Hatcher] Pre-deducted {eu_budget} EU for worker '{worker_id}'")
        except (
            ImportError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            ValueError,
            sqlite3.Error,
        ) as exc:
            logger.warning(f"[Hatcher] EU pre-deduction skipped (non-fatal): {exc}")
        finally:
            if "_ledger" in dir() and hasattr(_ledger, "close"):
                _ledger.close()

        try:
            process = spawn_worker_process(cmd=cmd, env=env)
        except (FileNotFoundError, PermissionError) as exc:
            logger.error(f"[Hatcher] Failed to spawn '{cmd[0]}': {exc}")
            raise HatchError(
                f"[Hatcher] Could not spawn CLI '{cmd[0]}' for spore '{spore_config.get('id')}': {exc}"
            ) from exc

        try:
            wait_for_worker_process_start(
                process=process,
                worker_id=worker_id,
                hatch_timeout=hatch_timeout,
                poll_interval_s=_PROCESS_POLL_INTERVAL_S,
            )
        except WorkerProcessExitedError as exc:
            logger.error(
                f"[Hatcher] Worker '{worker_id}' exited immediately rc={exc.returncode}. "
                f"stdout={exc.stdout[:200]!r} stderr={exc.stderr[:200]!r}"
            )
            raise HatchError(f"[Hatcher] {exc}") from exc
        except WorkerProcessStartTimeoutError as exc:
            logger.error(f"[Hatcher] Worker '{worker_id}' failed to start within {hatch_timeout}s")
            raise HatchTimeoutError(f"[Hatcher] {exc} (spore='{spore_config.get('id')}')") from exc

        now = time.time()
        handle = build_active_worker_handle(
            worker_id=worker_id,
            spore_id=spore_config.get("id", "unknown"),
            pid=process.pid,
            eu_budget=eu_budget,
            started_at=now,
            capabilities=capabilities,
            process=process,
        )

        self._register_handle(handle)

        emit_worker_hatched(
            worker_id=worker_id,
            handler="cli_subprocess",
            pid=process.pid,
            eu_budget=eu_budget,
            logger=logger,
            emit_event=_emit_hatcher_event,
        )
        return handle

    def _hatch_internal_thread(
        self,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Spawn a swarm worker as an in-process daemon thread."""
        try:
            from .organs.engine.result_bus import ResultBus  # type: ignore[import-not-found]
        except ImportError:
            from engine.result_bus import ResultBus  # type: ignore[no-redef, import-not-found]

        spore_id = spore_config.get("id", "unknown")
        capabilities: list[str] = spore_config.get("capabilities", [])
        worker_id = f"worker_{spore_id}_{uuid.uuid4().hex[:8]}"

        _thread_env: dict[str, str] = {}
        self._inject_identity(
            worker_id=worker_id,
            spore_config=spore_config,
            env=_thread_env,
            soul_context=soul_context,
        )
        for _k, _v in _thread_env.items():
            os.environ.setdefault(_k, _v)

        result_bus = ResultBus.get_instance()
        cancel_event = threading.Event()

        thread = threading.Thread(
            target=_thread_worker,
            kwargs={
                "worker_id": worker_id,
                "spore_id": spore_id,
                "task_prompt": task_prompt,
                "soul_context": soul_context,
                "eu_budget": eu_budget,
                "result_bus": result_bus,
                "cancel_event": cancel_event,
            },
            daemon=True,
            name=f"swarm-{worker_id[:28]}",
        )
        thread.start()

        now = time.time()
        handle = build_active_worker_handle(
            worker_id=worker_id,
            spore_id=spore_id,
            pid=thread.ident or 0,
            eu_budget=eu_budget,
            started_at=now,
            capabilities=capabilities,
            process=None,
        )

        self._register_internal_thread_runtime(handle, thread, cancel_event)

        emit_worker_hatched(
            worker_id=worker_id,
            handler="internal_thread",
            thread_ident=thread.ident,
            eu_budget=eu_budget,
            logger=logger,
            emit_event=_emit_hatcher_event,
        )
        return handle

    # ─── Identity injection ───────────────────────────────────────────────────

    def _inject_identity(
        self,
        worker_id: str,
        spore_config: dict[str, Any],
        env: dict[str, str],
        context_file: str = "",
        mcp_endpoint: str = "",
        soul_context: dict | None = None,
    ) -> None:
        """Inject standard BOS identity env vars into *env* (mutates in place)."""
        role_id = spore_config.get("role_id", spore_config.get("id", "unknown"))
        task_id = spore_config.get("task_id", f"task-{worker_id[:8]}")
        session_id = spore_config.get("session_id", os.environ.get("BOS_SESSION_ID", ""))

        env["BOS_WORKER_ID"] = worker_id
        env["BOS_ROLE_ID"] = role_id
        env["BOS_TASK_ID"] = task_id
        env["BOS_SESSION_ID"] = session_id

        if soul_context is not None:
            soul_path = (
                str(Path(_project_root) / "docs/archive/root_cleanup_20260428/SOUL.md")
                if _project_root
                else "docs/archive/root_cleanup_20260428/SOUL.md"
            )
            env["BOS_SOUL_PATH"] = soul_path
            control_plane = str(
                soul_context.get(
                    "control_plane",
                    "cockpit" if soul_context.get("cockpit_mode") else "",
                )
            )
            if control_plane:
                env["BOS_CONTROL_PLANE"] = control_plane
            controller_session_id = str(soul_context.get("controller_session_id", soul_context.get("session_id", "")))
            controller_node_id = str(soul_context.get("controller_node_id", soul_context.get("node_id", "")))
            if controller_session_id:
                env["BOS_CONTROLLER_SESSION_ID"] = controller_session_id
            if controller_node_id:
                env["BOS_CONTROLLER_NODE_ID"] = controller_node_id

        if mcp_endpoint:
            env["BOS_MCP_ENDPOINT"] = mcp_endpoint
        if context_file:
            env["BOS_CONTEXT_FILE"] = context_file

    # ─── agent_cli handler ────────────────────────────────────────────────────

    def _hatch_agent_cli(
        self,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None = None,
    ) -> WorkerHandle:
        """Spawn an external agent CLI process using the Bootstrap Protocol."""
        try:
            from .organs.engine.agent_cli_bootstrap import (
                WorkerContext,  # noqa: F401
                write_worker_context,  # noqa: F401
            )
        except ImportError:
            pass
        try:
            from .organs.engine.agent_cli_bootstrap import (
                CockpitBinding,  # noqa: F401
                apply_cockpit_binding,  # noqa: F401
            )
        except ImportError:
            pass
        spore_id = spore_config.get("id", "unknown")
        capabilities: list[str] = spore_config.get("capabilities", [])
        bootstrap = prepare_agent_cli_bootstrap(
            spore_config=spore_config,
            task_prompt=task_prompt,
            soul_context=soul_context,
            project_root=_project_root,
        )
        worker_id = bootstrap.worker_id
        mcp_endpoint = bootstrap.mcp_endpoint
        mcp_config_path = bootstrap.mcp_config_path
        context_file = bootstrap.context_file
        full_prompt = bootstrap.full_prompt
        logger.info(f"[Hatcher] agent_cli context written to '{context_file}' worker_id='{worker_id}'")

        env_whitelist: list[str] = spore_config.get("env_whitelist", [])
        env = self._build_env(env_whitelist)

        self._inject_identity(
            worker_id=worker_id,
            spore_config=spore_config,
            env=env,
            context_file=context_file,
            mcp_endpoint=mcp_endpoint,
            soul_context=soul_context,
        )

        inject_agent_cli_soul_env(env, soul_context)
        env["CLAUDE_MCP_CONFIG"] = mcp_config_path

        cmd = resolve_agent_cli_command(
            spore_config=spore_config,
            full_prompt=full_prompt,
            build_command=self._build_command,
        )

        try:
            process = spawn_agent_cli_process(
                cmd=cmd,
                env=env,
                cwd=str(Path(context_file).parent),
            )
        except (FileNotFoundError, PermissionError) as exc:
            logger.error(f"[Hatcher] Failed to spawn agent_cli '{cmd[0]}': {exc}")
            raise HatchError(f"[Hatcher] Could not spawn agent_cli '{cmd[0]}' for spore '{spore_id}': {exc}") from exc

        now = time.time()
        handle = build_agent_cli_handle(
            worker_id=worker_id,
            spore_id=spore_id,
            process=process,
            eu_budget=eu_budget,
            started_at=now,
            capabilities=capabilities,
            context_file=context_file,
        )

        self._register_handle(handle)

        emit_worker_hatched(
            worker_id=worker_id,
            handler="agent_cli",
            pid=process.pid,
            eu_budget=eu_budget,
            context_file=context_file,
            logger=logger,
            emit_event=_emit_hatcher_event,
        )
        return handle

    # ─── Retry logic ──────────────────────────────────────────────────────────

    def _handle_hatch_failure(
        self,
        error: str,
        spore_config: dict[str, Any],
        task_prompt: str,
        eu_budget: float,
        soul_context: dict | None,
        policy: RetryPolicy,
    ) -> WorkerHandle:
        """Attempt retries with backoff after an initial hatch failure."""
        spore_id = spore_config.get("id", "unknown")
        handler_type = spore_config.get("handler_type", "cli_subprocess")
        hatch_timeout = float(spore_config.get("hatch_timeout_s", _DEFAULT_HATCH_TIMEOUT_S))
        last_error = error

        for attempt in range(1, policy.max_attempts + 1):
            delay = policy.delay_for_attempt(attempt)
            logger.warning(
                "[Hatcher] Worker for spore '%s' failed (attempt %d/%d). Retrying in %.2fs — %s",
                spore_id,
                attempt,
                policy.max_attempts,
                delay,
                last_error,
            )
            _emit_hatcher_event(
                "hatcher.worker.retry_scheduled",
                {
                    "spore_id": spore_id,
                    "attempt": attempt,
                    "max_attempts": policy.max_attempts,
                    "delay_s": round(delay, 2),
                    "error": last_error,
                },
            )

            time.sleep(delay)

            try:
                handle = self._dispatch_hatch(
                    handler_type,
                    spore_config,
                    task_prompt,
                    eu_budget,
                    hatch_timeout,
                    soul_context,
                )
            except (HatchError, HatchTimeoutError) as exc:
                last_error = str(exc)
                continue

            logger.info(
                "[Hatcher] ✅ Retry succeeded for spore '%s' on attempt %d.",
                spore_id,
                attempt,
            )
            with self._lock:
                self._retry_states[handle.worker_id] = RetryState(
                    attempt_count=attempt,
                    last_error=last_error,
                    spore_config=dict(spore_config),
                    task_prompt=task_prompt,
                    eu_budget=eu_budget,
                    soul_context=soul_context,
                )
            return handle

        self._on_retry_exhausted(spore_id, policy.max_attempts, last_error)
        raise RetryExhaustedError(spore_id, policy.max_attempts, last_error)

    def _schedule_retry(self, worker_id: str, policy: RetryPolicy) -> float:
        """Compute the next retry delay for *worker_id* and update its state."""
        with self._lock:
            state = self._retry_states.get(worker_id)
            if state is None:
                return 0.0
            state.attempt_count += 1
            delay = policy.delay_for_attempt(state.attempt_count)
            state.next_retry_at = time.monotonic() + delay
            return delay

    def _on_retry_exhausted(self, worker_id: str, attempts: int, last_error: str) -> None:
        """Emit a dead-letter event and log when all retries are used up."""
        logger.warning(
            "[Hatcher] �� Retries exhausted for '%s' after %d attempts. Last error: %s — sending to dead-letter.",
            worker_id,
            attempts,
            last_error,
        )
        _emit_hatcher_event(
            "hatcher.worker.dead_letter",
            {"worker_id": worker_id, "attempts": attempts, "last_error": last_error},
        )

    def _terminate_thread(self, worker_id: str, reason: str) -> None:
        """Signal a thread worker to stop via its cancellation Event."""
        with self._lock:
            cancel_event = self._cancel_events.get(worker_id)
            thread = self._threads.get(worker_id)

        if cancel_event is not None:
            cancel_event.set()
            logger.info(f"[Hatcher] Cancel event set for thread worker '{worker_id}' reason='{reason}'")

        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
            if thread.is_alive():
                logger.warning(
                    f"[Hatcher] Thread worker '{worker_id}' still alive after 5s join — cannot forcibly terminate."
                )

        with self._lock:
            self._threads.pop(worker_id, None)
            self._cancel_events.pop(worker_id, None)
            handle = self._handles.get(worker_id)
            if handle is not None:
                handle.state = WorkerState.REAPED

        emit_worker_terminated(
            worker_id=worker_id,
            reason=reason,
            handler="internal_thread",
            logger=logger,
            log_message=f"[Hatcher] Thread worker '{worker_id}' terminated (reason='{reason}').",
            emit_event=_emit_hatcher_event,
        )

    def _terminate_process(self, handle: WorkerHandle, reason: str) -> None:
        """SIGTERM → 5s grace period → SIGKILL sequence."""
        process: subprocess.Popen | None = handle.process
        if process is None:
            logger.warning(f"[Hatcher] Worker '{handle.worker_id}' has no process — skipping.")
            return

        if process.poll() is not None:
            logger.debug(f"[Hatcher] Worker '{handle.worker_id}' already exited — no-op.")
            return

        logger.info(f"[Hatcher] Terminating worker='{handle.worker_id}' pid={handle.pid} reason='{reason}'")

        try:
            process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            return

        try:
            process.wait(timeout=5.0)
            logger.info(f"[Hatcher] Worker '{handle.worker_id}' terminated gracefully.")
        except subprocess.TimeoutExpired:
            logger.warning(f"[Hatcher] Worker '{handle.worker_id}' did not exit after SIGTERM — sending SIGKILL")
            try:
                process.send_signal(signal.SIGKILL)
                process.wait(timeout=3.0)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass

        with self._lock:
            if handle.worker_id in self._handles:
                self._handles[handle.worker_id].state = WorkerState.REAPED
        emit_worker_terminated(
            worker_id=handle.worker_id,
            reason=reason,
            handler="cli_subprocess",
            emit_event=_emit_hatcher_event,
        )

    # ─── CoreService.call dispatch ───────────────────────────────────────────

    def _handle_hatch(self, params: dict[str, Any]) -> dict[str, Any]:
        spore_config = params.get("spore_config", {})
        task_prompt = params.get("task_prompt", "")
        eu_budget = float(params.get("eu_budget", 1000.0))
        soul_context = params.get("soul_context", None)
        retry_policy_raw = params.get("retry_policy", None)
        retry_policy: RetryPolicy | None = None
        if isinstance(retry_policy_raw, dict):
            retry_policy = RetryPolicy(**retry_policy_raw)
        elif isinstance(retry_policy_raw, RetryPolicy):
            retry_policy = retry_policy_raw
        try:
            handle = self.hatch(
                spore_config,
                task_prompt,
                eu_budget,
                soul_context=soul_context,
                retry_policy=retry_policy,
            )
            return {
                "status": "ok",
                "worker_id": handle.worker_id,
                "pid": handle.pid,
                "state": handle.state.value,
            }
        except (HatchError, HatchTimeoutError, RetryExhaustedError, ValueError) as exc:
            logger.error(f"[Hatcher] Hatch failed: {exc}")
            raise

    def _handle_terminate(self, params: dict[str, Any]) -> dict[str, Any]:
        worker_id = params.get("worker_id", "")
        reason = params.get("reason", "api_request")
        self.terminate(worker_id, reason=reason)
        return {"status": "ok", "worker_id": worker_id}
