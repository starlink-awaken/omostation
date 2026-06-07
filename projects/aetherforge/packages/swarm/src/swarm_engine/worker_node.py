from __future__ import annotations

# ruff: noqa: RUF001, RUF002

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
Layer: L3
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 2.0.0
Owner: '@Kiro'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-ST01-01_architecture_standard.md
Layer: L3-Execution
Created: 2026-02-18
Updated: 2026-03-07
Constraint: "[!!] STATE_MACHINE_COMPLIANCE | [!!] SWARM_LIFECYCLE_INTEGRATION"
Summary: Worker 节点 — 状态机管理（IDLE/BUSY/DRAINING/DEAD）、任务执行、生命周期控制、Swarm 集成
Tags:
  - infrastructure
  - worker-node
  - state-machine
  - task-execution
  - lifecycle
  - swarm
---

🧑‍💻 Worker 节点 (Worker Node)

目的: Worker 节点的完整实现，支持状态管理、任务执行和 Swarm 生命周期集成
状态: IDLE → BUSY → DRAINING → DEAD
集成: SwarmLifecycleManager (可选)
"""

import json
import logging
import threading
import time
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)

# Soft import — graceful if SwarmLifecycleManager is not available
try:
    from .organs.swarm_lifecycle_manager import SwarmLifecycleManager  # type: ignore[import-not-found]

    _HAS_SLM = True
except ImportError:
    _HAS_SLM = False
    SwarmLifecycleManager = None  # type: ignore[assignment,misc]


class WorkerState(StrEnum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    DEAD = "DEAD"


class WorkerNode:
    """
    Production-ready Worker node for the B-OS Swarm Task system.

    Lifecycle: IDLE → BUSY → DRAINING → DEAD
    Capabilities are declared at init time and can be overridden via
    differentiate() when the LifeCompiler compiles a spore template.
    """

    # Differentiated by LifeCompiler
    DEFAULT_CAPABILITIES: list[str] = ["generic", "task_execution"]  # noqa: RUF012
    MAX_CONCURRENT: int = 3

    def __init__(
        self,
        node_id: str,
        capabilities: list[str] | None = None,
        spore_template: str | None = None,
    ) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.node_id = node_id
        self._state: WorkerState = WorkerState.DEAD
        self._active_tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._heartbeat_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Metrics
        self._completed_tasks: int = 0
        self._rejected_tasks: int = 0

        # Capability initialisation
        if spore_template is not None:
            self._load_spore_template(spore_template)
            if capabilities:
                self.capabilities: list[str] = capabilities
        else:
            default_caps = list(self.DEFAULT_CAPABILITIES)
            self.capabilities = list(capabilities) if capabilities else default_caps
            self.persona: str = "default"

        _log.debug("[WorkerNode:%s] Initialized with capabilities=%s", node_id, self.capabilities)

        # Register with SwarmLifecycleManager (soft, non-blocking)
        if _HAS_SLM and SwarmLifecycleManager is not None:
            try:
                SwarmLifecycleManager.register(self)  # type: ignore[attr-defined]
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                _log.debug("[WorkerNode:%s] SLM registration skipped: %s", node_id, exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_spore_template(self, spore_template: str) -> None:
        """Load capability profile from a JSON spore template string or file path."""
        data: dict[str, Any] = {}
        try:
            # Try JSON string first
            data = json.loads(spore_template)
        except (json.JSONDecodeError, TypeError):
            # Fall back to file path
            try:
                with open(spore_template) as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning("[WorkerNode:%s] Could not load spore_template: %s", self.node_id, exc)
                data = {}

        self.capabilities = data.get("capabilities", list(self.DEFAULT_CAPABILITIES))
        self.persona = data.get("persona", "default")

    def _heartbeat_loop(self, interval: float = 5.0) -> None:
        while not self._stop_event.is_set():
            hb = self.heartbeat()
            _log.debug("[WorkerNode:%s] heartbeat %s", self.node_id, hb)
            self._stop_event.wait(interval)

    # ------------------------------------------------------------------
    # Capability declarations
    # ------------------------------------------------------------------

    def declare_capabilities(self) -> dict[str, list[str]]:
        """Return mapping of node_id → capabilities."""
        return {self.node_id: list(self.capabilities)}

    def can_handle(self, capability_hint: str) -> bool:
        """Fuzzy-match capability_hint against declared capabilities."""
        hint_lower = capability_hint.lower()
        for cap in self.capabilities:
            if hint_lower in cap.lower() or cap.lower() in hint_lower:
                return True
        return False

    def get_load_score(self) -> float:
        """Return load score 0.0 (idle) – 1.0 (fully saturated)."""
        with self._lock:
            active = len(self._active_tasks)
        return min(1.0, active / self.MAX_CONCURRENT)

    # ------------------------------------------------------------------
    # Task assignment pipeline
    # ------------------------------------------------------------------

    def assign_task(self, task_envelope: dict[str, Any]) -> dict[str, Any]:
        """
        Attempt to assign a task to this node.

        Returns:
            {"status": "ACCEPTED"|"REJECTED", "reason": str}
        """
        task_id = task_envelope.get("task_id", "unknown")
        required_cap = task_envelope.get("capability", "")

        with self._lock:
            if self._state in (WorkerState.DRAINING, WorkerState.DEAD):
                self._rejected_tasks += 1
                return {"status": "REJECTED", "reason": f"Node is {self._state.value}"}

            if len(self._active_tasks) >= self.MAX_CONCURRENT:
                self._rejected_tasks += 1
                return {
                    "status": "REJECTED",
                    "reason": f"Capacity full ({self.MAX_CONCURRENT} concurrent tasks)",
                }

            if required_cap and not self.can_handle(required_cap):
                self._rejected_tasks += 1
                return {
                    "status": "REJECTED",
                    "reason": f"Capability '{required_cap}' not supported",
                }

            self._active_tasks[task_id] = task_envelope
            self._state = WorkerState.BUSY
            _log.info("[WorkerNode:%s] Accepted task %s", self.node_id, task_id)
            return {"status": "ACCEPTED", "reason": "Task accepted"}

    def complete_task(self, task_id: str, result: dict[str, Any]) -> None:
        """Mark a task as complete, update metrics, and possibly return to IDLE."""
        with self._lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
                self._completed_tasks += 1
                _log.info("[WorkerNode:%s] Completed task %s", self.node_id, task_id)
            else:
                _log.warning(
                    "[WorkerNode:%s] complete_task called for unknown task %s",
                    self.node_id,
                    task_id,
                )

            if not self._active_tasks and self._state == WorkerState.BUSY:
                self._state = WorkerState.IDLE

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Set state to IDLE and start heartbeat thread."""
        with self._lock:
            if self._state == WorkerState.DEAD:
                self._stop_event.clear()
                self._state = WorkerState.IDLE
                self._heartbeat_thread = threading.Thread(
                    target=self._heartbeat_loop,
                    daemon=True,
                    name=f"heartbeat-{self.node_id}",
                )
                self._heartbeat_thread.start()
                _log.info("[WorkerNode:%s] Started", self.node_id)

    def stop(self) -> None:
        """Gracefully drain active tasks, then set state to DEAD."""
        with self._lock:
            self._state = WorkerState.DRAINING

        # Wait for active tasks to finish (up to 30 s)
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            with self._lock:
                if not self._active_tasks:
                    break
            time.sleep(0.1)

        with self._lock:
            self._state = WorkerState.DEAD

        self._stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        _log.info("[WorkerNode:%s] Stopped", self.node_id)

    def heartbeat(self) -> dict[str, Any]:
        """Return current node health snapshot."""
        with self._lock:
            return {
                "node_id": self.node_id,
                "state": self._state.value,
                "active_tasks": list(self._active_tasks.keys()),
                "capabilities": list(self.capabilities),
                "timestamp": time.time(),
            }

    # ------------------------------------------------------------------
    # Differentiation by LifeCompiler
    # ------------------------------------------------------------------

    def differentiate(self, spore_dna: dict[str, Any]) -> None:
        """
        Apply DNA overrides to capabilities and persona.
        Called by LifeCompiler during spore differentiation.
        """
        with self._lock:
            if "capabilities" in spore_dna:
                self.capabilities = list(spore_dna["capabilities"])
            if "persona" in spore_dna:
                self.persona = spore_dna["persona"]
        _log.info(
            "[WorkerNode:%s] Differentiated → capabilities=%s persona=%s",
            self.node_id,
            self.capabilities,
            self.persona,
        )


# ---------------------------------------------------------------------------
# Legacy alias so existing code that references Worker_node still imports OK
# ---------------------------------------------------------------------------
Worker_node = WorkerNode
