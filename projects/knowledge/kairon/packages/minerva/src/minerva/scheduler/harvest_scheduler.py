from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Layer: L3
---
"""

# ---
# domain: minerva
# layer: scheduler
# status: active
# ---

"""HarvestScheduler — automated knowledge harvest scheduling and orchestration.

Extracted from SharedBrain D_Harvest → minerva.
"""

import hashlib
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HarvestJob:
    """A scheduled knowledge harvesting job."""

    job_id: str
    source_type: str  # "file", "directory", "url", "api"
    source_path: str
    schedule: str  # "once", "interval", "event"
    interval_seconds: float | None = None
    event_trigger: str | None = None
    priority: int = 5  # 1-10
    last_run: float | None = None
    next_run: float | None = None
    run_count: int = 0
    status: str = "scheduled"  # scheduled, running, paused, completed, failed
    quality_score: float | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class HarvestResult:
    """Result of a single harvest execution."""

    job_id: str
    facts_extracted: int
    duplicates_skipped: int
    errors: list[str]
    quality_score: float
    duration: float
    timestamp: float = field(default_factory=time.time)


class HarvestScheduler:
    """Automated knowledge harvest scheduling and orchestration.

    Capabilities:
    1. Schedule jobs (once, interval, event-triggered)
    2. Priority-based execution ordering
    3. Concurrent harvest with configurable parallelism
    4. Deduplication across sources
    5. Quality scoring and persistence
    6. Job lifecycle management (pause/resume/cancel)
    """

    MAX_CONCURRENT = 3
    DEFAULT_INTERVAL = 3600.0  # 1 hour

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._jobs: dict[str, HarvestJob] = {}
        self._results: list[HarvestResult] = []
        self._known_facts: set[str] = set()
        self._running_count = 0
        self._lock = threading.Lock()

    # ── Job management ──────────────────────────────────────────

    def schedule(
        self,
        source_type: str,
        source_path: str,
        schedule: str = "once",
        interval: float | None = None,
        priority: int = 5,
    ) -> HarvestJob:
        """Create and register a new harvest job."""
        job_id = uuid.uuid4().hex[:12]

        if schedule == "interval" and interval is None:
            interval = self.DEFAULT_INTERVAL

        next_run: float | None = None
        event_trigger: str | None = None

        if schedule in ("once", "interval"):
            next_run = time.time()
        elif schedule == "event":
            event_trigger = source_path

        job = HarvestJob(
            job_id=job_id,
            source_type=source_type,
            source_path=source_path,
            schedule=schedule,
            interval_seconds=interval,
            event_trigger=event_trigger,
            priority=priority,
            next_run=next_run,
        )

        with self._lock:
            self._jobs[job_id] = job

        logger.info("Scheduled job %s (%s/%s)", job_id, source_type, schedule)
        return job

    def cancel(self, job_id: str) -> bool:
        """Cancel a job. Returns True if the job existed and was cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.status = "completed"
            return True

    def pause(self, job_id: str) -> bool:
        """Pause a scheduled job. Returns True on success."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "scheduled":
                return False
            job.status = "paused"
            return True

    def resume(self, job_id: str) -> bool:
        """Resume a paused job. Returns True on success."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "paused":
                return False
            job.status = "scheduled"
            return True

    # ── Execution ───────────────────────────────────────────────

    def tick(self) -> list[HarvestResult]:
        """Check for due jobs and execute them. Called periodically."""
        due = self.get_due_jobs()

        with self._lock:
            slots = max(0, self.MAX_CONCURRENT - self._running_count)
        batch = due[:slots]

        results: list[HarvestResult] = []
        for job in batch:
            with self._lock:
                self._running_count += 1
            try:
                result = self.execute_job(job)
                results.append(result)
            finally:
                with self._lock:
                    self._running_count -= 1

        return results

    def execute_job(self, job: HarvestJob) -> HarvestResult:
        """Execute a single harvest job (simulated extraction)."""
        start = time.time()

        with self._lock:
            job.status = "running"

        errors: list[str] = []
        total_facts = 0
        duplicates = 0
        quality_scores: list[float] = []

        try:
            simulated_facts = self._simulate_extraction(job)

            for fact_text in simulated_facts:
                fact_hash = hashlib.sha256(fact_text.encode()).hexdigest()
                if self.is_duplicate(fact_hash):
                    duplicates += 1
                    continue
                self.register_known_fact(fact_hash)
                total_facts += 1
                quality_scores.append(self._score_fact(fact_text))

        except Exception as exc:
            errors.append(str(exc))
            logger.exception("Error executing job %s", job.job_id)

        duration = time.time() - start
        quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        with self._lock:
            job.last_run = time.time()
            job.run_count += 1
            job.quality_score = quality

            if job.schedule == "once":
                job.status = "completed"
                job.next_run = None
            elif job.schedule == "interval" and job.interval_seconds is not None:
                job.status = "scheduled"
                job.next_run = time.time() + job.interval_seconds
            elif job.schedule == "event":
                job.status = "scheduled"
                job.next_run = None
            else:
                job.status = "scheduled"

            if errors:
                job.status = "failed"

        result = HarvestResult(
            job_id=job.job_id,
            facts_extracted=total_facts,
            duplicates_skipped=duplicates,
            errors=errors,
            quality_score=quality,
            duration=duration,
        )

        with self._lock:
            self._results.append(result)

        logger.info(
            "Job %s completed: %d facts, %d dups, quality=%.2f",
            job.job_id,
            total_facts,
            duplicates,
            quality,
        )
        return result

    def is_due(self, job: HarvestJob) -> bool:
        """Check if a job should run now."""
        if job.status != "scheduled":
            return False

        if job.schedule == "event":
            return False

        now = time.time()

        if job.schedule == "once":
            return job.last_run is None

        if job.schedule == "interval":
            if job.last_run is None:
                return True
            if job.next_run is not None and now >= job.next_run:
                return True
            return False

        return False

    # ── Event triggers ──────────────────────────────────────────

    def trigger_event(self, event_name: str) -> list[HarvestResult]:
        """Trigger all jobs listening for this event."""
        results: list[HarvestResult] = []

        with self._lock:
            matching = [
                j
                for j in self._jobs.values()
                if j.schedule == "event" and j.event_trigger == event_name and j.status == "scheduled"
            ]

        for job in matching:
            result = self.execute_job(job)
            results.append(result)

        return results

    # ── Deduplication ───────────────────────────────────────────

    def register_known_fact(self, fact_hash: str) -> bool:
        """Register a fact hash. Returns True if the fact is new."""
        with self._lock:
            if fact_hash in self._known_facts:
                return False
            self._known_facts.add(fact_hash)
            return True

    def is_duplicate(self, fact_hash: str) -> bool:
        """Check whether a fact hash has already been registered."""
        with self._lock:
            return fact_hash in self._known_facts

    # ── Query ───────────────────────────────────────────────────

    def get_job(self, job_id: str) -> HarvestJob | None:
        """Return a job by ID, or None."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, status: str | None = None) -> list[HarvestJob]:
        """List jobs, optionally filtered by status."""
        with self._lock:
            if status is None:
                return list(self._jobs.values())
            return [j for j in self._jobs.values() if j.status == status]

    def get_due_jobs(self) -> list[HarvestJob]:
        """Return due jobs ordered by priority (1 = highest)."""
        with self._lock:
            due = [j for j in self._jobs.values() if self._is_due_unlocked(j)]
            due.sort(key=lambda j: j.priority)
            return due

    def get_results(self, job_id: str | None = None, limit: int = 50) -> list[HarvestResult]:
        """Return harvest results, optionally filtered by job_id."""
        with self._lock:
            results = self._results
            if job_id is not None:
                results = [r for r in results if r.job_id == job_id]
            return results[-limit:]

    def get_stats(self) -> dict:
        """Return aggregate scheduler statistics."""
        with self._lock:
            total_facts = sum(r.facts_extracted for r in self._results)
            total_dups = sum(r.duplicates_skipped for r in self._results)
            qualities = [r.quality_score for r in self._results if r.quality_score > 0]
            return {
                "total_jobs": len(self._jobs),
                "jobs_by_status": self._count_by_status(),
                "total_runs": sum(j.run_count for j in self._jobs.values()),
                "total_facts_extracted": total_facts,
                "total_duplicates_skipped": total_dups,
                "average_quality": (sum(qualities) / len(qualities) if qualities else 0.0),
                "known_facts": len(self._known_facts),
            }

    # ── Internal helpers ────────────────────────────────────────

    def _is_due_unlocked(self, job: HarvestJob) -> bool:
        """Non-locking variant of is_due for use inside locked sections."""
        if job.status != "scheduled":
            return False
        if job.schedule == "event":
            return False
        now = time.time()
        if job.schedule == "once":
            return job.last_run is None
        if job.schedule == "interval":
            if job.last_run is None:
                return True
            if job.next_run is not None and now >= job.next_run:
                return True
        return False

    def _count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for j in self._jobs.values():
            counts[j.status] = counts.get(j.status, 0) + 1
        return counts

    @staticmethod
    def _simulate_extraction(job: HarvestJob) -> list[str]:
        """Produce deterministic simulated facts based on the job source."""
        base = f"{job.source_type}:{job.source_path}"
        count = max(1, hash(base) % 10 + 1)
        return [f"fact-{base}-{i}" for i in range(count)]

    @staticmethod
    def _score_fact(fact_text: str) -> float:
        """Deterministic quality score in [0.5, 1.0] derived from content."""
        h = int(hashlib.md5(fact_text.encode()).hexdigest()[:8], 16)  # noqa: S324
        return 0.5 + (h % 500) / 1000.0
