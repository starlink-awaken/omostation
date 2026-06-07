from __future__ import annotations

import logging
import urllib.error
import urllib.request
from typing import Any

from ._compat import ISynapseWorker, MessageEnvelope, Receipt, SynapseAgentCard
from .agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]

"""
---
Type: Worker
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: "Web Scraper Worker for active execution scenarios"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Web Scraper Worker ≡ Worker
# 内涵 ≝ {Web, Scraper, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, WebScraperWorker)}
# 功能 ⊢ {Web_Scraper, Scraper_Worker, Worker_Init}
# =============================================================================

_log = logging.getLogger(__name__)


class WebScraperWorker(AgentDaemonBase, ISynapseWorker):
    def __init__(self, agent_id: str, persona: str, capabilities: list[str]) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=10.0,
            poll_interval=2.0,
        )

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(capabilities=self.capabilities, cost_class="medium", mode="active", max_eu_budget=50.0)

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
        }

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process task: Fetch content from a URL.
        """
        _log.info("🕸️ [{self.agent_id}] Processing scraping task...")

        url = task_payload.get("url")
        if not url:
            return {
                "status": "ERROR",
                "error": "No URL provided in task payload.",
                "worker_type": "WebScraperWorker",
            }

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (B-OS WebScraperWorker)"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=15) as response:  # noqa: S310
                content = response.read().decode("utf-8")

                # Basic extraction: just return the first 1000 chars for safety
                extracted = content[:1000] + ("..." if len(content) > 1000 else "")

                return {
                    "status": "SUCCESS",
                    "result": {"url": url, "content_length": len(content), "snippet": extracted},
                    "worker_type": "WebScraperWorker",
                    "handover": {"content": extracted, "summary": f"Scraped {url}"},
                }
        except urllib.error.URLError as e:
            _log.info("❌ [{self.agent_id}] Error scraping {url}: {e}")
            return {"status": "ERROR", "error": str(e), "worker_type": "WebScraperWorker"}
        except OSError as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {
                "status": "ERROR",
                "error": f"Unexpected error: {e!s}",
                "worker_type": "WebScraperWorker",
            }

    def _execute_task_in_sandbox(
        self,
        payload: dict[str, Any],
        msg_id: str,
        summary: str,
    ) -> tuple[dict[str, Any], float]:
        """Override to bypass file sandbox for web scraper."""
        import time

        start_t = time.time()
        result = self.process_task(payload)
        return result, (time.time() - start_t) * 1000


if __name__ == "__main__":
    worker = WebScraperWorker(
        agent_id="web_scraper_01",
        persona="You are a web scraping agent.",
        capabilities=["web.scrape", "data.extract"],
    )
    _log.info("🚀 Starting WebScraperWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
