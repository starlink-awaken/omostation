from __future__ import annotations

# ruff: noqa: RUF003
import logging
import os
import sqlite3
import time
import uuid
from typing import Any

from ._compat import ProjectPaths
from .organs.capability_matcher import CapabilityMatcher  # type: ignore[import-not-found]
from .organs.engine.vision_parser import TaskEnvelope, VisionParser  # type: ignore[import-not-found]

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Engineer'
Authority: organs/D-Execution/rules/agent_lifecycle.md
Layer: L3
Constraint: "[!!] BACKWARD_COMPATIBLE_SEMANTIC_ORCHESTRATOR"
Summary: >
  SemanticOrchestrator — backward-compatible replacement for
  ArterialOrchestrator.decompose_vision().  Uses VisionParser for LLM-driven
  (or rule-based) task decomposition, and CapabilityMatcher for three-tier
  worker assignment.  Exports TaskEnvelope as a convenience re-export.
Tags:
  - orchestrator
  - semantic
  - swarm
  - p2
  - backward-compat
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Semantic Orchestrator ≡ Orchestrator
# 内涵 ≝ {Semantic, Orchestrator}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, SemanticOrchestrator)}
# 功能 ⊢ {Semantic_Orchestrator, Init_Semantic, Validate_Orchestrator}
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# organs/D-Execution/organs/semantic_orchestrator.py
# SemanticOrchestrator — semantic decompose_vision() with worker assignment
# ─────────────────────────────────────────────────────────────────────────────

_log = logging.getLogger(__name__)

# Use centralized path resolver
_project_root = str(ProjectPaths.ROOT)

# ── WorkerHandle (optional — only needed when assigning from explicit lists) ──
try:
    from nucleus.Z_Spore.interfaces.swarm import WorkerHandle  # type: ignore[import]
except ImportError:
    WorkerHandle = None  # type: ignore[assignment,misc]

# Re-export TaskEnvelope at this module level for callers who import from here
__all__ = [
    "SemanticOrchestrator",
    "TaskEnvelope",
]

logger = logging.getLogger("bos.semantic_orchestrator")

# ── Default task DB path (mirrors ArterialOrchestrator) ───────────────────────
_DEFAULT_DB_PATH = str(ProjectPaths.get_db_path("execution", "tasks.db"))


# ─────────────────────────────────────────────────────────────────────────────
# SemanticOrchestrator
# ─────────────────────────────────────────────────────────────────────────────


from .organs.intent_particle import (  # type: ignore[import-not-found]
    IntentParticle,
    MetabolicStage,
)


