from __future__ import annotations

import os

from ._compat import (
    ISynapseWorker,
    MessageEnvelope,
    Receipt,
    SynapseAgentCard,
    get_synapse_registry,
)

BOS_ROOT = os.environ.get("BOS_ROOT", ".")
import logging
import os
import threading
import time
from typing import Any

from .agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]

"""
---
Type: Worker
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: "Sensor Adapter Worker implementing Universal Synapse Architecture"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Sensor Worker ≡ Worker
# 内涵 ≝ {Sensor, Worker}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, SensorWorker)}
# 功能 ⊢ {Sensor_Worker, Init_Sensor, Validate_Worker}
# =============================================================================

_log = logging.getLogger(__name__)
HAS_SYNAPSE_REGISTRY = True


class SensorWorker(AgentDaemonBase, ISynapseWorker):
    def __init__(self, agent_id: str, persona: str, capabilities: list[str], watch_dir: str) -> None:
        super().__init__(
            agent_id=agent_id,
            persona=persona,
            capabilities=capabilities,
            heartbeat_interval=10.0,
            poll_interval=2.0,
        )
        self.watch_dir = watch_dir
        self._sensor_thread: threading.Thread | None = None
        self._processed_files: set[str] = set()
        self.synapse_id = None

        # Register with SynapseRegistry
        self._register_with_registry()

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard(capabilities=self.capabilities, cost_class="low", mode="active", max_eu_budget=10.0)

    def accept(self, envelope: MessageEnvelope) -> Receipt:
        # Sensor workers usually don't accept tasks, but they can accept configuration updates
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
            "watched_files": len(self._processed_files),
        }

    def process_task(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """Process incoming configuration tasks."""
        return {
            "status": "SUCCESS",
            "result": "Sensor configuration updated.",
            "worker_type": "SensorWorker",
        }

    def _sensor_loop(self) -> None:
        """Background loop to monitor the watch_dir for new files."""
        _log.info("👁️ [{self.agent_id}] Monitoring directory: {self.watch_dir}")
        os.makedirs(self.watch_dir, exist_ok=True)

        while self.running:
            try:
                for filename in os.listdir(self.watch_dir):
                    if filename not in self._processed_files:
                        filepath = os.path.join(self.watch_dir, filename)
                        if os.path.isfile(filepath):
                            _log.info("🚨 [{self.agent_id}] Detected new file: {filename}")

                            # Read content
                            with open(filepath) as f:
                                content = f.read()

                            # Emit EVENT to the Orchestrator
                            envelope = MessageEnvelope(
                                source=self.agent_id,
                                target="Orchestrator",
                                type="EVENT",
                                payload={
                                    "event_type": "file_created",
                                    "filename": filename,
                                    "content": content,
                                },
                                eu_budget=5.0,
                            )
                            self._mcp_send_envelope(envelope)
                            self._processed_files.add(filename)

            except (TypeError, ValueError, AttributeError):
                _log.info("❌ [{self.agent_id}] Sensor error: {e}")

            time.sleep(2.0)

    def _register_with_registry(self) -> None:
        """Register with SynapseRegistry for dynamic discovery"""
        if not HAS_SYNAPSE_REGISTRY:
            return
        try:
            registry = get_synapse_registry()
            self.synapse_id = registry.register(self)
            _log.info("✅ SensorWorker registered with SynapseRegistry: {self.synapse_id}")
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
            _log.info("✅ SensorWorker unregistered from SynapseRegistry")
        except (TypeError, ValueError, AttributeError):
            _log.info("⚠️ Failed to unregister from SynapseRegistry: {e}")

    def run(self) -> None:
        """Override run to start the sensor loop."""
        threading.Thread(target=self._sensor_loop, daemon=True).start()
        self.running = True
        super().run()

    def shutdown(self) -> None:
        """Override shutdown to cleanup registry"""
        self._unregister_from_registry()
        super().shutdown()


if __name__ == "__main__":
    watch_dir = os.path.join(BOS_ROOT, "tmp", "sensor_watch")
    worker = SensorWorker(
        agent_id="sensor_fs_01",
        persona="You are a file system sensor.",
        capabilities=["sensor.fs"],
        watch_dir=watch_dir,
    )
    _log.info("🚀 Starting SensorWorker: {worker.agent_id}")
    try:
        worker.run()
    except KeyboardInterrupt:
        _log.info("\nWorker stopped.")
    finally:
        worker.shutdown()
