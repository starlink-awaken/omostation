from __future__ import annotations

import logging
import os
from typing import Any

from ._compat import AgentDaemonBase, KnowledgeEnhancementMixin

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/gemini_worker.py'
Tags:
- auto-metadata
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-GN01-01_differentiation_protocol.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

_log = logging.getLogger(__name__)


class GeminiWorker(KnowledgeEnhancementMixin, AgentDaemonBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_id="Gemini-Worker", persona="Orchestrator", capabilities=["reasoning.*"], **kwargs)

    def process_task(self, task_payload: dict) -> dict:
        """Process task with EnhancedContextInjector integration for FactGraph knowledge retrieval."""
        summary = task_payload.get("summary", "Task")
        content = task_payload.get("content", "")
        _log.info(f"[{self.agent_id}] 🧠 Orchestrating: {summary}")

        # Enhanced context injection from FactGraph using KnowledgeEnhancementMixin
        self.enhance_task_with_knowledge(task_payload, self.persona, os.getcwd())

        # Get the enhanced prompt or fallback to content/summary
        task_prompt = task_payload.get("_enhanced_prompt") or (content or summary)

        # Write proof file with enhanced prompt
        with open("support/trash/proof/Gemini.txt", "w") as f:
            f.write(f"I am Gemini-Worker. PID: {os.getpid()}\nTask: {summary}\n\nPrompt:\n{task_prompt}")
        return {"status": "SUCCESS"}


if __name__ == "__main__":
    GeminiWorker().run()
