"""L2 引擎面 — 协作引擎 + 蜂群引擎 + 个人知识引擎

基于 L0/L1 原语构建的引擎层组件：
- CollaborationEngine: 协作引擎 (任务编排 + 角色路由 + 超时重试)
- SwarmEngine: 蜂群引擎 (涌现检测 + 集体决策 + 自适应控制)
- PersonalEngine: 个人知识引擎 (知识图谱 + 偏好学习 + 智能推荐)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


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
    """协作引擎 — 任务编排 + 角色路由 + 超时重试 + DAG 依赖

    L2 引擎面: 管理多角色协作的完整运行时
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.status = EngineStatus.IDLE
        self.tasks: dict[str, OrchestrationTask] = {}
        self._agent_capabilities: dict[str, set[str]] = {}
        self._agent_load: dict[str, int] = {}
        self._task_dependencies: dict[str, set[str]] = {}
        self._completion_handlers: dict[str, Callable[[OrchestrationTask], None]] = {}
        self._event_log: list[dict[str, Any]] = []

    def start(self) -> bool:
        self.status = EngineStatus.RUNNING
        self._log_event("engine_started")
        return True

    def stop(self) -> bool:
        self.status = EngineStatus.STOPPED
        self._log_event("engine_stopped")
        return True

    def register_agent(self, agent_id: str, capabilities: list[str]) -> None:
        self._agent_capabilities[agent_id] = set(capabilities)
        self._agent_load.setdefault(agent_id, 0)

    def submit_task(self, task_id: str, name: str,
                    required_capabilities: list[str] | None = None,
                    priority: int = 0,
                    dependencies: list[str] | None = None) -> OrchestrationTask:
        task = OrchestrationTask(
            task_id=task_id,
            name=name,
            required_capabilities=required_capabilities or [],
            priority=priority,
        )
        self.tasks[task_id] = task
        if dependencies:
            self._task_dependencies[task_id] = set(dependencies)
        self._log_event("task_submitted", task_id=task_id, name=name)
        return task

    def set_dependency(self, task_id: str, depends_on: str) -> None:
        self._task_dependencies.setdefault(task_id, set()).add(depends_on)

    def on_complete(self, task_id: str, handler: Callable[[OrchestrationTask], None]) -> None:
        self._completion_handlers[task_id] = handler

    def auto_assign(self) -> list[tuple[str, str]]:
        """自动分配就绪任务给最佳 Agent"""
        assignments: list[tuple[str, str]] = []

        for task_id, task in self.tasks.items():
            if task.stage != TaskStage.PENDING:
                continue

            deps = self._task_dependencies.get(task_id, set())
            all_deps_done = all(
                self.tasks.get(d, OrchestrationTask(task_id=d, name="")).stage == TaskStage.DONE
                for d in deps
            )
            if not all_deps_done:
                continue

            agent = self._find_best_agent(task)
            if agent:
                task.assigned_agent = agent
                task.stage = TaskStage.PLANNING
                self._agent_load[agent] = self._agent_load.get(agent, 0) + 1
                assignments.append((task_id, agent))
                self._log_event("task_assigned", task_id=task_id, agent=agent)

        return assignments

    def start_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.stage != TaskStage.PLANNING:
            return False
        task.stage = TaskStage.EXECUTING
        task.started_at = datetime.now(timezone.utc)
        self._log_event("task_started", task_id=task_id)
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.stage != TaskStage.EXECUTING:
            return False
        task.stage = TaskStage.DONE
        task.result = result
        task.completed_at = datetime.now(timezone.utc)
        self._agent_load[task.assigned_agent] = max(
            0, self._agent_load.get(task.assigned_agent, 1) - 1
        )
        self._log_event("task_completed", task_id=task_id)

        handler = self._completion_handlers.get(task_id)
        if handler:
            handler(task)

        return True

    def fail_task(self, task_id: str, error: str = "") -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.retry_count += 1
        if task.retry_count <= self.config.retry_count:
            task.stage = TaskStage.PENDING
            task.assigned_agent = ""
            task.error = error
            self._log_event("task_retry", task_id=task_id, retry=task.retry_count)
            return True

        task.stage = TaskStage.FAILED
        task.error = error
        task.completed_at = datetime.now(timezone.utc)
        self._log_event("task_failed", task_id=task_id, error=error)
        return True

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "name": task.name,
            "stage": task.stage.value,
            "assigned_agent": task.assigned_agent,
            "retry_count": task.retry_count,
            "error": task.error,
            "dependencies": list(self._task_dependencies.get(task_id, set())),
        }

    def get_pipeline_status(self) -> dict[str, Any]:
        stage_counts: dict[str, int] = {}
        for task in self.tasks.values():
            stage_counts[task.stage.value] = stage_counts.get(task.stage.value, 0) + 1

        return {
            "engine_status": self.status.value,
            "total_tasks": len(self.tasks),
            "stage_distribution": stage_counts,
            "agent_load": dict(self._agent_load),
            "pending_assignments": sum(
                1 for t in self.tasks.values() if t.stage == TaskStage.PENDING
            ),
        }

    def _find_best_agent(self, task: OrchestrationTask) -> Optional[str]:
        candidates = []
        for agent_id, caps in self._agent_capabilities.items():
            if task.required_capabilities:
                if set(task.required_capabilities).issubset(caps):
                    candidates.append(agent_id)
            else:
                candidates.append(agent_id)

        if not candidates:
            return None

        candidates.sort(key=lambda a: self._agent_load.get(a, 0))
        return candidates[0]

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append({
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })


