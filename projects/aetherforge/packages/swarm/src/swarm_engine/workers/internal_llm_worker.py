from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from ._compat import (
    InferenceOracle,
    ISynapseWorker,
    MessageEnvelope,
    Receipt,
    SynapseAgentCard,
    get_synapse_registry,
)
from .agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]
from .knowledge_enhancement_mixin import KnowledgeEnhancementMixin  # type: ignore[import-not-found]

"""
---
Type: Worker
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: "Internal LLM Worker implementing Universal Synapse Architecture"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Internal Llm Worker ≡ Worker
# 内涵 ≝ {Internal, Llm, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, InternalLlmWorker)}
# 功能 ⊢ {Internal_Llm, Llm_Worker, Worker_Init}
# =============================================================================

_log = logging.getLogger(__name__)
HAS_SYNAPSE_REGISTRY = True


class InternalLlmWorker(KnowledgeEnhancementMixin, AgentDaemonBase, ISynapseWorker):
    def __init__(self, agent_id: str, persona: str, capabilities: list[str]) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=10.0,
            poll_interval=2.0,
        )
        self.oracle = InferenceOracle.get_instance()
        self.synapse_id = None
        self._register_with_registry()

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(capabilities=self.capabilities, cost_class="low", mode="active", max_eu_budget=50.0)

    def accept(self, envelope: MessageEnvelope) -> Receipt:
        if envelope.eu_budget > self.describe().max_eu_budget:
            raise ValueError("EU budget exceeds maximum allowed for this worker.")
        if hasattr(self, "current_eu") and self.current_eu < envelope.eu_budget:
            raise ValueError(f"Insufficient EU. Need {envelope.eu_budget}, have {self.current_eu}")
        return Receipt(envelope_id=envelope.id)

    def heartbeat(self) -> dict[str, Any]:
        return {"load": self.current_load, "health": "healthy", "remaining_eu": 100.0}

    def _register_with_registry(self) -> None:
        """Register with SynapseRegistry for dynamic discovery"""
        if not HAS_SYNAPSE_REGISTRY:
            return
        try:
            registry = get_synapse_registry()
            self.synapse_id = registry.register(self)
            _log.info("✅ InternalLlmWorker registered with SynapseRegistry: {self.synapse_id}")
        except (TypeError, ValueError, AttributeError):
            _log.info("⚠️ Failed to register with SynapseRegistry: {e}")
            self.synapse_id = None

    def _unregister_from_registry(self) -> None:
        """Unregister from SynapseRegistry"""
        if not HAS_SYNAPSE_REGISTRY or not self.synapse_id:
            return
        try:
            registry = get_synapse_registry()
            registry.unregister(self.synapse_id)
            _log.info("✅ InternalLlmWorker unregistered from SynapseRegistry")
        except (TypeError, ValueError, AttributeError):
            _log.info("⚠️ Failed to unregister from SynapseRegistry: {e}")

    def _execute_task_in_sandbox(
        self,
        payload: dict[str, Any] | MessageEnvelope,
        msg_id: str,
        summary: str,
    ) -> tuple[dict[str, Any], float]:
        """Override to bypass file sandbox for internal LLM worker."""
        start_t = time.time()
        result = self.process_task(payload)
        return result, (time.time() - start_t) * 1000

    def _resolve_oracle_result(self, result: Any) -> dict[str, Any]:
        if not inspect.isawaitable(result):
            return cast(dict[str, Any], result)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return cast(dict[str, Any], asyncio.run(result))

        with ThreadPoolExecutor(max_workers=1) as executor:
            return cast(dict[str, Any], executor.submit(asyncio.run, result).result())

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process task using the internal LLM adapter.
        Also supports direct MessageEnvelope from SynapseRegistry.
        """
        _log.info("🧠 [{self.agent_id}] Processing task via LLM Adapter...")

        # Handle both direct payload and MessageEnvelope
        if isinstance(task_payload, MessageEnvelope):
            prompt = task_payload.payload.get("content", "")
            context_dict = task_payload.payload.get("synthesized_context", {})
            summary = task_payload.payload.get("summary", "Direct synapse task")
            eu_budget = task_payload.eu_budget
        else:
            prompt = task_payload.get("content", str(task_payload))
            summary = task_payload.get("summary", "No summary provided")
            context_dict = {}
            eu_budget = 50.0

        # Build context with EnhancedContextInjector integration
        # Use HarvestContextInjector to retrieve relevant knowledge from FactGraph
        enhanced_context = f"Task Summary: {summary}\n"
        if context_dict.get("personality"):
            personality = context_dict["personality"]
            enhanced_context += f"\nPersona Traits: {', '.join(personality.get('traits', []))}\n"
            enhanced_context += f"Communication Style: {personality.get('communication_style', 'neutral')}\n"

        # Enhanced context injection from FactGraph using KnowledgeEnhancementMixin
        temp_task_payload = {"summary": summary, "content": prompt}
        self.enhance_task_with_knowledge(temp_task_payload, self.persona, os.getcwd())
        if "_enhanced_prompt" in temp_task_payload:
            enhanced_context += f"\n[Enhanced Context from FactGraph]:\n{temp_task_payload['_enhanced_prompt']}\n"

        context = enhanced_context

        try:
            # Check EU budget
            if eu_budget < 5.0:
                return {
                    "status": "ERROR",
                    "error": "Insufficient EU budget",
                    "worker_type": "InternalLlmWorker",
                }

            # [Evolution V4] Call Unified InferenceOracle instead of local adapter
            oracle_res = self._resolve_oracle_result(self.oracle.infer(prompt=prompt, context=context))

            if oracle_res["status"] == "error":
                return {
                    "status": "ERROR",
                    "error": oracle_res["message"],
                    "worker_type": "InternalLlmWorker",
                }

            response = oracle_res["content"]

            return {
                "status": "SUCCESS",
                "result": response,
                "worker_type": "InternalLlmWorker",
                "eu_consumed": 10.0,
                "handover": {"content": response, "summary": "LLM Task Completed"},
            }
        except (TypeError, ValueError, AttributeError) as e:
            _log.info("❌ [{self.agent_id}] Error calling LLM: {e}")
            return {"status": "ERROR", "error": str(e), "worker_type": "InternalLlmWorker"}

    def shutdown(self) -> None:
        """Override shutdown to cleanup registry"""
        self._unregister_from_registry()
        super().shutdown()


if __name__ == "__main__":
    worker = InternalLlmWorker(
        agent_id="internal_llm_01",
        persona="You are a helpful internal AI assistant.",
        capabilities=["text.process", "code.review"],
    )
    _log.info("🚀 Starting InternalLlmWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
    finally:
        worker.shutdown()
