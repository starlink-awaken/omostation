from __future__ import annotations

import json
import logging
import threading
import time
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
Summary: "GitHub Monitor Sensor Worker for Event-driven scenarios"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Github Sensor Worker ≡ Worker
# 内涵 ≝ {Github, Sensor, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, GithubSensorWorker)}
# 功能 ⊢ {Github_Sensor, Sensor_Worker, Worker_Init}
# =============================================================================

_log = logging.getLogger(__name__)


class GitHubSensorWorker(AgentDaemonBase, ISynapseWorker):
    def __init__(
        self,
        agent_id: str,
        persona: str,
        capabilities: list[str],
        repo: str,
        token: str | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=15.0,
            poll_interval=5.0,
        )
        self.repo = repo
        self.token = token
        self._sensor_thread: threading.Thread | None = None
        self._last_checked_time = time.time()
        self._seen_events: set[str] = set()

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(capabilities=self.capabilities, cost_class="low", mode="active", max_eu_budget=20.0)

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
            "repo_watched": self.repo,
        }

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """Process incoming configuration tasks (e.g., change repo)."""
        if "repo" in task_payload:
            self.repo = task_payload["repo"]
            return {
                "status": "SUCCESS",
                "result": f"Now watching {self.repo}",
                "worker_type": "GitHubSensorWorker",
            }
        return {
            "status": "SUCCESS",
            "result": "Config updated.",
            "worker_type": "GitHubSensorWorker",
        }

    def _fetch_github_events(self) -> list[dict[str, Any]]:
        url = f"https://api.github.com/repos/{self.repo}/events"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    return data
        except urllib.error.URLError:
            _log.info("⚠️ [{self.agent_id}] GitHub API Error: {e}")
        return []

    def _sensor_loop(self) -> None:
        """Background loop to monitor GitHub events."""
        _log.info("👁️ [{self.agent_id}] Monitoring GitHub Repo: {self.repo}")

        while self.running:
            try:
                events = self._fetch_github_events()
                for event in events:
                    event_id = event.get("id")
                    if event_id and event_id not in self._seen_events:
                        self._seen_events.add(event_id)

                        # Only process new events (simple heuristic)
                        # created_at = event.get("created_at")

                        event_type = event.get("type")
                        if event_type in ["PushEvent", "PullRequestEvent", "IssuesEvent"]:
                            _log.info(f"🚨 [{self.agent_id}] Detected GitHub Event: {event_type} on {self.repo}")

                            # Emit EVENT to the Orchestrator
                            envelope = MessageEnvelope(
                                source=self.agent_id,
                                target="Orchestrator",
                                type="EVENT",
                                payload={
                                    "event_type": f"github_{event_type.lower()}",
                                    "repo": self.repo,
                                    "actor": event.get("actor", {}).get("login"),
                                    "details": event.get("payload", {}),
                                },
                                eu_budget=5.0,
                            )
                            self._mcp_send_envelope(envelope)

                # Keep seen events set manageable
                if len(self._seen_events) > 1000:
                    self._seen_events.clear()

            except (TypeError, ValueError, AttributeError):
                _log.info("❌ [{self.agent_id}] Sensor error: {e}")

            time.sleep(60.0)  # Poll every 60 seconds to avoid rate limits

    def run(self) -> None:
        self.running = True
        self._sensor_thread = threading.Thread(target=self._sensor_loop, daemon=True)
        self._sensor_thread.start()
        super().run()


if __name__ == "__main__":
    worker = GitHubSensorWorker(
        agent_id="github_sensor_01",
        persona="You are a GitHub event monitor.",
        capabilities=["sensor.github"],
        repo="octocat/Hello-World",  # Example repo
    )
    _log.info("🚀 Starting GitHubSensorWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
