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
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/copilot_worker.py'
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


class CopilotWorker(KnowledgeEnhancementMixin, AgentDaemonBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_id="Copilot", persona="Auditor", capabilities=["audit.*"], **kwargs)

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        summary = task_payload.get("summary", "Task")
        _log.info(f"[{self.agent_id}] 🧠 Auditing: {summary}")

        # Enhanced context injection from FactGraph using KnowledgeEnhancementMixin
        self.enhance_task_with_knowledge(task_payload, self.persona, os.getcwd())

        with open("support/trash/proof/Copilot.txt", "w", encoding="utf-8") as f:
            f.write(f"I am Copilot. PID: {os.getpid()}\nTask: {summary}")
        return {"status": "SUCCESS"}


if __name__ == "__main__":
    CopilotWorker().run()