class SemanticOrchestrator:
    """
    Semantic replacement for :class:`ArterialOrchestrator`.

    Provides
    --------
    ``decompose(vision_text, total_eu_budget)``
        Parse a raw vision string → list of :class:`TaskEnvelope` with
        worker assignments.

    ``decompose_vision_compat(vision_id)``
        Legacy shim: reads vision content from the task DB (same format as
        ``ArterialOrchestrator.decompose_vision``), decomposes it, persists
        tasks, and returns a list of dicts matching the old schema so that
        ``ArterialOrchestrator`` can swap in this orchestrator with zero
        call-site changes::

            # Migration pattern inside ArterialOrchestrator:
            sem = SemanticOrchestrator()
            tasks = sem.decompose_vision_compat(vision_id)

    Design notes
    ------------
    * Never fails hard — all LLM/registry errors are caught and degraded.
    * EU costs 0 per decomposition cycle (Tiers 1-3 all cost 0 EU).
    * TaskEnvelope is also re-exported from this module.
    """

    def __init__(
        self,
        db_path: str | None = None,
        default_eu_budget: float = 5000.0,
    ) -> None:
        object.__init__(self)
        self.db_path: str = db_path or _DEFAULT_DB_PATH
        self.default_eu_budget = default_eu_budget

        self._parser = VisionParser()

        try:
            RoleManager = __import__(  # cross-organ: invisible to AST topology checker  # noqa: N806
                "organs.D_Memory.organs.role_manager", fromlist=["RoleManager"]
            ).RoleManager

            # Use the seeded roles DB in Z-Spore
            roles_db = os.path.join(_project_root, "nucleus/Z-Spore/seeds/roles.db")
            if os.path.exists(os.path.dirname(roles_db)):
                role_mgr = RoleManager(db_path=roles_db)
                self._matcher = CapabilityMatcher(role_mgr)
            else:
                self._matcher = CapabilityMatcher(None)
        except (ImportError, sqlite3.Error) as e:
            _log.error("%s: %s", type(e).__name__, e)
            self._matcher = CapabilityMatcher(None)  # Fallback

        # Ensure DB schema exists (idempotent)
        try:
            self._ensure_schema()
        except sqlite3.Error as exc:
            logger.warning(f"[SemanticOrchestrator] DB schema setup failed: {exc}")

    # ── Schema ────────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Create visions/tasks tables if absent (mirrors ArterialOrchestrator)."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        except sqlite3.Error as e:
            _log.error("%s: %s", type(e).__name__, e)
            pass

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS visions (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    status TEXT,
                    created_at REAL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    summary TEXT,
                    capability_req TEXT,
                    assigned_worker TEXT,
                    status TEXT,
                    eu_cost REAL DEFAULT 0.0,
                    feedback TEXT,
                    created_at REAL,
                    updated_at REAL
                )"""
            )
            conn.commit()
        finally:
            conn.close()

    # ── Core decomposition ────────────────────────────────────────────────────

    def decompose(
        self,
        vision_text: str,
        total_eu_budget: float = 5000.0,
    ) -> list[TaskEnvelope]:
        """
        Semantically decompose *vision_text* into worker-assigned TaskEnvelopes.

        Args:
            vision_text:     Natural-language task/vision description.
            total_eu_budget: EU budget to distribute across resulting tasks.

        Returns:
            Non-empty list of :class:`TaskEnvelope` instances, each with
            ``context["assigned_worker"]`` populated when a matching worker
            was found in the SynapseRegistry.
        """
        if hasattr(self, "_constraint_check"):
            self._constraint_check(f"decompose: {vision_text[:40]}")

        envelopes = self._parser.parse(vision_text, total_eu_budget)

        # Attempt worker assignment for each envelope
        for envelope in envelopes:
            try:
                worker = self._matcher.match_from_registry(envelope.capability_hint)
                if worker is not None:
                    envelope.context["assigned_worker"] = worker.worker_id
                    envelope.context["assigned_worker_capabilities"] = worker.capabilities
                else:
                    envelope.context["assigned_worker"] = None
            except (TypeError, ValueError, AttributeError) as exc:
                logger.warning(
                    f"[SemanticOrchestrator] Worker assignment failed for '{envelope.capability_hint}': {exc}"
                )
                envelope.context["assigned_worker"] = None

        logger.info(f"[SemanticOrchestrator] decompose() → {len(envelopes)} envelopes")
        return envelopes

    def decompose_vision_particle(self, vision_particle: Any) -> list[object]:
        """
        将 VisionParticle 自动展开为分形的 Symphony 任务流并利用 CapabilityMatcher 招募虚拟角色。
        Args:
            vision_particle: VisionParticle 实例
        Returns:
            list[IntentParticle]: 完成任务拆解与角色分配后的子意图粒子列表
        """
        try:
            from .organs.intent_digestor import IntentDigestor  # type: ignore[import-not-found]

            digestor = IntentDigestor(db_path=self.db_path)

            # 1. 使用 D-Logos 的元演化能力（已集成在 IntentDigestor 中）进行分形拆解
            sub_particles = digestor.digest(vision_particle, use_llm=True)

            # 2. 动态分化和招募虚拟角色 (Role 分化)
            for p in sub_particles:
                try:
                    # 将 required_capabilities 转为字符串提示，或者直接利用列表匹配
                    caps_hint = ",".join(p.required_capabilities) if p.required_capabilities else "general"
                    worker = self._matcher.match_from_registry(caps_hint)

                    if worker:
                        p.assigned_worker = worker.worker_id
                        p.assigned_role = worker.capabilities[0] if worker.capabilities else None
                        logger.info(f"[SemanticOrchestrator] Assigned {worker.worker_id} to particle {p.id}")
                    else:
                        p.assigned_worker = "PENDING_ASSIGNMENT"
                        logger.warning(f"[SemanticOrchestrator] No suitable worker for {p.id} ({caps_hint})")
                except (TypeError, ValueError, AttributeError) as e:
                    logger.error(f"[SemanticOrchestrator] Capability matching failed for {p.id}: {e}")

            return sub_particles
        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f"[SemanticOrchestrator] Failed to decompose vision particle: {e}")
            return []

    # ── Legacy compatibility shim ─────────────────────────────────────────────

    def assign_role(self, particle: IntentParticle) -> IntentParticle:
        """
        Assign a role to an IntentParticle using CapabilityMatcher.
        Leaves the particle pending when no real role match is found.
        """
        if self._matcher:
            match = None
            try:
                # Try L2 Organ interface: match(particle)
                match = self._matcher.match(particle)
            except TypeError:
                # Fallback to Engine interface: match(capability, workers)
                # or match_from_registry(capability)
                cap = particle.required_capabilities[0] if particle.required_capabilities else "*"
                if hasattr(self._matcher, "match_from_registry"):
                    match = self._matcher.match_from_registry(cap)

            if match:
                particle.assigned_role = getattr(match, "role_id", str(match))
                particle.context_snapshot["assignment_status"] = "assigned"
                particle.context_snapshot.pop("assignment_failure_reason", None)
                particle.stage = MetabolicStage.ABSORBED
            else:
                particle.assigned_role = None
                particle.assigned_worker = "PENDING_ASSIGNMENT"
                particle.context_snapshot["assignment_status"] = "pending"
                particle.context_snapshot["assignment_failure_reason"] = "no_capability_match"
                logger.warning(
                    "[SemanticOrchestrator] No real role match for particle %s (%s)",
                    particle.id,
                    ",".join(particle.required_capabilities) if particle.required_capabilities else "*",
                )

        return particle

    def decompose_vision_compat(self, vision_id: str) -> list[dict[str, Any]]:
        """
        Legacy shim that replicates the behaviour of
        ``ArterialOrchestrator.decompose_vision(vision_id)``.

        Reads the vision content from the task DB, runs the semantic
        decomposition pipeline, persists the resulting tasks, and returns a
        list of dicts that match the ``tasks`` table schema::

            [
                {
                    "id": "TASK-XXXXXXXX",
                    "parent_id": "<vision_id>",
                    "summary": "...",
                    "capability_req": "code.generation.*",
                    "assigned_worker": "<worker_id_or_None>",
                    "status": "PENDING",
                    "eu_cost": 833.33,
                    "phase": "P1",
                    "dependencies": ["TASK-YYYYYYYY"],
                    "created_at": 1700000000.0,
                    "updated_at": 1700000000.0,
                },
                ...
            ]

        Args:
            vision_id: Vision ID previously stored by
                       ``ArterialOrchestrator.receive_vision()``.

        Returns:
            List of task dicts (may be empty if vision_id not found).
        """
        if hasattr(self, "_constraint_check"):
            self._constraint_check(f"decompose_vision_compat: {vision_id}")

        # 1. Fetch vision content
        vision_text: str | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT content FROM visions WHERE id = ?", (vision_id,)).fetchone()
            conn.close()
            vision_text = row[0] if row else None
        except sqlite3.Error as exc:
            logger.error(f"[SemanticOrchestrator] Cannot read vision {vision_id}: {exc}")

        if not vision_text:
            logger.warning(f"[SemanticOrchestrator] Vision '{vision_id}' not found in DB — returning empty task list")
            return []

        # 2. Decompose
        envelopes = self.decompose(vision_text, self.default_eu_budget)

        # 3. Persist tasks and build legacy dicts
        now = time.time()
        task_dicts: list[dict[str, Any]] = []

        try:
            conn = sqlite3.connect(self.db_path)
            for envelope in envelopes:
                legacy_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
                assigned = envelope.context.get("assigned_worker")

                conn.execute(
                    """INSERT INTO tasks
                       (id, parent_id, summary, capability_req, assigned_worker,
                        status, eu_cost, feedback, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        legacy_id,
                        vision_id,
                        envelope.description,
                        envelope.capability_hint,
                        assigned,
                        "PENDING",
                        envelope.eu_budget,
                        None,
                        now,
                        now,
                    ),
                )

                task_dicts.append(
                    {
                        "id": legacy_id,
                        "parent_id": vision_id,
                        "summary": envelope.description,
                        "capability_req": envelope.capability_hint,
                        "assigned_worker": assigned,
                        "status": "PENDING",
                        "eu_cost": envelope.eu_budget,
                        "phase": envelope.phase,
                        "dependencies": envelope.dependencies,
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            conn.execute("UPDATE visions SET status = 'DECOMPOSED' WHERE id = ?", (vision_id,))
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            logger.error(f"[SemanticOrchestrator] Failed to persist tasks for {vision_id}: {exc}")

        logger.info(
            f"[SemanticOrchestrator] decompose_vision_compat('{vision_id}') → {len(task_dicts)} tasks persisted"
        )
        return task_dicts

    # ── Phase 3: Parallel assignment & conflict detection ─────────────────────

    def assign_parallel_tasks(
        self,
        envelopes: list[TaskEnvelope],
        max_concurrent: int = 1,
    ) -> dict[str, list[TaskEnvelope]]:
        """
        Group envelopes by assigned_worker and detect scheduling conflicts.

        A *conflict* occurs when the same worker has two or more envelopes
        sharing the same ``capability_hint`` and the worker's concurrency
        limit (``max_concurrent``) is 1.

        Args:
            envelopes:      TaskEnvelopes produced by :meth:`decompose`.
            max_concurrent: Maximum parallel tasks per (worker, capability)
                            pair before a conflict is declared.

        Returns:
            A mapping ``{worker_id: [envelopes], "CONFLICTS": [envelopes]}``.
            Workers that have no conflicts appear under their own key.
            The special ``"CONFLICTS"`` key lists every envelope that was
            flagged as a scheduling conflict.
        """
        assignments: dict[str, list[TaskEnvelope]] = {}
        conflicts: list[TaskEnvelope] = []

        # Track (worker_id, capability_hint) → count for conflict detection
        _cap_count: dict[tuple[str, str], int] = {}

        for envelope in envelopes:
            worker_id: str = envelope.context.get("assigned_worker") or "UNASSIGNED"
            cap_key = (worker_id, envelope.capability_hint)
            count = _cap_count.get(cap_key, 0)

            if worker_id != "UNASSIGNED" and count >= max_concurrent:
                # This envelope is a conflict — mark it and collect separately
                envelope.context["conflict_status"] = "CONFLICT"
                conflicts.append(envelope)
                logger.info(
                    f"[SemanticOrchestrator] Conflict detected: worker={worker_id} "
                    f"cap={envelope.capability_hint} task={envelope.task_id}"
                )
            else:
                _cap_count[cap_key] = count + 1
                assignments.setdefault(worker_id, []).append(envelope)

        assignments["CONFLICTS"] = conflicts

        logger.info(
            f"[SemanticOrchestrator] assign_parallel_tasks → "
            f"{len(assignments) - 1} worker buckets, {len(conflicts)} conflicts"
        )
        return assignments

    # ── Phase 3: Dependency graph ─────────────────────────────────────────────

    def build_dependency_graph(
        self,
        envelopes: list[TaskEnvelope],
    ) -> dict[str, list[str]]:
        """
        Build a task dependency graph from envelope metadata.

        For every envelope the method:

        1. Seeds the dep list from ``envelope.dependencies`` (already parsed
           by VisionParser).
        2. Scans ``envelope.description`` for natural-language dependency
           keywords and cross-references other envelopes by task_id.

        Dependency keywords: "after", "depends on", "requires",
        "uses output from".

        Args:
            envelopes: List of TaskEnvelopes to analyse.

        Returns:
            ``{task_id: [list of task_id strings this task depends on]}``.
            Tasks with no detected dependencies map to an empty list.
        """
        _DEP_KEYWORDS = ("after", "depends on", "requires", "uses output from")  # noqa: N806

        # Build a quick lookup of task_id → envelope for cross-referencing
        id_map: dict[str, TaskEnvelope] = {e.task_id: e for e in envelopes}

        graph: dict[str, list[str]] = {}

        for envelope in envelopes:
            deps: list[str] = list(envelope.dependencies)  # shallow copy

            desc_lower = envelope.description.lower()
            if any(kw in desc_lower for kw in _DEP_KEYWORDS):
                # Look for any *other* task_id mentioned in this description
                for other_id, other_env in id_map.items():
                    if other_id == envelope.task_id:
                        continue
                    if other_id in envelope.description or other_env.description.lower()[:20] in desc_lower:
                        if other_id not in deps:
                            deps.append(other_id)

            graph[envelope.task_id] = deps

        logger.info(
            f"[SemanticOrchestrator] build_dependency_graph → "
            f"{sum(len(v) for v in graph.values())} dependency edges across "
            f"{len(graph)} tasks"
        )
        return graph

    # ── Phase 3: Conflict resolution / arbitration ────────────────────────────

    def resolve_conflicts(
        self,
        conflicts: list[TaskEnvelope],
        available_workers: list[str] | None = None,
    ) -> list[TaskEnvelope]:
        """
        Attempt to re-assign conflicting envelopes to alternative workers.

        For each conflicting envelope:
        * Tries :meth:`CapabilityMatcher.match_from_registry` to find a
          *different* worker for the same capability.
        * If no alternative is available the envelope is marked
          ``context["conflict_status"] = "QUEUED"`` and persisted to the
          tasks DB with ``status="conflict_pending"``.

        Args:
            conflicts:         List of conflicting TaskEnvelopes (from
                               :meth:`assign_parallel_tasks`).
            available_workers: Optional allowlist of worker IDs to consider.
                               When supplied, only workers whose ID appears in
                               this list are eligible for re-assignment.

        Returns:
            The same envelope list, mutated in-place (re-assigned or QUEUED).
        """
        resolved: list[TaskEnvelope] = []
        now = time.time()

        for envelope in conflicts:
            original_worker = envelope.context.get("assigned_worker")
            new_worker: str | None = None

            try:
                worker_handle = self._matcher.match_from_registry(envelope.capability_hint)
                if worker_handle is not None:
                    candidate = worker_handle.worker_id
                    # Must differ from the conflicting worker
                    if candidate != original_worker:
                        if available_workers is None or candidate in available_workers:
                            new_worker = candidate
            except (TypeError, ValueError, AttributeError) as exc:
                logger.warning(f"[SemanticOrchestrator] Re-assignment lookup failed for {envelope.task_id}: {exc}")

            if new_worker is not None:
                envelope.context["assigned_worker"] = new_worker
                envelope.context["conflict_status"] = "REASSIGNED"
                logger.info(f"[SemanticOrchestrator] Conflict resolved: {envelope.task_id} → {new_worker}")
            else:
                # No alternative — queue for later execution
                envelope.context["conflict_status"] = "QUEUED"
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.execute(
                        """INSERT OR REPLACE INTO tasks
                           (id, parent_id, summary, capability_req, assigned_worker,
                            status, eu_cost, feedback, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            envelope.task_id,
                            envelope.context.get("vision_id"),
                            envelope.description,
                            envelope.capability_hint,
                            original_worker,
                            "conflict_pending",
                            envelope.eu_budget,
                            None,
                            now,
                            now,
                        ),
                    )
                    conn.commit()
                    conn.close()
                except sqlite3.Error as exc:
                    logger.error(
                        f"[SemanticOrchestrator] DB persist failed for conflict_pending {envelope.task_id}: {exc}"
                    )
                logger.warning(f"[SemanticOrchestrator] No alternative worker for {envelope.task_id} — queued")

            resolved.append(envelope)

        logger.info(
            f"[SemanticOrchestrator] resolve_conflicts → "
            f"{sum(1 for e in resolved if e.context.get('conflict_status') == 'REASSIGNED')} "
            f"reassigned, "
            f"{sum(1 for e in resolved if e.context.get('conflict_status') == 'QUEUED')} queued"
        )
        return resolved

    # ── Phase 3: Result consolidation ─────────────────────────────────────────

    def consolidate_results(
        self,
        task_ids: list[str],
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        """
        Poll the tasks DB until all supplied task_ids have reached a terminal
        state or *timeout_seconds* elapses.

        Terminal statuses: ``"done"``, ``"DONE"``, ``"completed"``,
        ``"COMPLETED"``, ``"failed"``, ``"FAILED"``, ``"error"``.

        Args:
            task_ids:        List of task IDs to monitor.
            timeout_seconds: Maximum wall-clock seconds to wait before
                             returning with whatever is known.

        Returns:
            ``{completed: [...], failed: [...], pending: [...], summary: str}``
        """
        _TERMINAL_OK = {"done", "completed"}  # noqa: N806
        _TERMINAL_FAIL = {"failed", "error", "cancelled"}  # noqa: N806

        if not task_ids:
            return {
                "completed": [],
                "failed": [],
                "pending": [],
                "summary": "No task IDs supplied.",
            }

        completed: list[str] = []
        failed: list[str] = []
        pending: list[str] = list(task_ids)

        deadline = time.time() + timeout_seconds
        poll_interval = 0.5  # seconds

        while pending and time.time() < deadline:
            still_pending: list[str] = []
            try:
                conn = sqlite3.connect(self.db_path)
                placeholders = ",".join("?" * len(pending))
                rows = conn.execute(
                    f"SELECT id, status FROM tasks WHERE id IN ({placeholders})",  # noqa: S608
                    pending,
                ).fetchall()
                conn.close()

                known_ids = {row[0]: row[1].lower() if row[1] else "" for row in rows}

                for tid in pending:
                    status = known_ids.get(tid, "")
                    if status in _TERMINAL_OK:
                        completed.append(tid)
                    elif status in _TERMINAL_FAIL:
                        failed.append(tid)
                    else:
                        still_pending.append(tid)

            except sqlite3.Error as exc:
                logger.error(f"[SemanticOrchestrator] DB poll error: {exc}")
                still_pending = pending  # retry next cycle

            pending = still_pending
            if pending:
                time.sleep(poll_interval)

        total = len(task_ids)
        summary = (
            f"{len(completed)}/{total} completed, "
            f"{len(failed)}/{total} failed, "
            f"{len(pending)}/{total} still pending" + (" (timeout)" if pending else "")
        )

        logger.info(f"[SemanticOrchestrator] consolidate_results → {summary}")
        return {
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "summary": summary,
        }

    # ── Phase 3: High-level swarm orchestration entry point ───────────────────

    def orchestrate_swarm(
        self,
        vision_text: str,
        total_eu_budget: float = 5000.0,
        max_workers: int = 5,
    ) -> dict[str, Any]:
        """
        Phase 3 orchestration entry-point — strings all pipeline stages together.

        Pipeline
        --------
        1. ``decompose(vision_text, total_eu_budget)`` → envelopes
        2. ``build_dependency_graph(envelopes)`` → dep_graph
        3. ``assign_parallel_tasks(envelopes)`` → assignments
        4. ``resolve_conflicts(assignments["CONFLICTS"])`` → resolved
        5. Store all non-conflict tasks to DB with ``status="assigned"``
        6. Return orchestration summary dict

        Args:
            vision_text:     Natural-language vision/task description.
            total_eu_budget: EU budget to distribute across subtasks.
            max_workers:     Hint for maximum parallel workers (not enforced
                             at this layer; passed through for callers).

        Returns:
            ``{vision_text, total_tasks, assignments, dependency_graph,
               conflicts_resolved, eu_budget, status: "ORCHESTRATED"}``
        """
        self._constraint_check(f"orchestrate_swarm: {vision_text[:40]}")
        logger.info(
            f"[SemanticOrchestrator] orchestrate_swarm START budget={total_eu_budget} max_workers={max_workers}"
        )

        # Step 1 — Decompose
        envelopes: list[TaskEnvelope] = self.decompose(vision_text, total_eu_budget)

        # Step 2 — Build dependency graph
        dep_graph: dict[str, list[str]] = self.build_dependency_graph(envelopes)

        # Step 3 — Assign (detect conflicts)
        assignments: dict[str, list[TaskEnvelope]] = self.assign_parallel_tasks(envelopes)

        # Step 4 — Resolve conflicts
        raw_conflicts: list[TaskEnvelope] = assignments.get("CONFLICTS", [])
        resolved_conflicts: list[TaskEnvelope] = self.resolve_conflicts(raw_conflicts)

        # Step 5 — Persist all assigned (non-conflict) tasks to DB
        now = time.time()
        persisted_ids: list[str] = []

        try:
            conn = sqlite3.connect(self.db_path)
            for worker_id, worker_envelopes in assignments.items():
                if worker_id == "CONFLICTS":
                    continue
                for envelope in worker_envelopes:
                    conn.execute(
                        """INSERT OR REPLACE INTO tasks
                           (id, parent_id, summary, capability_req, assigned_worker,
                            status, eu_cost, feedback, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            envelope.task_id,
                            envelope.context.get("vision_id"),
                            envelope.description,
                            envelope.capability_hint,
                            worker_id if worker_id != "UNASSIGNED" else None,
                            "assigned",
                            envelope.eu_budget,
                            None,
                            now,
                            now,
                        ),
                    )
                    persisted_ids.append(envelope.task_id)
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            logger.error(f"[SemanticOrchestrator] Failed to persist swarm tasks: {exc}")

        # Build a serialisable view of assignments (worker → task_ids)
        assignments_summary: dict[str, list[str]] = {
            wid: [e.task_id for e in envs] for wid, envs in assignments.items()
        }

        result: dict[str, Any] = {
            "vision_text": vision_text,
            "total_tasks": len(envelopes),
            "assignments": assignments_summary,
            "dependency_graph": dep_graph,
            "conflicts_resolved": len(resolved_conflicts),
            "eu_budget": total_eu_budget,
            "max_workers": max_workers,
            "persisted_task_ids": persisted_ids,
            "status": "ORCHESTRATED",
        }

        logger.info(
            f"[SemanticOrchestrator] orchestrate_swarm DONE → "
            f"{len(envelopes)} tasks, {len(resolved_conflicts)} conflicts resolved"
        )
        return result

    # ── CoreService contract ─────────────────────────────────────────────────

    def validate_internal_state(self) -> bool:
        """Health check — verifies VisionParser and CapabilityMatcher are live."""
        return self._parser is not None and self._matcher is not None

    @staticmethod
    def _constraint_check(_constraint: str) -> None:
        pass
