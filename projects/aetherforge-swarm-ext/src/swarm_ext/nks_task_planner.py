from __future__ import annotations

# ruff: noqa: RUF002
import sqlite3

"""
---
Type: Organ
Status: Active
Layer: L3
Summary: NKS-aware task planner that uses graph-based impact analysis to guide execution.
Owner: bos-core
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Nks Task Planner ≡ Module
# 内涵 ≝ {Nks, Task, Planner}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, NksTaskPlanner)}
# 功能 ⊢ {Nks_Task, Task_Planner, Planner_Init}
# =============================================================================
import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, TypedDict

from .organs.symphony.models import AgentProfile  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ExecutionStrategy(Enum):
    """Execution strategy for a planned task."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CAREFUL = "careful"


# ---------------------------------------------------------------------------
# Risk helpers
# ---------------------------------------------------------------------------

_RISK_THRESHOLDS = [
    (0.2, "MINIMAL"),
    (0.4, "LOW"),
    (0.6, "MEDIUM"),
    (0.8, "HIGH"),
]


def _get_risk_level(score: float) -> str:
    for threshold, level in _RISK_THRESHOLDS:
        if score < threshold:
            return level
    return "CRITICAL"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TaskAnalysis:
    """
    Result of analysing a planned task against the NKS knowledge graph.

    Attributes:
        risk_score: Numeric risk score 0.0–1.0.
        affected_components: Domain names / component IDs affected.
        test_files: Test files that should be run after the change.
        execution_strategy: String value of ExecutionStrategy enum.
        suggested_agents: Agent IDs or profiles recommended for the task.
        metadata: Arbitrary extra context attached during analysis.
        impact_report: Raw ImpactReport from the ImpactAnalyzer.
        related_code: Additional related source files identified.
        requires_approval: True when the CAREFUL strategy was chosen and
            human / automated approval is required before execution.
    """

    risk_score: float = 0.0
    affected_components: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    execution_strategy: str = ExecutionStrategy.SEQUENTIAL.value
    suggested_agents: list = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    impact_report: Any = None  # ImpactReport | None
    related_code: list[str] = field(default_factory=list)
    requires_approval: bool = False

    # ------------------------------------------------------------------

    def _get_risk_level(self) -> str:
        return _get_risk_level(self.risk_score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_level": self._get_risk_level(),
            "affected_components": self.affected_components,
            "test_files": self.test_files,
            "execution_strategy": self.execution_strategy,
            "requires_approval": self.requires_approval,
            "suggested_agents": self.suggested_agents,
            "related_code": self.related_code,
            "metadata": self.metadata,
        }


@dataclass
class AgentContext:
    """
    Context bundle provided to an agent before it begins work on a task.

    Attributes:
        architecture_overview: Human-readable overview of the relevant system.
        affected_files: Files the task directly touches.
        risk_assessment: Dict with risk scoring and contributing factors.
        suggested_tools: Tool names or IDs recommended for the task.
        call_graphs: Simplified call-graph data for affected entities.
        related_entities: Entity names referenced by the task files.
        metadata: Arbitrary extra data.
    """

    architecture_overview: str = ""
    affected_files: list[str] = field(default_factory=list)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    suggested_tools: list = field(default_factory=list)
    call_graphs: dict[str, Any] = field(default_factory=dict)
    related_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture_overview": self.architecture_overview,
            "affected_files": self.affected_files,
            "risk_assessment": self.risk_assessment,
            "suggested_tools": self.suggested_tools,
            "call_graphs": self.call_graphs,
            "related_entities": self.related_entities,
            "metadata": self.metadata,
        }


class ImpactReportLike(Protocol):
    risk_score: float
    suggested_tests: list[str]


class ImpactAnalyzerLike(Protocol):
    graph_store: Any

    def analyze_file_change(self, file_path: str, change_type: str) -> ImpactReportLike: ...


class QueryEngineLike(Protocol):
    def query_related_code(self, file_path: str, depth: int = 2) -> list[str]: ...

    def query_entities_by_file(self, file_path: str) -> list[object]: ...

    def query_call_graph(self, entity_id: str, depth: int = 2) -> Any: ...

    def get_neighbors(self, entity_id: str) -> list[Any]: ...


