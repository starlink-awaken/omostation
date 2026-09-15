"""GC Engine core — mark-and-sweep with reference counting, incremental GC, and background scheduling."""

from __future__ import annotations

import statistics
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class GCStats:
    """Statistics for garbage collection runs.

    Attributes:
        entries_marked: Number of entries currently marked for collection.
        entries_swept: Total swept across all runs.
        last_run: ISO-format timestamp of the most recent sweep.
        objects_scanned: Total objects examined across all cycles.
        objects_collected: Total objects actually removed.
        time_taken: Duration of the last cycle in seconds.
        memory_freed: Estimated bytes freed across all cycles.
        total_cycles: Number of completed GC cycles.
        cycle_durations: Timings of the most recent cycles (up to 100).
        avg_cycle_ms: Mean cycle duration in milliseconds.
    """

    entries_marked: int = 0
    entries_swept: int = 0
    last_run: str | None = None
    objects_scanned: int = 0
    objects_collected: int = 0
    time_taken: float = 0.0
    memory_freed: int = 0
    total_cycles: int = 0
    cycle_durations: list[float] = field(default_factory=list)
    avg_cycle_ms: float = 0.0


class GCEngine:
    """Mark-and-sweep garbage collector with reference counting and incremental collection.

    Maintains backward compatibility with the original stub API (``mark``, ``sweep``,
    ``get_stats``) while adding full reference counting, incremental GC with
    configurable thresholds, and background scheduling via :meth:`schedule_gc`.

    Typical usage::

        engine = GCEngine()
        engine.incref("entry-a")
        engine.mark("entry-a", "obsolete")
        deleted = engine.sweep()
        print(engine.get_stats())
    """

    # Estimated average bytes per entry for memory-freed estimation.
    _ESTIMATED_BYTES_PER_ENTRY: int = 1024
    _MAX_CYCLE_HISTORY: int = 100

    def __init__(self, incremental_threshold: int = 1000, batch_size: int = 100) -> None:
        # --- Mark state ---
        self._marked: dict[str, str] = {}  # entry_id → reason
        # --- Reference counting ---
        self._ref_counts: dict[str, int] = {}  # entry_id → count
        self._ref_graph: dict[str, set[str]] = {}  # entry_id → {referents}
        # --- Sweep history ---
        self._swept_ids: set[str] = set()
        self._total_swept: int = 0
        self._last_run: str | None = None
        # --- Cumulative counters ---
        self._objects_scanned: int = 0
        self._objects_collected: int = 0
        self._memory_freed: int = 0
        self._total_cycles: int = 0
        self._cycle_durations: list[float] = []

        # --- Incremental GC ---
        self._incremental_batch_size: int = batch_size
        self._incremental_threshold: int = incremental_threshold
        self._incremental_phase: str = "idle"  # idle | marking | sweeping
        self._incremental_queue: list[str] = []  # entries pending sweep

        # --- Background scheduling ---
        self._scheduler_thread: threading.Thread | None = None
        self._scheduler_stop: threading.Event = threading.Event()
        self._scheduler_interval: float = 0
        self._scheduler_callback: Callable[[list[str]], None] | None = None
        self._lock: threading.RLock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API — Reference Counting
    # ------------------------------------------------------------------

    def incref(self, entry_id: str) -> int:
        """Increment the reference count for *entry_id*.

        Returns the new reference count.
        """
        with self._lock:
            current = self._ref_counts.get(entry_id, 0) + 1
            self._ref_counts[entry_id] = current
            return current

    def decref(self, entry_id: str) -> int:
        """Decrement the reference count for *entry_id*.

        If the count reaches zero, the entry is automatically marked for
        collection with reason ``"refcount_zero"``.

        Returns the new reference count (0 means marked).
        """
        with self._lock:
            current = self._ref_counts.get(entry_id, 0) - 1
            if current <= 0:
                self._ref_counts[entry_id] = 0
                self.mark(entry_id, "refcount_zero")
                return 0
            self._ref_counts[entry_id] = current
            return current

    def get_refcount(self, entry_id: str) -> int:
        """Return the current reference count for *entry_id*."""
        return self._ref_counts.get(entry_id, 0)

    def add_reference(self, source_id: str, target_id: str) -> None:
        """Record that *source_id* references *target_id*.

        Used by the mark phase to trace reachability.
        """
        with self._lock:
            self._ref_graph.setdefault(source_id, set()).add(target_id)

    def remove_reference(self, source_id: str, target_id: str) -> None:
        """Remove a recorded reference."""
        with self._lock:
            refs = self._ref_graph.get(source_id)
            if refs:
                refs.discard(target_id)
                if not refs:
                    del self._ref_graph[source_id]

    # ------------------------------------------------------------------
    # Public API — Mark & Sweep (original stub-compatible signatures)
    # ------------------------------------------------------------------

    def mark(self, entry_id: str, reason: str = "") -> None:
        """Mark an entry for collection.

        Args:
            entry_id: The identifier of the entry to mark.
            reason: An optional human-readable reason for collection.
        """
        with self._lock:
            self._marked[entry_id] = reason

    def sweep(self) -> list[str]:
        """Sweep all marked entries, removing them from the mark set.

        Before sweeping, the engine performs a full mark phase: entries that are
        marked but still referenced from a non-marked entry are un-marked (they
        are reachable).  The remaining marked entries are collected.

        Returns:
            The list of entry IDs that were deleted in this sweep.
        """
        start = time.monotonic()
        with self._lock:
            # Phase 1 — Mark: remove marks from entries still reachable from
            # non-marked roots.
            roots = set(self._ref_graph.keys()) - set(self._marked.keys())
            reachable: set[str] = set()
            _mark_reachable(self._ref_graph, roots, reachable)
            # Un-mark any entry that is reachable
            for rid in reachable:
                self._marked.pop(rid, None)

            self._objects_scanned += len(self._marked)
            swept = list(self._marked.keys())
            self._swept_ids.update(swept)
            self._total_swept += len(swept)
            self._objects_collected += len(swept)
            self._memory_freed += len(swept) * self._ESTIMATED_BYTES_PER_ENTRY

            # Clean up references for swept entries
            for eid in swept:
                self._ref_counts.pop(eid, None)
                self._ref_graph.pop(eid, None)
                # Remove back-references
                for source, targets in self._ref_graph.items():
                    targets.discard(eid)

            self._marked.clear()
            self._last_run = datetime.now(UTC).isoformat()
            elapsed = time.monotonic() - start
            self._total_cycles += 1
            self._cycle_durations.append(elapsed)
            if len(self._cycle_durations) > self._MAX_CYCLE_HISTORY:
                self._cycle_durations = self._cycle_durations[-self._MAX_CYCLE_HISTORY :]

        return swept

    def get_stats(self) -> GCStats:
        """Return current garbage-collection statistics.

        Returns:
            A :class:`GCStats` instance with the current counts and metadata.
        """
        with self._lock:
            deps = self._cycle_durations
            avg = (statistics.mean(deps) * 1000) if deps else 0.0
            return GCStats(
                entries_marked=len(self._marked),
                entries_swept=self._total_swept,
                last_run=self._last_run,
                objects_scanned=self._objects_scanned,
                objects_collected=self._objects_collected,
                time_taken=self._cycle_durations[-1] if self._cycle_durations else 0.0,
                memory_freed=self._memory_freed,
                total_cycles=self._total_cycles,
                cycle_durations=list(self._cycle_durations),
                avg_cycle_ms=round(avg, 3),
            )

    # ------------------------------------------------------------------
    # Public API — Incremental GC
    # ------------------------------------------------------------------

    def start_incremental_step(self) -> int:
        """Execute one batch of incremental mark-sweep.

        If the number of marked entries exceeds *incremental_threshold*, a
        partial sweep of *batch_size* entries is performed.  Otherwise the
        engine stays idle.

        Returns the number of entries collected in this step.
        """
        with self._lock:
            if len(self._marked) < self._incremental_threshold:
                return 0

            if self._incremental_phase == "idle":
                self._incremental_phase = "sweeping"
                self._incremental_queue = list(self._marked.keys())

            if self._incremental_phase == "sweeping":
                batch = self._incremental_queue[: self._incremental_batch_size]
                self._incremental_queue = self._incremental_queue[self._incremental_batch_size :]

                collected = 0
                for eid in batch:
                    if eid in self._marked:
                        _ = self._marked.pop(eid)
                        self._swept_ids.add(eid)
                        self._total_swept += 1
                        self._objects_collected += 1
                        self._memory_freed += self._ESTIMATED_BYTES_PER_ENTRY
                        self._ref_counts.pop(eid, None)
                        self._ref_graph.pop(eid, None)
                        # Remove back-references
                        for source, targets in self._ref_graph.items():
                            targets.discard(eid)
                        collected += 1

                if not self._incremental_queue:
                    self._incremental_phase = "idle"
                    self._last_run = datetime.now(UTC).isoformat()
                    self._total_cycles += 1

                self._objects_scanned += len(batch)
                return collected

            return 0

    def set_incremental_params(self, threshold: int | None = None, batch_size: int | None = None) -> None:
        """Update incremental GC parameters.

        Args:
            threshold: Minimum number of marked entries to trigger incremental sweep.
            batch_size: Maximum entries to collect per step.
        """
        with self._lock:
            if threshold is not None:
                self._incremental_threshold = threshold
            if batch_size is not None:
                self._incremental_batch_size = batch_size

    @property
    def incremental_phase(self) -> str:
        """Return the current incremental GC phase (idle/marking/sweeping)."""
        return self._incremental_phase

    # ------------------------------------------------------------------
    # Public API — Background Scheduling
    # ------------------------------------------------------------------

    def schedule_gc(
        self,
        interval_sec: float = 60.0,
        callback: Callable[[list[str]], None] | None = None,
    ) -> None:
        """Start a background daemon thread that runs ``sweep()`` every *interval_sec*.

        If a scheduler is already running it is stopped first.  An optional
        *callback* is invoked with the list of swept entry IDs after each cycle.

        Args:
            interval_sec: Seconds between automatic sweeps.
            callback: Optional callable invoked with swept IDs after each run.
        """
        self.stop_scheduler()
        self._scheduler_stop.clear()
        self._scheduler_interval = interval_sec
        self._scheduler_callback = callback

        def _worker() -> None:
            while not self._scheduler_stop.wait(timeout=self._scheduler_interval):
                collected = self.sweep()
                if self._scheduler_callback and collected:
                    self._scheduler_callback(collected)

        self._scheduler_thread = threading.Thread(target=_worker, daemon=True, name="gc-engine-scheduler")
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        """Stop the background scheduler if running."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_stop.set()
            self._scheduler_thread.join(timeout=5)
        self._scheduler_thread = None

    @property
    def scheduler_running(self) -> bool:
        """Return True if the background scheduler is active."""
        return self._scheduler_thread is not None and self._scheduler_thread.is_alive()

    # ------------------------------------------------------------------
    # Public API — Utilities
    # ------------------------------------------------------------------

    def is_marked(self, entry_id: str) -> bool:
        """Return True if *entry_id* is currently marked for collection."""
        with self._lock:
            return entry_id in self._marked

    def mark_reason(self, entry_id: str) -> str | None:
        """Return the reason why *entry_id* was marked, or None."""
        with self._lock:
            return self._marked.get(entry_id)

    def reset_stats(self) -> None:
        """Reset all cumulative statistics to zero (does not affect marks)."""
        with self._lock:
            self._total_swept = 0
            self._objects_scanned = 0
            self._objects_collected = 0
            self._memory_freed = 0
            self._total_cycles = 0
            self._cycle_durations.clear()


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _mark_reachable(
    graph: dict[str, set[str]],
    roots: set[str],
    reachable: set[str],
) -> None:
    """Depth-first traversal to mark all entries reachable from *roots*."""
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in graph.get(node, ()):
            if neighbor not in reachable:
                stack.append(neighbor)
