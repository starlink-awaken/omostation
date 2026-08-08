"""L2 引擎面 — 协作引擎 + 蜂群引擎 + 个人知识引擎

基于 L0 原语构建的引擎层组件，每个引擎内部委托给对应的 L0 原语：
- CollaborationEngine → L0 TaskScheduler + RoleManager + AgentRegistry
- SwarmEngine → L0 SwarmManager + CollectiveDecision + EmergenceDetector
- PersonalEngine → L0 PersonalKnowledgeManager + KnowledgeGraphBuilder + RecommendationEngine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from ecos.common.exceptions import ECOSException
from ecos.common.logger import get_logger

logger = get_logger("engine")


class EngineStatus(Enum):
    """引擎状态"""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStage(Enum):
    """任务阶段"""

    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETING = "completing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class EngineConfig:
    """引擎配置"""

    engine_id: str
    max_concurrent: int = 10
    timeout_seconds: int = 300
    retry_count: int = 3


@dataclass
class OrchestrationTask:
    """编排任务"""

    task_id: str
    name: str
    stage: TaskStage = TaskStage.PENDING
    required_capabilities: list[str] = field(default_factory=list)
    assigned_agent: str = ""
    priority: int = 0
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CollaborationEngine:
    """协作引擎 — 委托给 L0 TaskScheduler + RoleManager + AgentRegistry

    L2 引擎面: 管理多角色协作的完整运行时
    """

    def __init__(self, config: EngineConfig):
        from ecos.l0.governance import AgentRegistry, RoleManager, TaskScheduler

        self.config = config
        self.status = EngineStatus.IDLE

        self._scheduler = TaskScheduler()
        self._role_manager = RoleManager()
        self._registry = AgentRegistry()

        self._task_stages: dict[str, TaskStage] = {}
        self._task_dependencies: dict[str, set[str]] = {}
        self._completion_handlers: dict[str, Callable[[OrchestrationTask], None]] = {}
        self._event_log: list[dict[str, Any]] = []

    def start(self) -> bool:
        try:
            self.status = EngineStatus.RUNNING
            logger.info("协作引擎启动: %s", self.config.engine_id)
            self._log_event("engine_started")
            return True
        except Exception as e:  # defensive fallback
            logger.error("协作引擎启动失败: %s", str(e))
            self.status = EngineStatus.ERROR
            return False

    def stop(self) -> bool:
        try:
            self.status = EngineStatus.STOPPED
            logger.info("协作引擎停止: %s", self.config.engine_id)
            self._log_event("engine_stopped")
            return True
        except Exception as e:  # defensive fallback
            logger.error("协作引擎停止失败: %s", str(e))
            return False

    def register_agent(self, agent_id: str, capabilities: list[str]) -> None:
        try:
            self._registry.register(agent_id, agent_id, capabilities)
            self._role_manager.define_role(
                __import__(
                    "ecos.l0.governance", fromlist=["RoleDefinition"]
                ).RoleDefinition(
                    role_id=f"role-{agent_id}",
                    role_type=__import__(
                        "ecos.l0.governance", fromlist=["RoleType"]
                    ).RoleType.WORKER,
                    capabilities=capabilities,
                    constraints={},
                )
            )
            logger.info("注册 Agent: %s, capabilities=%s", agent_id, capabilities)
        except Exception as e:  # defensive fallback
            logger.error("注册 Agent 失败: %s - %s", agent_id, str(e))
            raise ECOSException(f"注册 Agent 失败: {e}")

    def submit_task(
        self,
        task_id: str,
        name: str,
        required_capabilities: list[str] | None = None,
        priority: int = 0,
        dependencies: list[str] | None = None,
    ) -> OrchestrationTask:
        try:
            self._scheduler.submit_task(task_id, name, required_capabilities, priority)  # type: ignore[reportArgumentType]
            self._task_stages[task_id] = TaskStage.PENDING

            if dependencies:
                self._task_dependencies[task_id] = set(dependencies)

            task = OrchestrationTask(
                task_id=task_id,
                name=name,
                required_capabilities=required_capabilities or [],
                priority=priority,
            )
            logger.info("提交任务: %s, name=%s", task_id, name)
            self._log_event("task_submitted", task_id=task_id, name=name)
            return task
        except Exception as e:  # defensive fallback
            logger.error("提交任务失败: %s - %s", task_id, str(e))
            raise ECOSException(f"提交任务失败: {e}")

    def set_dependency(self, task_id: str, depends_on: str) -> None:
        self._task_dependencies.setdefault(task_id, set()).add(depends_on)

    def on_complete(
        self, task_id: str, handler: Callable[[OrchestrationTask], None]
    ) -> None:
        self._completion_handlers[task_id] = handler

    def auto_assign(self) -> list[tuple[str, str]]:
        assignments: list[tuple[str, str]] = []

        for task_id in list(self._scheduler.task_queue):
            task_info = self._scheduler.get_task(task_id)
            if not task_info or task_info.status.value != "pending":
                continue

            deps = self._task_dependencies.get(task_id, set())
            all_done = all(self._task_stages.get(d) == TaskStage.DONE for d in deps)
            if not all_done:
                continue

            idle = self._registry.get_idle_agents()
            if not idle:
                continue

            required = set(task_info.required_capabilities)
            best = None
            for agent in idle:
                if not required or required.issubset(set(agent.capabilities)):
                    best = agent
                    break

            if best:
                self._scheduler.assign_task(task_id, best.agent_id)
                self._task_stages[task_id] = TaskStage.PLANNING
                assignments.append((task_id, best.agent_id))
                self._log_event("task_assigned", task_id=task_id, agent=best.agent_id)

        return assignments

    def start_task(self, task_id: str) -> bool:
        if self._task_stages.get(task_id) != TaskStage.PLANNING:
            return False
        self._scheduler.start_task(task_id)
        self._task_stages[task_id] = TaskStage.EXECUTING
        self._log_event("task_started", task_id=task_id)
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        if self._task_stages.get(task_id) != TaskStage.EXECUTING:
            return False
        self._scheduler.complete_task(task_id, result)
        self._task_stages[task_id] = TaskStage.DONE
        self._log_event("task_completed", task_id=task_id)

        handler = self._completion_handlers.get(task_id)
        if handler:
            task = OrchestrationTask(
                task_id=task_id, name="", stage=TaskStage.DONE, result=result
            )
            handler(task)
        return True

    def fail_task(self, task_id: str, error: str = "") -> bool:
        task_info = self._scheduler.get_task(task_id)
        if not task_info:
            return False

        task_info.metadata["retry_count"] = task_info.metadata.get("retry_count", 0) + 1
        if task_info.metadata["retry_count"] <= self.config.retry_count:
            self._task_stages[task_id] = TaskStage.PENDING
            self._log_event(
                "task_retry", task_id=task_id, retry=task_info.metadata["retry_count"]
            )
            return True

        self._scheduler.fail_task(task_id)
        self._task_stages[task_id] = TaskStage.FAILED
        self._log_event("task_failed", task_id=task_id, error=error)
        return True

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        task_info = self._scheduler.get_task(task_id)
        if not task_info:
            return None
        return {
            "task_id": task_id,
            "name": task_info.name,
            "stage": self._task_stages.get(task_id, TaskStage.PENDING).value,
            "assigned_agent": task_info.assigned_agent,
            "priority": task_info.priority,
            "dependencies": list(self._task_dependencies.get(task_id, set())),
        }

    def get_pipeline_status(self) -> dict[str, Any]:
        stage_counts: dict[str, int] = {}
        for stage in self._task_stages.values():
            stage_counts[stage.value] = stage_counts.get(stage.value, 0) + 1

        return {
            "engine_status": self.status.value,
            "total_tasks": len(self._task_stages),
            "stage_distribution": stage_counts,
            "pending_assignments": stage_counts.get("pending", 0),
        }

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append(
            {
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            }
        )


class SwarmEngine:
    """蜂群引擎 — 委托给 L0 SwarmManager + CollectiveDecision + EmergenceDetector

    L2 引擎面: 管理蜂群智能的完整运行时
    """

    def __init__(self, config: EngineConfig):
        from ecos.l0.governance import (
            CollectiveDecision,
            EmergenceDetector,
            SwarmManager,
        )

        self.config = config
        self.status = EngineStatus.IDLE

        self._swarm = SwarmManager()
        self._decision = CollectiveDecision()
        self._detector = EmergenceDetector()

        self._event_log: list[dict[str, Any]] = []

    def start(self) -> bool:
        self.status = EngineStatus.RUNNING
        self._log_event("swarm_started")
        return True

    def stop(self) -> bool:
        self.status = EngineStatus.STOPPED
        self._log_event("swarm_stopped")
        return True

    def register_agent(
        self, agent_id: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        self._swarm.add_agent(agent_id, initial_state=metadata)
        self._log_event("agent_registered", agent_id=agent_id)
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        return self._swarm.remove_agent(agent_id)

    def update_agent_state(self, agent_id: str, state: dict[str, Any]) -> bool:
        return self._swarm.update_agent_state(agent_id, state)

    def detect_emergence(self) -> list[dict[str, Any]]:
        state = self._swarm.get_swarm_state()
        l0_behaviors = self._swarm.detect_emergence(state)
        detected = [b.to_dict() for b in l0_behaviors]
        self._log_event("emergence_detected", patterns=[d["pattern"] for d in detected])
        return detected

    def propose_decision(
        self,
        proposal_id: str,
        title: str,
        options: list[str],
        method: str = "majority_vote",
    ) -> dict[str, Any]:
        from ecos.l0.governance import DecisionMethod

        method_map = {
            "majority_vote": DecisionMethod.MAJORITY_VOTE,
            "weighted_vote": DecisionMethod.WEIGHTED_VOTE,
            "consensus": DecisionMethod.CONSENSUS,
            "leader": DecisionMethod.LEADER,
            "pheromone": DecisionMethod.PHEROMONE,
        }
        dm = method_map.get(method, DecisionMethod.MAJORITY_VOTE)
        proposal = self._decision.create_proposal(proposal_id, title, options, dm)
        self._log_event("decision_proposed", proposal_id=proposal_id)
        return {
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "options": proposal.options,
            "method": method,
            "status": proposal.status,
        }

    def vote(self, proposal_id: str, agent_id: str, option: str) -> bool:
        return self._decision.vote(proposal_id, agent_id, option)

    def resolve_decision(self, proposal_id: str) -> Optional[str]:
        result = self._decision.decide(proposal_id)
        if result:
            self._log_event("decision_resolved", proposal_id=proposal_id, result=result)
        return result

    def get_swarm_status(self) -> dict[str, Any]:
        metrics = self._swarm.get_metrics()

        pending = len(self._decision.get_pending_proposals())

        return {
            "engine_status": self.status.value,
            "agent_count": metrics["agent_count"],
            "behavior_count": metrics["behavior_count"],
            "pattern_distribution": metrics["pattern_distribution"],
            "pending_decisions": pending,
        }

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append(
            {
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            }
        )


class PersonalEngine:
    """个人知识引擎 — 委托给 L0 PersonalKnowledgeManager + KnowledgeGraphBuilder + RecommendationEngine

    L2 引擎面: 管理个人知识的完整运行时
    """

    def __init__(self, config: EngineConfig):
        from ecos.l0.governance import (
            KnowledgeGraphBuilder,
            PersonalKnowledgeManager,
            PreferenceEngine,
            RecommendationEngine,
        )

        self.config = config
        self.status = EngineStatus.IDLE

        self._km = PersonalKnowledgeManager()
        self._pe = PreferenceEngine()
        self._graph = KnowledgeGraphBuilder()
        self._rec_engine: Optional[RecommendationEngine] = None

        self._event_log: list[dict[str, Any]] = []

    def _ensure_rec_engine(self) -> None:
        if self._rec_engine is None:
            from ecos.l0.governance import RecommendationEngine

            self._rec_engine = RecommendationEngine(self._km, self._pe)

    def start(self) -> bool:
        self.status = EngineStatus.RUNNING
        self._log_event("engine_started")
        return True

    def stop(self) -> bool:
        self.status = EngineStatus.STOPPED
        self._log_event("engine_stopped")
        return True

    def add_knowledge(
        self,
        key: str,
        content: dict[str, Any],
        tags: list[str] | None = None,
        relations: list[str] | None = None,
    ) -> bool:
        from ecos.l0.governance import KnowledgeNode, KnowledgeType

        node = KnowledgeNode(
            node_id=key,
            knowledge_type=KnowledgeType.FACT,
            content=content,
            tags=tags or [],
            relations=relations or [],
        )
        self._km.add_knowledge(node)
        self._graph.add_node(key, content)
        for rel in relations or []:
            self._graph.add_edge(key, rel, "related_to")
        self._log_event("knowledge_added", key=key)
        return True

    def remove_knowledge(self, key: str) -> bool:
        removed = self._km.remove_knowledge(key)
        if removed:
            self._graph.remove_node(key)
        return removed

    def query_knowledge(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        nodes = self._km.query_knowledge(query, limit)
        return [
            {"key": n.node_id, "score": 1.0, "content": n.content, "tags": n.tags}
            for n in nodes
        ]

    def get_related_knowledge(self, key: str) -> list[str]:
        return self._km.get_related(key, depth=1)  # type: ignore[reportReturnType]

    def add_edge(self, source: str, target: str, relation: str = "related_to") -> None:
        self._graph.add_edge(source, target, relation)

    def learn_preference(self, user_id: str, key: str, score: float = 1.0) -> None:
        from ecos.l0.governance import PreferenceType, UserPreference

        pref = UserPreference(
            user_id=user_id,
            preference_type=PreferenceType.TOPIC,
            key=key,
            value=key,
            weight=score,
        )
        self._km.learn_preference(user_id, pref)
        self._pe.learn(user_id, key, key, score)

    def get_recommendations(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_rec_engine()
        recs = self._rec_engine.recommend(user_id, limit=limit)  # type: ignore[reportOptionalMemberAccess]
        return [{"key": r.node_id, "score": r.score, "reason": r.reason} for r in recs]

    def record_access(self, key: str, user_id: str = "") -> None:
        node = self._km.get_knowledge(key)
        if node:
            self._log_event("knowledge_accessed", key=key, user_id=user_id)

    def get_stats(self) -> dict[str, Any]:
        km_stats = self._km.get_stats()
        graph_stats = self._graph.get_stats()

        return {
            "engine_status": self.status.value,
            "knowledge_count": km_stats["node_count"],
            "edge_count": graph_stats["edge_count"],
            "total_tags": km_stats["total_tags"],
            "user_count": km_stats["user_count"],
        }

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append(
            {
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            }
        )