class AnalyzeTaskParams(TypedDict, total=False):
    task_description: str
    modified_files: list[str]
    change_type: str


def _require_str_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field_name} must be list[str]")
    return value


# ---------------------------------------------------------------------------
# NKSTaskPlanner
# ---------------------------------------------------------------------------


class NKSTaskPlanner:
    """
    Graph-aware task planner for the B-OS execution layer.

    Uses an :class:`ImpactAnalyzer` to evaluate the blast-radius of a planned
    change and a :class:`GraphQueryEngine` to build rich agent context.
    Exposes BOS-URI handler methods (``_handle_*``) for integration with the
    URI routing fabric.
    """

    def __init__(
        self,
        impact_analyzer: ImpactAnalyzerLike | None = None,
        query_engine: QueryEngineLike | None = None,
        # Legacy kwargs accepted silently
        graph_store: Any | None = None,
        db_path: str | None = None,
    ) -> None:
        object.__init__(self)
        self.organ_name = "nks_task_planner"
        self.organ_id = str(uuid.uuid4())

        # Resolve impact_analyzer
        if impact_analyzer is not None:
            self.impact_analyzer: ImpactAnalyzerLike | None = impact_analyzer
        elif graph_store is not None:
            try:
                _ia_mod = __import__(
                    "organs.D_Memory.organs.nks.impact_analyzer",
                    fromlist=["ImpactAnalyzer", "ImpactReport"],
                )
                ImpactAnalyzer = _ia_mod.ImpactAnalyzer  # noqa: N806
                ImpactReport = _ia_mod.ImpactReport  # noqa: N806
                self.impact_analyzer = ImpactAnalyzer(graph_store=graph_store)
            except ImportError:
                self.impact_analyzer = None
        else:
            try:
                _ia_mod = __import__(
                    "organs.D_Memory.organs.nks.impact_analyzer",
                    fromlist=["ImpactAnalyzer", "ImpactReport"],
                )
                ImpactAnalyzer = _ia_mod.ImpactAnalyzer  # noqa: N806
                ImpactReport = _ia_mod.ImpactReport  # noqa: F841, N806
                self.impact_analyzer = ImpactAnalyzer(db_path=db_path)
            except ImportError:
                self.impact_analyzer = None

        # Resolve query_engine
        if query_engine is not None:
            self.query_engine: QueryEngineLike | None = query_engine
        elif graph_store is not None:
            try:
                GraphQueryEngine = __import__(  # noqa: N806
                    "organs.D_Memory.organs.nks.query_engine", fromlist=["GraphQueryEngine"]
                ).GraphQueryEngine
                self.query_engine = GraphQueryEngine(graph_store)
            except (ImportError, KeyError, AttributeError):
                self.query_engine = None
        else:
            self.query_engine = None

        self._energy_consumed: float = 0.0
        self._call_count: int = 0

    # ------------------------------------------------------------------
    # Core: task analysis
    # ------------------------------------------------------------------

    def analyze_task(
        self,
        task_description: str,
        modified_files: list[str],
        change_type: str = "modify",
    ) -> TaskAnalysis:
        """
        Analyse the impact of modifying *modified_files* and return a
        :class:`TaskAnalysis` with risk score, affected components, suggested
        tests and execution strategy.
        """
        self._call_count += 1
        self._energy_consumed += 1.0

        if not modified_files:
            return TaskAnalysis(
                risk_score=0.0,
                affected_components=[],
                test_files=[],
                execution_strategy=ExecutionStrategy.PARALLEL.value,
                metadata={
                    "task_description": task_description,
                    "modified_files_count": 0,
                    "change_type": change_type,
                },
            )

        # Aggregate impact reports for each modified file
        reports: list[ImpactReportLike] = []
        all_test_files: list[str] = []
        affected_components: set[str] = set()
        related_code: set[str] = set()

        for file_path in modified_files:
            report = self._analyze_file(file_path, change_type)
            reports.append(report)
            if hasattr(report, "suggested_tests"):
                all_test_files.extend(report.suggested_tests or [])
            # Extract domain component from path
            component = self._extract_component(file_path)
            if component:
                affected_components.add(component)

        # Compute aggregate risk
        if reports:
            aggregate_risk = max(getattr(r, "risk_score", 0.0) for r in reports)
        else:
            aggregate_risk = 0.0

        # Determine strategy
        strategy = self.determine_execution_strategy(aggregate_risk, len(modified_files))

        # Build combined test list (dedup)
        test_files = list(dict.fromkeys(all_test_files))

        # Use the highest-risk report as the primary impact_report
        primary_report = reports[0] if reports else None

        requires_approval = strategy == ExecutionStrategy.CAREFUL

        # ----------------------------------------------------------------
        # Approval gate (R2-D02): CAREFUL strategy tasks must be approved
        # before execution proceeds.  Uses dynamic import to avoid a
        # organs → nucleus layer violation in the reverse direction.
        # ----------------------------------------------------------------
        if requires_approval:
            task_id = task_description[:64] if task_description else "unknown"
            try:
                approval_mod = __import__(
                    "organs.D_Governance.organs.approval_router",
                    fromlist=["ApprovalRouter"],
                )
                approval_router = approval_mod.ApprovalRouter
            except (ImportError, AttributeError) as approval_exc:
                _log.warning("[NKSTaskPlanner] Approval gate unavailable: %s", approval_exc)
            else:
                approval_result = approval_router().request_approval(
                    task_id=task_id,
                    plan={
                        "strategy": strategy.value,
                        "requires_approval": True,
                        "risk_score": round(aggregate_risk, 4),
                    },
                    requester="NKSTaskPlanner",
                )
                if not approval_result.approved:
                    raise PermissionError(
                        f"Task requires approval but was not approved: "
                        f"{approval_result.reason} (request_id={approval_result.request_id})"
                    )
                _log.info(
                    "[NKSTaskPlanner] Approval granted for task '%s': %s",
                    task_id,
                    approval_result.reason,
                )

        return TaskAnalysis(
            risk_score=round(aggregate_risk, 4),
            affected_components=list(affected_components),
            test_files=test_files,
            execution_strategy=strategy.value,
            requires_approval=requires_approval,
            suggested_agents=[],
            metadata={
                "task_description": task_description,
                "modified_files_count": len(modified_files),
                "change_type": change_type,
                "files": modified_files,
            },
            impact_report=primary_report,
            related_code=list(related_code),
        )

    def _analyze_file(self, file_path: str, change_type: str) -> ImpactReportLike:
        """Run impact analysis for a single file; return empty ImpactReport on error."""
        try:
            ImpactReport = __import__(  # noqa: N806
                "organs.D_Memory.organs.nks.impact_analyzer", fromlist=["ImpactReport"]
            ).ImpactReport
        except (ImportError, AttributeError):
            return type("_IR", (), {"risk_score": 0.0, "suggested_tests": []})()
        if self.impact_analyzer is None:
            return ImpactReport(risk_score=0.0)
        try:
            return self.impact_analyzer.analyze_file_change(file_path, change_type)
        except (OSError, ValueError, AttributeError, ImportError) as exc:
            _log.debug("analyze_file_change failed for %s: %s", file_path, exc)
            # Estimate risk from change_type weight
            weights = {"add": 0.1, "delete": 0.5, "modify": 0.3}
            risk = weights.get(change_type, 0.3)
            try:
                return ImpactReport(risk_score=risk)
            except (ValueError, TypeError):
                return type("_IR", (), {"risk_score": risk, "suggested_tests": []})()

    @staticmethod
    def _extract_component(file_path: str) -> str:
        """Extract a domain component name from a file path."""
        # Match patterns like organs/D-Memory/... → "D-Memory"
        match = re.search(r"organs/([^/]+)/", file_path)
        if match:
            return match.group(1)
        # Fall back to top-level directory
        parts = file_path.replace("\\", "/").split("/")
        return parts[0] if parts else ""

    # ------------------------------------------------------------------
    # Core: execution strategy
    # ------------------------------------------------------------------

    def determine_execution_strategy(
        self,
        risk_score: float,
        affected_count: int,
    ) -> ExecutionStrategy:
        """
        Map a *risk_score* and *affected_count* to an :class:`ExecutionStrategy`.

        Rules:
        - risk < 0.3 **and** affected_count < 10 → PARALLEL
        - 0.3 ≤ risk < 0.7 **or** affected_count ≥ 10 → SEQUENTIAL
        - risk ≥ 0.7 → CAREFUL
        """
        # Large number of affected files bumps effective risk
        effective_risk = risk_score
        if affected_count >= 10:
            effective_risk = min(1.0, risk_score + 0.15)

        if effective_risk < 0.3:
            return ExecutionStrategy.PARALLEL
        if effective_risk < 0.7:
            return ExecutionStrategy.SEQUENTIAL
        return ExecutionStrategy.CAREFUL

    # ------------------------------------------------------------------
    # Core: agent suggestion
    # ------------------------------------------------------------------

    def suggest_agents_for_task(
        self,
        affected_entities: list[Any],
        available_agents: list[Any],
    ) -> list[tuple[Any, float]]:
        """
        Score each agent in *available_agents* against *affected_entities*.

        Returns a list of ``(AgentProfile, score)`` tuples ordered by score
        descending.  Score is in [0.0, 1.0].
        """
        results: list[tuple[Any, float]] = []

        # Determine domains of affected entities
        entity_domains: set[str] = set()
        for e in affected_entities:
            if hasattr(e, "source_files") and e.source_files:
                for sf in e.source_files:
                    comp = self._extract_component(sf)
                    if comp:
                        entity_domains.add(comp)
            if hasattr(e, "properties"):
                domain = (e.properties or {}).get("domain", "")
                if domain:
                    entity_domains.add(domain)

        for agent in available_agents:
            score = self._score_agent(agent, entity_domains)
            results.append((agent, score))

        # Sort by score descending
        results.sort(key=lambda t: t[1], reverse=True)
        return results

    def _score_agent(self, agent: Any, entity_domains: set[str]) -> float:
        """Compute an affinity score for an agent given the entity domains."""
        score = 0.0

        # Domain specialization match
        spec = getattr(agent, "specialization", None) or ""
        if spec and entity_domains and spec in entity_domains:
            score += 0.5

        # Capability score (average of all capabilities)
        caps = getattr(agent, "capabilities", {}) or {}
        if caps:
            cap_values = []
            for _k, v in caps.items():
                # Handle both string keys and enum keys
                cap_values.append(float(v))
            if cap_values:
                score += sum(cap_values) / len(cap_values) * 0.4

        # Penalise for high load
        load = getattr(agent, "current_load", 0.0) or 0.0
        score -= load * 0.1

        return max(0.0, min(1.0, round(score, 4)))

    # ------------------------------------------------------------------
    # Core: test selection
    # ------------------------------------------------------------------

    def select_tests_for_task(
        self,
        modified_files: list[str],
        impact_report: Any,
    ) -> list[str]:
        """
        Select test files for a task given modified files and an impact report.

        Always includes tests from *impact_report.suggested_tests*.
        Also infers test file paths from modified_files patterns.
        """
        tests: list[str] = []

        # Include tests from impact report
        suggested = getattr(impact_report, "suggested_tests", []) or []
        tests.extend(suggested)

        # Infer test files from source paths
        for file_path in modified_files:
            inferred = self._infer_test_file(file_path)
            if inferred and inferred not in tests:
                tests.append(inferred)

        return list(dict.fromkeys(tests))  # preserve order, deduplicate

    @staticmethod
    def _infer_test_file(source_path: str) -> str:
        """Guess the corresponding test file path for a source file."""
        p = source_path.replace("\\", "/")
        # organs/D-Memory/organs/db.py → tests/unit/test_db.py
        filename = p.split("/")[-1]
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        return f"tests/unit/test_{stem}.py"

    # ------------------------------------------------------------------
    # Core: agent context
    # ------------------------------------------------------------------

    def get_agent_context(
        self,
        agent_id: str,
        task_files: list[str],
    ) -> AgentContext:
        """
        Build an :class:`AgentContext` for *agent_id* working on *task_files*.
        """
        call_graphs: dict[str, Any] = {}
        related_entities: list[str] = []

        # Try to pull call-graph data from the query engine
        if self.query_engine is not None:
            for file_path in task_files:
                try:
                    component = self._extract_component(file_path)
                    neighbors = self.query_engine.get_neighbors(entity_id=component)
                    if neighbors:
                        call_graphs[file_path] = [
                            getattr(n[0], "entity_id", str(n[0]))
                            if isinstance(n, tuple)
                            else getattr(n, "entity_id", str(n))
                            for n in neighbors
                        ]
                except (KeyError, AttributeError, TypeError, ValueError) as e:
                    _log.warning("call graph neighbor lookup failed: %s", e)

        # Aggregate risk for the files
        risk_score = 0.0
        if self.impact_analyzer is not None:
            for fp in task_files:
                try:
                    rep = self.impact_analyzer.analyze_file_change(fp, "modify")
                    risk_score = max(risk_score, getattr(rep, "risk_score", 0.0))
                except (KeyError, AttributeError):
                    risk_score = max(risk_score, 0.3)

        # Build architecture overview
        components = list({self._extract_component(f) for f in task_files if f})
        overview = f"Task touches {len(task_files)} file(s) in component(s): " + ", ".join(components or ["unknown"])

        return AgentContext(
            architecture_overview=overview,
            affected_files=list(task_files),
            risk_assessment={
                "score": round(risk_score, 4),
                "level": _get_risk_level(risk_score),
                "agent_id": agent_id,
            },
            suggested_tools=["code_editor", "test_runner"],
            call_graphs=call_graphs,
            related_entities=related_entities,
            metadata={"agent_id": agent_id},
        )

    # ------------------------------------------------------------------
    # Helper: risk level (public for backwards-compat with spec)
    # ------------------------------------------------------------------

    @staticmethod
    def get_risk_level(score: float) -> str:
        return _get_risk_level(score)

    # ------------------------------------------------------------------
    # BOS-URI handlers
    # ------------------------------------------------------------------

    def _handle_analyze_task(self, params: AnalyzeTaskParams) -> dict[str, Any]:
        try:
            modified_files = _require_str_list(params.get("modified_files", []), "modified_files")
            analysis = self.analyze_task(
                task_description=params.get("task_description", ""),
                modified_files=modified_files,
                change_type=params.get("change_type", "modify"),
            )
            return {"status": "success", "analysis": analysis.to_dict()}
        except (ImportError, OSError, ValueError, AttributeError, TypeError) as exc:
            return {"status": "error", "error": str(exc)}

    def _handle_suggest_agents(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            entity_ids: list[str] = params.get("entity_ids", [])
            raw_agents: list[dict] = params.get("available_agents", [])

            # Look up entities from graph store if available
            entities: list[Any] = []
            store = self._get_graph_store()
            for eid in entity_ids:
                if store is not None:
                    try:
                        e = store.get_entity(eid)
                        if e:
                            entities.append(e)
                            continue
                    except (sqlite3.Error, ValueError) as e:
                        _log.warning("entity store lookup failed: %s", e)

            # Build AgentProfile objects from raw dicts
            agent_profiles: list[Any] = []
            for raw in raw_agents:
                try:
                    profile = AgentProfile(
                        agent_id=raw.get("agent_id", str(uuid.uuid4())),
                        capabilities=raw.get("capabilities", {}),
                        specialization=raw.get("specialization"),
                        current_load=raw.get("current_load", 0.0),
                    )
                    agent_profiles.append(profile)
                except (ValueError, TypeError) as e:
                    _log.warning("agent profile construction failed: %s", e)

            suggestions = self.suggest_agents_for_task(entities, agent_profiles)
            return {
                "status": "success",
                "suggestions": [
                    {
                        "agent_id": getattr(a, "agent_id", str(a)),
                        "score": s,
                    }
                    for a, s in suggestions
                ],
            }
        except (ImportError, OSError, ValueError, AttributeError, TypeError) as exc:
            return {"status": "error", "error": str(exc)}

    def _handle_select_tests(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            modified_files: list[str] = params.get("modified_files", [])
            raw_report: dict[str, Any] = params.get("impact_report", {})

            # Reconstruct a minimal ImpactReport-like object
            try:
                ImpactReport = __import__(  # noqa: N806
                    "organs.D_Memory.organs.nks.impact_analyzer", fromlist=["ImpactReport"]
                ).ImpactReport
                report = ImpactReport(
                    risk_score=raw_report.get("risk_score", 0.0),
                    suggested_tests=raw_report.get("suggested_tests", []),
                )
            except ImportError:
                report = type(
                    "_IR",
                    (),
                    {
                        "risk_score": raw_report.get("risk_score", 0.0),
                        "suggested_tests": raw_report.get("suggested_tests", []),
                    },
                )()

            test_files = self.select_tests_for_task(modified_files, report)
            return {"status": "success", "test_files": test_files}
        except ImportError as exc:
            return {"status": "error", "error": str(exc)}

    def _handle_get_context(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            context = self.get_agent_context(
                agent_id=params.get("agent_id", "unknown"),
                task_files=params.get("task_files", []),
            )
            return {"status": "success", "context": context.to_dict()}
        except (ImportError, OSError, ValueError, AttributeError, TypeError) as exc:
            return {"status": "error", "error": str(exc)}

    def _handle_determine_strategy(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            risk_score: float = float(params.get("risk_score", 0.0))
            affected_count: int = int(params.get("affected_files_count", 1))
            strategy = self.determine_execution_strategy(risk_score, affected_count)
            requires_approval = strategy == ExecutionStrategy.CAREFUL
            plan: dict[str, Any] = {
                "status": "success",
                "strategy": strategy.value,
                "requires_approval": requires_approval,
            }

            # ----------------------------------------------------------------
            # R2-D02: wire the approval gate for CAREFUL strategy
            # ----------------------------------------------------------------
            if requires_approval:
                try:
                    ApprovalRouter = __import__(  # noqa: N806
                        "organs.D_Governance.organs.approval_router", fromlist=["ApprovalRouter"]
                    ).ApprovalRouter
                except (ImportError, AttributeError) as approval_exc:
                    _log.warning(
                        "[NKSTaskPlanner] Approval gate unavailable (non-fatal): %s",
                        approval_exc,
                    )
                else:
                    task_id: str = str(params.get("task_id", "unknown"))
                    approval_result = ApprovalRouter().request_approval(
                        task_id=task_id,
                        plan=plan,
                        requester=str(params.get("agent_id", "system")),
                    )
                    plan["approval_status"] = "approved" if approval_result.approved else "rejected"
                    plan["approval_reason"] = approval_result.reason
                    plan["approval_request_id"] = approval_result.request_id
                    if not approval_result.approved:
                        plan["status"] = "rejected"
                        _log.warning(
                            "[NKSTaskPlanner] Task %s requires approval but was not approved: %s",
                            task_id,
                            approval_result.reason,
                        )

            return plan
        except (ImportError, OSError, ValueError, AttributeError, TypeError) as exc:
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        return True

    def get_stats(self) -> dict[str, Any]:
        return {
            "organ_name": self.organ_name,
            "organ_id": self.organ_id,
            "energy_consumed": self._energy_consumed,
            "call_count": self._call_count,
            "impact_analyzer_ok": self.impact_analyzer is not None,
            "query_engine_ok": self.query_engine is not None,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_graph_store(self) -> Any | None:
        """Try to obtain the underlying graph store from the impact_analyzer."""
        if self.impact_analyzer is not None and hasattr(self.impact_analyzer, "graph_store"):
            return self.impact_analyzer.graph_store
        return None


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_planner: NKSTaskPlanner | None = None


def get_global_planner(**kwargs: Any) -> NKSTaskPlanner:
    """Return the process-wide singleton :class:`NKSTaskPlanner`."""
    global _global_planner
    if _global_planner is None:
        _global_planner = NKSTaskPlanner(**kwargs)
    return _global_planner


def reset_global_planner() -> None:
    """Clear the singleton (primarily for testing)."""
    global _global_planner
    _global_planner = None
