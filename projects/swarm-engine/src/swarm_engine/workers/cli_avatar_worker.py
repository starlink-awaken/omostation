from __future__ import annotations

import asyncio
import importlib
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from ._compat import (
    CapabilityRegistry,
    ISynapseWorker,
    MessageEnvelope,
    Receipt,
    RegistryAgentCard,
    SynapseAgentCard,
    agent_ack,
    agent_receive,
    agent_send,
    get_synapse_registry,
)
from .context_injector import ContextInjector
from .workspace_manager import WorkspaceManager  # type: ignore[import-not-found]

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

_log = logging.getLogger(__name__)

HAS_SYNAPSE_REGISTRY = True

logger = logging.getLogger("bos_daemon.cli_avatar_worker")


def _get_harvest_context_injector_factory() -> Callable[..., object] | None:
    try:
        context_injector_mod = importlib.import_module("organs.D_KnowledgeIntegration.services.context_injector")
        return context_injector_mod.get_context_injector
    except (ImportError, ModuleNotFoundError, AttributeError):
        return None


class CliAvatarWorker(ISynapseWorker):
    """
    A worker that acts as a physical body for an external CLI (like claude-code).
    It listens to the bos_agent_router message bus. When a task arrives, it:
    1. Prepares the role context (Persona, Constraints).
    2. Injects this context via Environment Variables (e.g., BOS_ROLE_CONTEXT).
    3. Spawns the CLI tool as a subprocess.
    4. Waits for the tool to finish and sends the result back to the sender.
    """

    def __init__(self, worker_id: str, cli_command: list[str], persona: str, capabilities: list[str]) -> None:
        super().__init__()
        self.worker_id = worker_id
        self.cli_command = cli_command  # e.g., ["claude", "-p"]
        self.persona = persona
        self.capabilities = capabilities
        self.registry = CapabilityRegistry()
        self._running = False
        self._thread = None
        self._current_load = 0
        self.synapse_id = None

    def start(self) -> None:
        logger.info(
            f"[{self.worker_id}] Starting CLI Avatar Worker for '{self.persona}' using cmd: {' '.join(self.cli_command)}"
        )

        # 1. Register with CapabilityRegistry
        card = RegistryAgentCard(
            agent_id=self.worker_id,
            agent_instance_id=self.worker_id,
            persona=self.persona,
            capabilities=self.capabilities,
            max_concurrency=1,  # CLI tools usually block
            endpoint="cli_subprocess_wrapper",
        )
        self.registry.register(card)

        # Register with SynapseRegistry for dynamic discovery
        self._register_with_synapse_registry()

        self._running = True

        # Run the async polling loop in a new thread to not block the main event loop
        def run_async_loop() -> None:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._polling_loop())

        self._thread = threading.Thread(target=run_async_loop, daemon=True, name=f"CliAvatar-{self.worker_id}")
        self._thread.start()

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(
            capabilities=self.capabilities, cost_class="medium", mode="passive", max_eu_budget=300.0
        )

    def accept(self, envelope: MessageEnvelope) -> Receipt:
        if envelope.eu_budget > self.describe().max_eu_budget:
            raise ValueError("EU budget exceeds maximum allowed for this worker.")
        return Receipt(envelope_id=envelope.id)

    def heartbeat(self) -> dict:
        return {
            "status": "healthy" if self._running else "offline",
            "current_load": float(self._current_load),
            "active_tasks": int(self._current_load),
            "remaining_eu": 100.0,
        }

    def _register_with_synapse_registry(self) -> None:
        if not HAS_SYNAPSE_REGISTRY:
            return
        try:
            registry = get_synapse_registry()
            self.synapse_id = registry.register(self)
            logger.info(f"✅ CliAvatarWorker registered with SynapseRegistry: {self.synapse_id}")
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"⚠️ Failed to register with SynapseRegistry: {e}")
            self.synapse_id = None

    def _unregister_from_synapse_registry(self) -> None:
        if not HAS_SYNAPSE_REGISTRY or not self.synapse_id:
            return
        try:
            registry = get_synapse_registry()
            registry.unregister(self.synapse_id)
            logger.info("✅ CliAvatarWorker unregistered from SynapseRegistry")
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"⚠️ Failed to unregister from SynapseRegistry: {e}")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._unregister_from_synapse_registry()

    async def _polling_loop(self) -> None:
        while self._running:
            try:
                # 2. Heartbeat to keep the worker active in the Swarm registry
                self.registry.heartbeat(self.worker_id, self.heartbeat())

                # 3. Check Inbox for Symphony tasks
                messages = agent_receive(target=self.worker_id)
                for msg in messages:
                    logger.info(f"[{self.worker_id}] Task received from {msg['source']}: {msg['summary']}")

                    # Acknowledge receipt immediately so the sender knows it's being worked on
                    agent_ack(msg["id"])

                    # 4. Execute the task by spawning the external CLI process
                    self._current_load += 1
                    try:
                        await self._execute_cli_task(msg)
                    finally:
                        self._current_load -= 1

                await asyncio.sleep(3)
            except (TimeoutError, asyncio.CancelledError) as e:
                logger.error(f"[{self.worker_id}] Error in polling loop: {e}")
                await asyncio.sleep(3)

    async def _execute_cli_task(self, msg: dict[str, Any]) -> None:
        """Spawn the CLI tool and inject the Holo-Context.
        Also handles MessageEnvelope from SynapseRegistry."""
        logger.info(f"[{self.worker_id}] Preparing HCI Context for Phase {msg.get('phase', 1)}...")

        # 1. Allocate Physical Sandbox (Workdir)
        from pathlib import Path

        master_path = Path(os.environ.get("BOS_ROOT", os.getcwd()))
        wm = WorkspaceManager(master_path=master_path)
        # For dynamic workers, we create a layer 1/2 sandbox based on task_id
        task_id = msg["id"]
        sandbox = wm.create_sandbox(self.worker_id, task_id)
        sandbox.enter()
        sandbox_path = str(sandbox.private_path)
        # 2. Inject Holo-Context via ENV
        env = ContextInjector.prepare_environment(self.persona, sandbox_path)

        # 3. Generate Hi-Fi Density Prompt with Knowledge from FactGraph
        # Use HarvestContextInjector to retrieve relevant knowledge from FactGraph
        get_harvest_context_injector = _get_harvest_context_injector_factory()
        if get_harvest_context_injector is not None:
            try:
                harvest_injector = get_harvest_context_injector()
                if harvest_injector is not None:
                    # Derive knowledge query from task content
                    knowledge_query = msg.get("summary", "") + " " + msg.get("content", "")[:200]
                    # Inject harvest context with knowledge retrieval
                    task_prompt = await harvest_injector.inject_harvest_context(
                        persona=self.persona,
                        task_msg=msg,
                        workspace_path=sandbox_path,
                        knowledge_query=knowledge_query,
                    )
                    logger.info(f"[{self.worker_id}] Using EnhancedContextInjector with FactGraph knowledge")
                else:
                    raise RuntimeError("get_harvest_context_injector returned None")
            except (ImportError, AttributeError, RuntimeError, OSError) as exc:
                logger.warning(f"[{self.worker_id}] HarvestContextInjector failed, falling back to basic prompt: {exc}")
                task_prompt = ContextInjector.generate_hifi_prompt(self.persona, msg, sandbox_path)
        else:
            # Fallback to basic context injection
            task_prompt = ContextInjector.generate_hifi_prompt(self.persona, msg, sandbox_path)

        cmd = self.cli_command + [task_prompt]  # noqa: RUF005

        try:
            logger.info(f"[{self.worker_id}] Spawning {self.cli_command[0]} in {sandbox_path}")
            start_time = time.time()

            # Execute with STRICT Workdir and ENV using asyncio
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                cwd=sandbox_path,  # Physical enforcement of directory
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start Metabolic Monitor (Rule-R)
            try:
                from D_Economy.organs.metabolism import MetabolicMonitor  # type: ignore[import-not-found]

                monitor = MetabolicMonitor(process.pid, self.worker_id, budget_eu=300.0)
                monitor.start()
            except ImportError:
                logger.warning(f"[{self.worker_id}] MetabolicMonitor not available. Skipping Rule-R enforcement.")
                monitor = None

            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""
            duration = time.time() - start_time

            if monitor:
                monitor.stop()

            if process.returncode == 0:
                logger.info(f"[{self.worker_id}] Execution successful ({duration:.2f}s).")
                # Clean up sandbox
                sandbox.exit()
                sandbox.cleanup()
                result_content = "Process exited successfully. Output:\n" + stdout[-1000:]
            else:
                logger.warning(f"[{self.worker_id}] Execution failed (Code: {process.returncode}).")
                result_content = f"EXECUTION FAILED.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
            agent_send(
                source=self.worker_id,
                target=msg["source"],
                phase=msg["phase"],
                summary=f"Result: {msg['summary']}",
                content=result_content,
            )

            # ── Notify SwarmResultCollector so WorkerBundle.task_results is populated ──
            import json as _json

            _task_result_payload = _json.dumps(
                {
                    "type": "TASK_RESULT",
                    "task_id": msg["id"],
                    "worker_id": self.worker_id,
                    "success": process.returncode == 0,
                    "output": stdout[:5000],  # cap at 5 k chars
                    "eu_consumed": 0.0,  # MetabolicMonitor feeds the real value externally
                    "duration_s": round(duration, 3),
                    "quality_score": 0.0,  # re-scored by QualityJudge in collector
                    "error": "" if process.returncode == 0 else f"exit code {process.returncode}",
                }
            )
            try:
                agent_send(
                    source=self.worker_id,
                    target="swarm_result_collector",
                    phase=msg.get("phase", "P0"),
                    summary=f"TaskResult from {self.worker_id}",
                    content=_task_result_payload,
                )
            except (TypeError, ValueError, AttributeError) as _rc_exc:
                logger.debug(f"[{self.worker_id}] SwarmResultCollector notify failed (non-fatal): {_rc_exc}")

        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f"[{self.worker_id}] Failed to spawn CLI: {e}")
            agent_send(
                source=self.worker_id,
                target=msg["source"],
                phase=msg["phase"],
                summary="Error",
                content=str(e),
            )


if __name__ == "__main__":
    # A quick standalone test for the CLI Avatar Worker
    logging.basicConfig(level=logging.INFO)
    _log.info("Testing CliAvatarWorker standalone mode...")

    # We use 'echo' as a dummy CLI tool to test the wrapper
    # In reality, this would be ["claude-code", "--prompt"] or ["aider", "--message"]
    dummy_cli = ["echo", "[Dummy CLI Output] Processing prompt:"]

    worker = CliAvatarWorker(
        worker_id="test_cli_worker_01",
        cli_command=dummy_cli,
        persona="Dummy Shell Executor",
        capabilities=["sys.shell", "test.dummy"],
    )

    worker.start()
    _log.info("Worker started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop()
        _log.info("Worker stopped.")
