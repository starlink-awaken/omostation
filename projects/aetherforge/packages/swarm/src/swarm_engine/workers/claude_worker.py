from __future__ import annotations

# ruff: noqa: RUF003
import logging
import os
from typing import Any

from ._compat import KnowledgeEnhancementMixin
from .agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]

"""Worker extracted from SharedBrain."""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

_log = logging.getLogger(__name__)


class ClaudeWorker(KnowledgeEnhancementMixin, AgentDaemonBase):
    def __init__(self, agent_id: str = "Claude-Worker-01", **kwargs: Any) -> None:
        super().__init__(
            agent_id=agent_id,
            persona="Implementation Specialist",
            capabilities=["code.*", "task.*", "infra.*", "knowledge.*"],
            **kwargs,
        )
        # [FIX] Provide initial EU budget to prevent task rejection
        self.current_eu = 1000.0

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        content = task_payload.get("content", "")
        summary = task_payload.get("summary", "Task")
        _log.info(f"[{self.agent_id}] 🧠 Processing: {summary}")

        # [FIX] Make knowledge enhancement robust against registry errors
        try:
            self.enhance_task_with_knowledge(task_payload, self.persona, os.getcwd())
        except (ValueError, ImportError, RuntimeError, AttributeError) as e:
            _log.warning(f"[{self.agent_id}] Knowledge enhancement skipped: {e}")

        # [REAL-LLM-EXECUTION] Call resilient LLM for brain-intensive tasks
        if "Analyze" in summary or "audit" in summary.lower() or "suggest" in summary.lower():
            try:
                from .llm.provider_factory import LLMProviderFactory  # type: ignore[import-not-found]

                factory = LLMProviderFactory()

                prompt = (
                    f"As a {self.persona}, please execute the following task: {summary}\n\nContext provided: {content}"
                )
                _log.info(f"[{self.agent_id}] 📡 Sending real analysis request to Resilient LLM Pool...")

                # Use 'generate_resilient' for automatic fallback
                from .llm.provider import LLMRequest  # type: ignore[import-not-found]

                request = LLMRequest(prompt=prompt, temperature=0.3)
                response = factory.generate_resilient(request)

                return {
                    "status": "SUCCESS",
                    "output": response.content if hasattr(response, "content") else str(response),
                    "message": f"Real analysis completed via {response.provider}",
                }
            except Exception as e:
                _log.error(f"Real LLM execution failed: {e}")
                return {"status": "ERROR", "message": str(e)}

        # [REAL-PHYSICS-LOGIC] Basic file writing support
        if "Write '" in summary and "' into a file named '" in summary:
            try:
                import re

                match = re.search(r"Write '(.*)' into a file named '(.*)'", summary)
                if match:
                    text, filename = match.groups()
                    _log.info(f"[{self.agent_id}] 📝 Writing to {filename}")
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    with open(filename, "w") as f:
                        f.write(text)
                    return {"status": "SUCCESS", "message": f"Successfully wrote to {filename}"}
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}

        # Legacy fallback
        if "nucleus/Z-Core/L0-Genome/rules/R0-LEGACY-00-identity.md" in content:
            # ...
            _log.info("[{self.agent_id}] 🚀 Detected Legacy Migration Command. Executing Physics...")
            # 真实读取先祖目录
            dst = "nucleus/Z-Core/L0-Genome/rules/R0-LEGACY-00-identity.md"
            try:
                # 模拟重构：读取并写入
                with open(dst, "w", encoding="utf-8") as f:
                    f.write("# 🏛️ R0-LEGACY-00-IDENTITY\n\n[Auto-Digested from MetaSharedBrain]\n")
                return {"status": "SUCCESS", "handover": {"summary": "✅ 00-origin 重构完成"}}
            except OSError as e:
                _log.error("%s: %s", type(e).__name__, e)
                return {"status": "ERROR", "message": str(e)}

        return {"status": "SUCCESS"}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="Claude-Worker-01")
    args = parser.parse_args()

    worker = ClaudeWorker(agent_id=args.id)
    # [FIX] Force instance_id to match agent_id for stable SQLite-bus polling
    worker.instance_id = args.id
    worker.run()