class SwarmEngine:
    """蜂群引擎 — 涌现检测 + 集体决策 + 自适应控制

    L2 引擎面: 管理蜂群智能的完整运行时
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.status = EngineStatus.IDLE
        self.agents: dict[str, dict[str, Any]] = {}
        self._behaviors: list[dict[str, Any]] = []
        self._decisions: list[dict[str, Any]] = []
        self._event_log: list[dict[str, Any]] = []

    def start(self) -> bool:
        self.status = EngineStatus.RUNNING
        self._log_event("swarm_started")
        return True

    def stop(self) -> bool:
        self.status = EngineStatus.STOPPED
        self._log_event("swarm_stopped")
        return True

    def register_agent(self, agent_id: str, metadata: dict[str, Any] | None = None) -> bool:
        self.agents[agent_id] = metadata or {}
        self._log_event("agent_registered", agent_id=agent_id)
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            self._log_event("agent_unregistered", agent_id=agent_id)
            return True
        return False

    def update_agent_state(self, agent_id: str, state: dict[str, Any]) -> bool:
        if agent_id in self.agents:
            self.agents[agent_id].update(state)
            return True
        return False

    def detect_emergence(self) -> list[dict[str, Any]]:
        agent_ids = list(self.agents.keys())
        detected: list[dict[str, Any]] = []

        if len(agent_ids) >= 3:
            detected.append({
                "pattern": "clustering",
                "agents": agent_ids[:3],
                "confidence": min(0.5 + len(agent_ids) * 0.05, 0.95),
            })

        roles: dict[str, list[str]] = {}
        for aid, state in self.agents.items():
            role = state.get("role", "general")
            roles.setdefault(role, []).append(aid)

        if len(roles) >= 2:
            detected.append({
                "pattern": "specialization",
                "agents": agent_ids,
                "confidence": min(0.4 + len(roles) * 0.15, 0.9),
                "role_diversity": len(roles),
            })

        self._behaviors.extend(detected)
        self._log_event("emergence_detected", patterns=[d["pattern"] for d in detected])
        return detected

    def propose_decision(self, proposal_id: str, title: str,
                         options: list[str], method: str = "majority_vote") -> dict[str, Any]:
        proposal = {
            "proposal_id": proposal_id,
            "title": title,
            "options": options,
            "method": method,
            "votes": {},
            "status": "pending",
            "result": None,
        }
        self._decisions.append(proposal)
        self._log_event("decision_proposed", proposal_id=proposal_id)
        return proposal

    def vote(self, proposal_id: str, agent_id: str, option: str) -> bool:
        for proposal in self._decisions:
            if proposal["proposal_id"] == proposal_id:
                if option in proposal["options"]:
                    proposal["votes"][agent_id] = option
                    return True
        return False

    def resolve_decision(self, proposal_id: str) -> Optional[str]:
        for proposal in self._decisions:
            if proposal["proposal_id"] != proposal_id:
                continue

            votes = proposal["votes"]
            if not votes:
                return None

            if proposal["method"] == "majority_vote":
                counts: dict[str, int] = {}
                for vote in votes.values():
                    counts[vote] = counts.get(vote, 0) + 1

                total = sum(counts.values())
                winner = max(counts, key=lambda k: counts[k])
                if counts[winner] > total / 2:
                    proposal["result"] = winner
                    proposal["status"] = "resolved"
                    self._log_event("decision_resolved",
                                    proposal_id=proposal_id, result=winner)
                    return winner

            elif proposal["method"] == "consensus":
                unique = set(votes.values())
                if len(unique) == 1:
                    result = unique.pop()
                    proposal["result"] = result
                    proposal["status"] = "resolved"
                    self._log_event("decision_resolved",
                                    proposal_id=proposal_id, result=result)
                    return result

        return None

    def get_swarm_status(self) -> dict[str, Any]:
        role_dist: dict[str, int] = {}
        for state in self.agents.values():
            role = state.get("role", "general")
            role_dist[role] = role_dist.get(role, 0) + 1

        pattern_dist: dict[str, int] = {}
        for b in self._behaviors:
            p = b["pattern"]
            pattern_dist[p] = pattern_dist.get(p, 0) + 1

        return {
            "engine_status": self.status.value,
            "agent_count": len(self.agents),
            "role_distribution": role_dist,
            "behavior_count": len(self._behaviors),
            "pattern_distribution": pattern_dist,
            "pending_decisions": sum(
                1 for d in self._decisions if d["status"] == "pending"
            ),
        }

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append({
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })


class PersonalEngine:
    """个人知识引擎 — 知识图谱 + 偏好学习 + 智能推荐

    L2 引擎面: 管理个人知识的完整运行时
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.status = EngineStatus.IDLE
        self.knowledge: dict[str, dict[str, Any]] = {}
        self._edges: list[tuple[str, str, str]] = []
        self._user_preferences: dict[str, dict[str, float]] = {}
        self._access_log: list[dict[str, Any]] = []
        self._event_log: list[dict[str, Any]] = []

    def start(self) -> bool:
        self.status = EngineStatus.RUNNING
        self._log_event("engine_started")
        return True

    def stop(self) -> bool:
        self.status = EngineStatus.STOPPED
        self._log_event("engine_stopped")
        return True

    def add_knowledge(self, key: str, content: dict[str, Any],
                      tags: list[str] | None = None, relations: list[str] | None = None) -> bool:
        self.knowledge[key] = {
            "content": content,
            "tags": tags or [],
            "access_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for rel in (relations or []):
            self._edges.append((key, rel, "related_to"))
        self._log_event("knowledge_added", key=key)
        return True

    def remove_knowledge(self, key: str) -> bool:
        if key in self.knowledge:
            del self.knowledge[key]
            self._edges = [(s, t, r) for s, t, r in self._edges if s != key and t != key]
            return True
        return False

    def query_knowledge(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for key, data in self.knowledge.items():
            content_text = " ".join(str(v) for v in data["content"].values()).lower()
            tags_text = " ".join(data.get("tags", [])).lower()
            combined = f"{key} {content_text} {tags_text}".lower()

            score = 0.0
            for term in query_lower.split():
                if term in combined:
                    score += 1.0
                    if term in key.lower():
                        score += 0.5

            if score > 0:
                results.append({"key": key, "score": score, **data})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_related_knowledge(self, key: str) -> list[str]:
        related = []
        for src, tgt, _ in self._edges:
            if src == key:
                related.append(tgt)
            elif tgt == key:
                related.append(src)
        return list(set(related))

    def add_edge(self, source: str, target: str, relation: str = "related_to") -> None:
        self._edges.append((source, target, relation))

    def learn_preference(self, user_id: str, key: str, score: float = 1.0) -> None:
        if user_id not in self._user_preferences:
            self._user_preferences[user_id] = {}
        current = self._user_preferences[user_id].get(key, 0.0)
        self._user_preferences[user_id][key] = current + score

    def get_recommendations(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        prefs = self._user_preferences.get(user_id, {})
        if not prefs:
            recent = sorted(
                self.knowledge.items(),
                key=lambda x: x[1].get("created_at", ""),
                reverse=True,
            )
            return [{"key": k, "score": 0.5, "reason": "recent"} for k, _ in recent[:limit]]

        scored: list[tuple[str, float]] = []
        for key, data in self.knowledge.items():
            score = 0.0
            content_text = " ".join(str(v) for v in data["content"].values()).lower()
            for pref_key, pref_weight in prefs.items():
                if pref_key.lower() in content_text:
                    score += pref_weight
            if score > 0:
                scored.append((key, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {"key": k, "score": s, "reason": "preference_match"}
            for k, s in scored[:limit]
        ]

    def record_access(self, key: str, user_id: str = "") -> None:
        if key in self.knowledge:
            self.knowledge[key]["access_count"] = self.knowledge[key].get("access_count", 0) + 1
            self._access_log.append({
                "key": key,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_stats(self) -> dict[str, Any]:
        total_access = sum(d.get("access_count", 0) for d in self.knowledge.values())
        tag_counts: dict[str, int] = {}
        for data in self.knowledge.values():
            for tag in data.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "engine_status": self.status.value,
            "knowledge_count": len(self.knowledge),
            "edge_count": len(self._edges),
            "total_access": total_access,
            "user_count": len(self._user_preferences),
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        self._event_log.append({
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })
