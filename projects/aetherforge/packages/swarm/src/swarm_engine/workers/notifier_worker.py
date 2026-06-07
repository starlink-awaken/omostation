from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from ._compat import (
    AgentDaemonBase,
    ISynapseWorker,
    MessageEnvelope,
    Receipt,
    SynapseAgentCard,
)

"""
---
Type: Worker
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: "Notifier Worker for Passive/Output scenarios (e.g., Slack, Discord)"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Notifier Worker ≡ Worker
# 内涵 ≝ {Notifier, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, NotifierWorker)}
# 功能 ⊢ {Notifier_Worker, Init_Notifier, Validate_Worker}
# =============================================================================

_log = logging.getLogger(__name__)


class NotifierWorker(AgentDaemonBase, ISynapseWorker):
    def __init__(self, agent_id: str, persona: str, capabilities: list[str], webhook_url: str | None = None) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=10.0,
            poll_interval=2.0,
        )
        self.webhook_url = webhook_url

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(
            capabilities=self.capabilities,
            cost_class="low",
            mode="passive",  # Passive because it mainly receives commands to output
            max_eu_budget=10.0,
        )

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
            "remaining_eu": getattr(self, "current_eu", 100.0),
            "webhook_configured": bool(self.webhook_url),
        }

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process task: Send a notification.
        """
        _log.info("📢 [{self.agent_id}] Processing notification task...")

        message = task_payload.get("message")
        if not message:
            return {
                "status": "ERROR",
                "error": "No message provided in task payload.",
                "worker_type": "NotifierWorker",
            }

        # If no webhook is configured, just print to console (mock mode)
        if not self.webhook_url:
            _log.info("🔔 [MOCK NOTIFICATION]: {message}")
            return {
                "status": "SUCCESS",
                "result": "Message logged to console (Mock Mode).",
                "worker_type": "NotifierWorker",
            }

        # Send to actual webhook (e.g., Slack/Discord)
        try:
            data = json.dumps({"text": message}).encode("utf-8")
            req = urllib.request.Request(  # noqa: S310
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "B-OS NotifierWorker"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:  # noqa: S310
                if response.status in [200, 204]:
                    return {
                        "status": "SUCCESS",
                        "result": "Notification sent successfully.",
                        "worker_type": "NotifierWorker",
                    }
                else:
                    return {
                        "status": "ERROR",
                        "error": f"Webhook returned status {response.status}",
                        "worker_type": "NotifierWorker",
                    }
        except urllib.error.URLError as e:
            _log.info("❌ [{self.agent_id}] Error sending notification: {e}")
            return {"status": "ERROR", "error": str(e), "worker_type": "NotifierWorker"}
        except (OSError, ValueError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {
                "status": "ERROR",
                "error": f"Unexpected error: {e!s}",
                "worker_type": "NotifierWorker",
            }

    def _execute_task_in_sandbox(
        self, payload: dict[str, Any], msg_id: str, summary: str
    ) -> tuple[dict[str, Any], float]:
        """Override to bypass file sandbox for notifier."""
        import time

        start_t = time.time()
        result = self.process_task(payload)
        return result, (time.time() - start_t) * 1000


if __name__ == "__main__":
    worker = NotifierWorker(
        agent_id="notifier_slack_01",
        persona="You are a system notification agent.",
        capabilities=["notify.slack", "notify.discord"],
        webhook_url=None,  # Set to actual URL for real usage
    )
    _log.info("🚀 Starting NotifierWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
