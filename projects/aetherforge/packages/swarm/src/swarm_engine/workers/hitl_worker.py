from __future__ import annotations

import asyncio
import logging
from typing import Any

from ._compat import (
    ISynapseWorker,
    MessageEnvelope,
    Receipt,
    SynapseAgentCard,
    get_synapse_registry,
)
from .agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]

"""
---
Type: Worker
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: "Human-In-The-Loop (HITL) Worker implementing Universal Synapse Architecture"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Hitl Worker ≡ Worker
# 内涵 ≝ {Hitl, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, HitlWorker)}
# 功能 ⊢ {Hitl_Worker, Init_Hitl, Validate_Worker}
# =============================================================================

_log = logging.getLogger(__name__)
HAS_SYNAPSE_REGISTRY = True


class HitlWorker(AgentDaemonBase, ISynapseWorker):
    def __init__(self, agent_id: str, persona: str, capabilities: list[str]) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=10.0,
            poll_interval=2.0,
        )
        self.synapse_id = None
        self._register_with_registry()

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(capabilities=self.capabilities, cost_class="high", mode="active", max_eu_budget=100.0)

    def accept(self, envelope: MessageEnvelope) -> Receipt:
        if envelope.eu_budget > self.describe().max_eu_budget:
            raise ValueError("EU budget exceeds maximum allowed for this worker.")
        if hasattr(self, "current_eu") and self.current_eu < envelope.eu_budget:
            raise ValueError(f"Insufficient EU. Need {envelope.eu_budget}, have {self.current_eu}")
        return Receipt(envelope_id=envelope.id)

    def heartbeat(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self.running else "offline",
            "current_load": float(self.current_load),
            "active_tasks": int(self.current_load),
            "remaining_eu": self.current_eu,
        }

    def _register_with_registry(self) -> None:
        """Register with SynapseRegistry for dynamic discovery"""
        if not HAS_SYNAPSE_REGISTRY:
            return
        try:
            registry = get_synapse_registry()
            self.synapse_id = registry.register(self)
            _log.info(f"✅ HitlWorker registered with SynapseRegistry: {self.synapse_id}")
        except (TypeError, ValueError, AttributeError) as e:
            _log.info(f"⚠️ Failed to register with SynapseRegistry: {e}")
            self.synapse_id = None

    def _unregister_from_registry(self) -> None:
        """Unregister from SynapseRegistry"""
        if not HAS_SYNAPSE_REGISTRY or not self.synapse_id:
            return
        try:
            registry = get_synapse_registry()
            registry.unregister(self.synapse_id)
            _log.info("✅ HitlWorker unregistered from SynapseRegistry")
        except (TypeError, ValueError, AttributeError) as e:
            _log.info(f"⚠️ Failed to unregister from SynapseRegistry: {e}")

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process task by asking human for input.

        Non-blocking strategy:
        - If a thread-safe _input_queue is attached (via set_input_queue()),
          read from it without touching the event loop.
        - Otherwise, only call input() when no event loop is running,
          so daemon threads are never blocked.
        """
        _log.info(f"\n🔔 [HITL Alert] {self.agent_id} requires human intervention!")

        content = task_payload.get("content", str(task_payload))
        summary = task_payload.get("summary", "No summary provided")

        _log.info(f"Task Summary: {summary}")
        _log.info(f"Task Details: {content}")
        _log.info("Please provide your input (or type 'reject' to fail the task):")

        user_input = ""
        if hasattr(self, "_input_queue") and not self._input_queue.empty():
            user_input = self._input_queue.get_nowait()
        else:
            # Only call synchronous input() when there is NO running event loop.
            # In daemon/async contexts, _input_queue should be used instead.
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                user_input = input("> ")

        if not user_input:
            return {
                "status": "ERROR",
                "error": "No input received (event loop was running and queue was empty).",
                "worker_type": "HitlWorker",
            }

        if user_input.strip().lower() == "reject":
            return {
                "status": "FAILED",
                "error": "Human rejected the task.",
                "worker_type": "HitlWorker",
            }

        return {
            "status": "SUCCESS",
            "result": user_input,
            "worker_type": "HitlWorker",
            "handover": {"content": user_input, "summary": "Human Input Provided"},
        }

    def set_input_queue(self, queue: Any) -> None:
        """Attach a thread-safe queue for async-compatible input delivery."""
        self._input_queue = queue

    def _execute_task_in_sandbox(
        self, payload: dict[str, object], msg_id: Any, summary: Any
    ) -> tuple[dict[str, Any], float]:
        """Override to bypass file sandbox for HITL worker."""
        import time

        start_t = time.time()
        result = self.process_task(payload)
        return result, (time.time() - start_t) * 1000

    def shutdown(self) -> None:
        """Override shutdown to cleanup registry"""
        self._unregister_from_registry()
        super().shutdown()


if __name__ == "__main__":
    worker = HitlWorker(
        agent_id="hitl_gate_01",
        persona="You are a human-in-the-loop gateway.",
        capabilities=["human.approval", "human.input"],
    )
    _log.info(f"🚀 Starting HitlWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
    finally:
        worker.shutdown()
