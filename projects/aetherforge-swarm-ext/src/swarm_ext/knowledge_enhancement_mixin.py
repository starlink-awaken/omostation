from __future__ import annotations

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
# Knowledge Enhancement Mixin ≡ Module
# 内涵 ≝ {Knowledge, Enhancement, Mixin}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, KnowledgeEnhancementMixin)}
# 功能 ⊢ {Knowledge_Enhancement, Enhancement_Mixin, Mixin_Init}
# =============================================================================

"""
---
Type: Mixin
Status: ACTIVE
Version: 1.0.0
Owner: "@Prime"
Layer: L3
Summary: "SharedBrain Knowledge Enhancement Mixin — Eliminates 350+ lines of duplication across 5 workers"
Tags:
  - knowledge
  - injection
  - mixin
  - DRY
Authority: organs/D-Execution/organs/engine/knowledge_enhancement_mixin.py
---

Knowledge Enhancement Mixin for SharedBrain Workers
====================================================

This mixin provides a unified implementation for FactGraph knowledge injection,
eliminating ~350 lines of duplicated code across 5 worker files:
- claude_worker.py
- copilot_worker.py
- gemini_worker.py
- internal_llm_worker.py
- cli_avatar_worker.py

Usage:
    class MyWorker(AgentDaemonBase, KnowledgeEnhancementMixin):
        def process_task(self, task_payload):
            self.enhance_task_with_knowledge(task_payload, self.persona, os.getcwd())
            # Continue with enhanced task_payload...
"""


import asyncio
import logging
from typing import Any

# Import ContextInjector for basic Holo-Context generation
# Note: Using __import__ to handle module names with hyphens
try:
    ContextInjector = __import__(
        "organs.D_Execution.organs.engine.context_injector",
        fromlist=["ContextInjector"],
    ).ContextInjector
    HAS_CONTEXT_INJECTOR = True
except (ImportError, ModuleNotFoundError, AttributeError):
    ContextInjector = None  # type: ignore[assignment]
    HAS_CONTEXT_INJECTOR = False

# Import HarvestContextInjector for knowledge retrieval from FactGraph
get_harvest_context_injector = None
HAS_HARVEST_INJECTOR = False
try:
    _module = __import__(
        "organs.D_KnowledgeIntegration.services.context_injector",
        fromlist=["get_context_injector"],
    )
    get_harvest_context_injector = _module.get_context_injector
    HAS_HARVEST_INJECTOR = True
except (ImportError, ModuleNotFoundError, AttributeError):
    HAS_HARVEST_INJECTOR = False

_log = logging.getLogger(__name__)


class KnowledgeEnhancementMixin:
    """
    Mixin for workers to add FactGraph knowledge enhancement.

    This mixin provides a single method `enhance_task_with_knowledge()` that:
    1. Attempts to inject knowledge from FactGraph via HarvestContextInjector
    2. Falls back to basic ContextInjector if FactGraph unavailable
    3. Handles all error cases gracefully with appropriate logging

    This eliminates ~70 lines of duplicated code per worker.
    """

    def enhance_task_with_knowledge(
        self,
        task_payload: dict[str, Any],
        persona: str,
        workspace_path: str,
        agent_id: str | None = None,
    ) -> None:
        """
        Enhance task payload with knowledge from FactGraph.

        Modifies task_payload in-place by adding '_enhanced_prompt' key.

        Args:
            task_payload: Task dictionary to enhance
            persona: Worker persona string for prompt generation
            workspace_path: Current working directory path
            agent_id: Optional agent ID for logging (defaults to self.agent_id if available)

        Raises:
            No exceptions - all errors are caught and logged, with fallback to basic prompt
        """
        if agent_id is None and hasattr(self, "agent_id"):
            agent_id = self.agent_id  # type: ignore[attr-defined]
        elif agent_id is None:
            agent_id = "Worker"

        summary = task_payload.get("summary", "Task")
        content = task_payload.get("content", "")

        # Try Enhanced Context Injector with FactGraph knowledge
        if HAS_HARVEST_INJECTOR and get_harvest_context_injector is not None:
            try:
                harvest_injector = get_harvest_context_injector()
                if harvest_injector is not None:
                    knowledge_query = summary + " " + (content[:200] if content else "")

                    # Check if we're in an async context
                    try:
                        asyncio.get_running_loop()
                        # Already in async context - cannot use asyncio.run()
                        # Synchronous context injection is NOT possible with async functions
                        # Fall back to basic ContextInjector instead
                        if HAS_CONTEXT_INJECTOR and ContextInjector is not None:
                            try:
                                basic_prompt = ContextInjector.generate_hifi_prompt(
                                    persona, task_payload, workspace_path
                                )
                                task_payload["_enhanced_prompt"] = basic_prompt
                                _log.info(f"[{agent_id}] Using basic ContextInjector (async context limitation)")
                            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                                _log.warning(f"[{agent_id}] ContextInjector failed: {exc}")
                        else:
                            _log.warning(
                                f"[{agent_id}] In async context but no ContextInjector available - skipping knowledge enhancement"
                            )
                    except RuntimeError:
                        # No running event loop, use asyncio.run()
                        enhanced_prompt = asyncio.run(
                            harvest_injector.inject_harvest_context(
                                persona=persona,
                                task_msg=task_payload,
                                workspace_path=workspace_path,
                                knowledge_query=knowledge_query,
                            )
                        )
                        task_payload["_enhanced_prompt"] = enhanced_prompt

                    _log.info(f"[{agent_id}] Using EnhancedContextInjector with FactGraph knowledge")
                    return
                else:
                    raise RuntimeError("get_harvest_context_injector returned None")

            except (ImportError, AttributeError, RuntimeError, OSError, ValueError) as exc:
                _log.warning(f"[{agent_id}] HarvestContextInjector failed, using basic prompt: {exc}")
                # Fall through to basic ContextInjector

        # Fallback: Basic Context Injector
        if HAS_CONTEXT_INJECTOR and ContextInjector is not None:
            try:
                basic_prompt = ContextInjector.generate_hifi_prompt(persona, task_payload, workspace_path)
                task_payload["_enhanced_prompt"] = basic_prompt
                _log.info(f"[{agent_id}] Using basic ContextInjector")
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                _log.warning(f"[{agent_id}] Basic context injection failed: {exc}")

    async def _async_enhancement_wrapper(
        self,
        injector: Any,
        task_payload: dict[str, Any],
        persona: str,
        workspace_path: str,
        knowledge_query: str,
        agent_id: str | None,
    ) -> None:
        """Wrapper for async enhancement in existing event loop."""
        # Ensure agent_id is never None for logging
        if agent_id is None:
            agent_id = "Worker"
        try:
            enhanced_prompt = await injector.inject_harvest_context(
                persona=persona,
                task_msg=task_payload,
                workspace_path=workspace_path,
                knowledge_query=knowledge_query,
            )
            task_payload["_enhanced_prompt"] = enhanced_prompt
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _log.warning(f"[{agent_id}] Async enhancement failed: {exc}")
