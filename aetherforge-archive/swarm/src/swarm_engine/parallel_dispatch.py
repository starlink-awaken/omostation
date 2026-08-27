"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: ParallelDispatch — Parallel-Probe worker batch spawning with ConsensusMonitor wiring.
  Extracted from SwarmLifecycleManager.dispatch_parallel() and _ensure_consensus_monitor().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md

Responsibility: Single — spawn parallel worker batches and wire ConsensusMonitor
for early stopping. Does NOT handle individual worker lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from ._compat import WorkerHandle

_log = logging.getLogger(__name__)


class ParallelDispatch:
    """
    Parallel-Probe dispatch with consensus-based early stopping.

    Responsibility: Single — spawn a batch of workers from multiple capabilities
    and wire a ConsensusMonitor for early termination when a majority agrees.
    Based on Parallel-Probe (arXiv:2602.03845).
    """

    def __init__(
        self,
        *,
        spawn_fn: Callable[..., WorkerHandle],  # SwarmLifecycleManager.spawn
        ensure_consensus_monitor_fn: Callable[[], None],  # SwarmLifecycleManager._ensure_consensus_monitor
        get_consensus_monitor: Callable[[], Any | None],  # lambda returning _consensus_monitor
        events_emit: Callable[[str, dict[str, object]], None],  # SwarmEventEmitter.emit
    ) -> None:
        self._spawn = spawn_fn
        self._ensure_cm = ensure_consensus_monitor_fn
        self._get_cm = get_consensus_monitor
        self._emit = events_emit

    def dispatch(
        self,
        capabilities: list[str],
        task_prompt: str,
        eu_budget: float = 0.0,
        consensus_threshold: float = 0.5,
        soul_context: dict | None = None,
    ) -> list[WorkerHandle]:
        """Spawn a parallel batch and optionally wire ConsensusMonitor for early stopping."""
        if not capabilities:
            return []

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        handles: list[WorkerHandle] = []

        for cap in capabilities:
            try:
                handle = self._spawn(
                    capability=cap,
                    eu_budget=eu_budget,
                    task_prompt=task_prompt,
                    soul_context=soul_context,
                )
                handles.append(handle)
            except (OSError, ValueError, RuntimeError) as exc:
                _log.warning(
                    "[ParallelDispatch] spawn '%s' failed — %s",
                    cap,
                    exc,
                )

        if not handles:
            _log.warning("[ParallelDispatch] No workers spawned.")
            return handles

        # Wire ConsensusMonitor for early-stopping if available
        self._ensure_cm()
        monitor = self._get_cm()
        if monitor is not None:
            worker_ids = [h.worker_id for h in handles]
            try:
                monitor.create_group(
                    group_id=batch_id,
                    worker_ids=worker_ids,
                    threshold=consensus_threshold,
                )
                _log.info(
                    "[ParallelDispatch] Batch '%s' monitoring %d workers (threshold=%.2f).",
                    batch_id,
                    len(worker_ids),
                    consensus_threshold,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                _log.warning(
                    "[ParallelDispatch] ConsensusMonitor.create_group failed — %s",
                    exc,
                )
        else:
            _log.debug("[ParallelDispatch] ConsensusMonitor unavailable, running without early stopping.")

        self._emit(
            "dispatch.parallel.started",
            {"batch_id": batch_id, "worker_count": len(handles)},
        )
        return handles
