"""Symphony Protocol agent matcher — capability-weighted task-to-agent matching.

Adapted from SharedBrain D_Execution symphony/agent_matcher.py.
All CoreService dependencies removed; uses standalone classes.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .models import (
    AgentCapability,
    AgentProfile,
    MatchResult,
    TaskRequirement,
)

logger = logging.getLogger(__name__)


class AgentMatcher:
    """Agent capability matching engine with multi-objective optimization.

    Strategy weights:
    - Capability match: 42%
    - Historical performance: 18%
    - Load balance: 15%
    - Specialization: 10%
    - Reputation: 15%
    """

    def __init__(self, intervention_weight: float = 0.0) -> None:
        self._score_weights = {
            "capability": 0.42,
            "performance": 0.18,
            "load": 0.15,
            "specialization": 0.10,
            "reputation": 0.15,
        }
        self._reputation_ledger: Any = None
        self._reputation_cache: dict[str, float] = {}
        self._reputation_cache_time: float = 0.0
        self._reputation_cache_ttl: float = 5.0
        self._intervention_weight = max(0.0, min(1.0, intervention_weight))

    def set_intervention_weight(self, weight: float) -> None:
        self._intervention_weight = max(0.0, min(1.0, weight))

    def set_reputation_source(self, reputation_ledger: Any) -> None:
        self._reputation_ledger = reputation_ledger
        self._reputation_cache.clear()

    def _preload_reputations(self, agent_ids: list[str]) -> None:
        if self._reputation_ledger is None or not agent_ids:
            return
        now = time.time()
        if self._reputation_cache and (now - self._reputation_cache_time) < self._reputation_cache_ttl:
            return
        try:
            all_nodes = self._reputation_ledger.list_all_nodes(sort_by="node_id")  # type: ignore[union-attr]
            self._reputation_cache = {node["node_id"]: node["reputation"] for node in all_nodes}
            self._reputation_cache_time = now
        except Exception:
            self._reputation_cache = {}

    def apply_task_degradation(self, task: TaskRequirement) -> TaskRequirement:
        if self._intervention_weight < 0.3:
            return task
        complexity = task.complexity
        if self._intervention_weight > 0.7 and complexity >= 7:
            return TaskRequirement(
                task_id=task.task_id,
                required_capabilities=task.required_capabilities,
                complexity=task.complexity,
                priority=1,
            )
        if self._intervention_weight > 0.5 and complexity >= 5:
            return TaskRequirement(
                task_id=task.task_id,
                required_capabilities=task.required_capabilities,
                complexity=task.complexity,
                priority=max(1, task.priority - 2),
            )
        if complexity >= 3:
            return TaskRequirement(
                task_id=task.task_id,
                required_capabilities=task.required_capabilities,
                complexity=task.complexity,
                priority=max(1, task.priority - 1),
            )
        return task

    def match(self, task: TaskRequirement, agents: list[AgentProfile]) -> tuple[AgentProfile, MatchResult]:
        if not agents:
            raise ValueError("agent pool is empty")

        adjusted_task = self.apply_task_degradation(task)
        agent_ids = [agent.agent_id for agent in agents]
        self._preload_reputations(agent_ids)

        filtered_agents = agents
        if self._reputation_ledger is not None:
            filtered_agents = []
            for agent in agents:
                if self._reputation_ledger.is_node_circuit_open(agent.agent_id):  # type: ignore[union-attr]
                    continue
                filtered_agents.append(agent)

        if not filtered_agents:
            raise ValueError("all agents isolated by circuit breaker")

        scores: list[tuple[AgentProfile, float, dict[str, float]]] = []
        for agent in filtered_agents:
            score, breakdown = self._calculate_match_score(adjusted_task, agent)
            scores.append((agent, score, breakdown))

        scores.sort(key=lambda x: x[1], reverse=True)
        best_agent, best_score, best_breakdown = scores[0]

        result = MatchResult(
            task_id=adjusted_task.task_id,
            agent_id=best_agent.agent_id,
            score=best_score,
            score_breakdown=best_breakdown,
        )
        return best_agent, result

    def match_multiple(
        self, tasks: list[TaskRequirement], agents: list[AgentProfile], max_assignments_per_agent: int = 3
    ) -> dict[str, tuple[str, float]]:
        assignments: dict[str, tuple[str, float]] = {}
        agent_assignment_count: dict[str, int] = {a.agent_id: 0 for a in agents}
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)

        for task in sorted_tasks:
            available_agents = [a for a in agents if agent_assignment_count[a.agent_id] < max_assignments_per_agent]
            if not available_agents:
                continue
            adjusted_agents = self._adjust_for_load(available_agents, agent_assignment_count)
            agent, result = self.match(task, adjusted_agents)
            assignments[task.task_id] = (agent.agent_id, result.score)
            agent_assignment_count[agent.agent_id] += 1
            agent.current_load = agent_assignment_count[agent.agent_id] / max_assignments_per_agent

        return assignments

    def _adjust_for_load(self, agents: list[AgentProfile], assignment_count: dict[str, int]) -> list[AgentProfile]:
        adjusted = []
        for agent in agents:
            adjusted_agent = AgentProfile(
                agent_id=agent.agent_id,
                capabilities=agent.capabilities.copy(),
                historical_performance=agent.historical_performance.copy(),
                current_load=assignment_count.get(agent.agent_id, 0) / max(1, len(agents)),
                specialization=agent.specialization,
            )
            adjusted.append(adjusted_agent)
        return adjusted

    def _calculate_match_score(self, task: TaskRequirement, agent: AgentProfile) -> tuple[float, dict[str, float]]:
        capability_score = self._calculate_capability_score(task, agent)
        performance_score = self._calculate_performance_score(agent)
        load_score = 1.0 - agent.current_load
        specialization_score = self._calculate_specialization_score(task, agent)
        reputation_score = self._calculate_reputation_score(agent)

        total_score = (
            capability_score * self._score_weights["capability"]
            + performance_score * self._score_weights["performance"]
            + load_score * self._score_weights["load"]
            + specialization_score * self._score_weights["specialization"]
            + reputation_score * self._score_weights["reputation"]
        )

        return total_score, {
            "capability": capability_score,
            "performance": performance_score,
            "load": load_score,
            "specialization": specialization_score,
            "reputation": reputation_score,
        }

    def _calculate_capability_score(self, task: TaskRequirement, agent: AgentProfile) -> float:
        if not task.required_capabilities:
            return 0.5
        matching_scores = [agent.capabilities.get(cap, 0.0) for cap in task.required_capabilities]
        return sum(matching_scores) / len(matching_scores)

    @staticmethod
    def _calculate_performance_score(agent: AgentProfile) -> float:
        performance_data = agent.historical_performance
        if not performance_data:
            return 0.5
        avg_performance = sum(performance_data.values()) / len(performance_data)
        recent_tasks = list(performance_data.values())[-10:]
        if recent_tasks:
            trend_bonus = max(0, sum(recent_tasks) / len(recent_tasks) - avg_performance) * 0.2
        else:
            trend_bonus = 0.0
        return min(1.0, avg_performance + trend_bonus)

    @staticmethod
    def _calculate_specialization_score(task: TaskRequirement, agent: AgentProfile) -> float:
        if not agent.specialization:
            return 0.5
        task_domain = str(task.task_id).split("_")[0].lower()
        agent_domain = agent.specialization.lower()
        if task_domain == agent_domain:
            return 1.0
        if task_domain in agent_domain or agent_domain in task_domain:
            return 0.7
        return 0.3

    def _calculate_reputation_score(self, agent: AgentProfile) -> float:
        if self._reputation_ledger is None:
            return 0.5
        try:
            if agent.agent_id in self._reputation_cache:
                return self._reputation_cache[agent.agent_id]
            return self._reputation_ledger.get_reputation(agent.agent_id)  # type: ignore[union-attr]
        except Exception:
            return 0.5

    def get_agent_ranking(
        self, task: TaskRequirement, agents: list[AgentProfile]
    ) -> list[tuple[AgentProfile, float, dict[str, float]]]:
        rankings = [(agent, *self._calculate_match_score(task, agent)) for agent in agents]
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def get_capability_gap(self, task: TaskRequirement, agents: list[AgentProfile]) -> dict[AgentCapability, float]:
        gaps: dict[AgentCapability, float] = {}
        for capability in task.required_capabilities:
            max_capability = max((agent.capabilities.get(capability, 0.0) for agent in agents), default=0.0)
            gaps[capability] = 1.0 - max_capability
        return gaps
