"""Governance Coordinator — role-based voting, conflict detection, and multi-agent decision aggregation."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VoteType(Enum):
    GO = "go"
    NO_GO = "no-go"
    CONDITIONAL_GO = "conditional-go"
    ABSTAIN = "abstain"


class ConflictType(Enum):
    DIRECT = "direct-conflict"
    CONFIDENCE_GAP = "confidence-gap"
    LOGICAL = "logical-contradiction"
    SCOPE = "scope-mismatch"


class ConflictSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AggregationStrategy(Enum):
    SIMPLE_MAJORITY = "simple-majority"
    WEIGHTED = "weighted-majority"
    UNANIMITY = "unanimity"
    CONFIDENCE = "confidence-weighted"
    SUPER_MAJORITY = "super-majority"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class GovernanceAgent:
    """An agent with voting weight."""

    id: str
    name: str = ""
    weight: float = 1.0
    enabled: bool = True


@dataclass
class GovernanceVote:
    agent_id: str
    type: VoteType = VoteType.ABSTAIN
    confidence: float = 0.5
    reasoning: str = ""
    timestamp: float = 0.0


@dataclass
class GovernanceConflict:
    id: str = ""
    type: ConflictType = ConflictType.DIRECT
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    agents: list[str] = field(default_factory=list)
    description: str = ""
    timestamp: float = 0.0


@dataclass
class GovernanceDecision:
    id: str = ""
    project_id: str = ""
    decision_id: str = ""
    type: VoteType = VoteType.NO_GO
    confidence: float = 0.0
    go_votes: int = 0
    no_go_votes: int = 0
    conditional_votes: int = 0
    abstain_votes: int = 0
    reasoning: str = ""
    timestamp: float = 0.0
    conflicts: list[GovernanceConflict] = field(default_factory=list)


@dataclass
class ConflictResolution:
    resolved: bool = False
    requires_human: bool = False
    decision: GovernanceDecision | None = None
    message: str = ""


@dataclass
class CoordinatorConfig:
    agents: list[GovernanceAgent] = field(default_factory=list)
    strategy: AggregationStrategy = AggregationStrategy.WEIGHTED
    conflict_threshold: float = 0.3
    super_majority_threshold: float = 2.0 / 3.0
    max_conflict_history: int = 100


@dataclass
class CoordinatorStats:
    total_decisions: int = 0
    total_votes: int = 0
    total_conflicts: int = 0
    human_intervention_count: int = 0


# ---------------------------------------------------------------------------
# GovernanceCoordinator
# ---------------------------------------------------------------------------


class GovernanceCoordinator:
    """Coordinates governance across agents: voting, conflict detection, and aggregation."""

    def __init__(self, config: CoordinatorConfig | None = None) -> None:
        self._config = config or CoordinatorConfig()
        self._agents: dict[str, GovernanceAgent] = {}
        self._votes: dict[str, dict[str, list[GovernanceVote]]] = {}  # project_id -> decision_id -> votes
        self._decisions: dict[str, dict[str, GovernanceDecision]] = {}
        self._conflicts: dict[str, list[GovernanceConflict]] = {}
        self._conflict_history: list[GovernanceConflict] = []
        self._strategy = self._config.strategy

        for agent in self._config.agents:
            self._agents[agent.id] = GovernanceAgent(**{**agent.__dict__})

    # -- Agent management ----------------------------------------------------

    def get_agent(self, agent_id: str) -> GovernanceAgent | None:
        return self._agents.get(agent_id)

    def set_weight(self, agent_id: str, weight: float) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.weight = weight
        return True

    def set_enabled(self, agent_id: str, enabled: bool) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.enabled = enabled
        return True

    def all_agents(self) -> list[GovernanceAgent]:
        return list(self._agents.values())

    # -- Voting --------------------------------------------------------------

    def submit_vote(self, project_id: str, decision_id: str, vote: GovernanceVote) -> dict[str, Any]:
        agent = self._agents.get(vote.agent_id)
        if agent is None:
            return {"success": False, "error": f"Unknown agent: {vote.agent_id}"}
        if not agent.enabled:
            return {"success": False, "error": f"Agent disabled: {vote.agent_id}"}
        if not (0 <= vote.confidence <= 1):
            return {"success": False, "error": "Confidence must be 0-1"}

        self._votes.setdefault(project_id, {}).setdefault(decision_id, [])
        votes = self._votes[project_id][decision_id]

        existing = next((i for i, v in enumerate(votes) if v.agent_id == vote.agent_id), None)
        vote.timestamp = time.time()
        if existing is not None:
            votes[existing] = vote
        else:
            votes.append(vote)

        # Clear cached decision
        if project_id in self._decisions:
            self._decisions[project_id].pop(decision_id, None)

        return {"success": True, "vote_id": uuid.uuid4().hex[:12]}

    def get_votes(self, project_id: str, decision_id: str) -> list[GovernanceVote]:
        return list(self._votes.get(project_id, {}).get(decision_id, []))

    def is_voting_complete(self, project_id: str, decision_id: str) -> bool:
        votes = self.get_votes(project_id, decision_id)
        enabled_agents = [a for a in self._agents.values() if a.enabled]
        return all(any(v.agent_id == a.id for v in votes) for a in enabled_agents)

    # -- Conflict detection --------------------------------------------------

    def detect_conflicts(self, project_id: str, decision_id: str) -> list[GovernanceConflict]:
        votes = self.get_votes(project_id, decision_id)
        conflicts: list[GovernanceConflict] = []

        if len(votes) < 2:
            return conflicts

        go_votes = [v for v in votes if v.type == VoteType.GO]
        no_go_votes = [v for v in votes if v.type == VoteType.NO_GO]

        # Direct conflict (GO vs NO_GO)
        if go_votes and no_go_votes:
            avg_go = sum(v.confidence for v in go_votes) / len(go_votes)
            avg_no = sum(v.confidence for v in no_go_votes) / len(no_go_votes)
            combined = (avg_go + avg_no) / 2

            severity = ConflictSeverity.CRITICAL if combined > 0.85 else (
                ConflictSeverity.HIGH if combined > 0.7 else (
                    ConflictSeverity.MEDIUM if combined > 0.5 else ConflictSeverity.LOW
                )
            )

            conflicts.append(GovernanceConflict(
                id=uuid.uuid4().hex[:12],
                type=ConflictType.DIRECT,
                severity=severity,
                agents=[v.agent_id for v in go_votes + no_go_votes],
                description=f"{len(go_votes)} GO vs {len(no_go_votes)} NO_GO",
                timestamp=time.time(),
            ))
            self._record_conflicts(project_id, conflicts)
            return conflicts

        # Confidence gap
        confidences = [v.confidence for v in votes]
        gap = max(confidences) - min(confidences)
        if gap > self._config.conflict_threshold:
            conflicts.append(GovernanceConflict(
                id=uuid.uuid4().hex[:12],
                type=ConflictType.CONFIDENCE_GAP,
                severity=ConflictSeverity.HIGH if gap > 0.5 else ConflictSeverity.MEDIUM,
                agents=[v.agent_id for v in votes],
                description=f"Confidence gap: {gap:.1%}",
                timestamp=time.time(),
            ))

        if conflicts:
            self._record_conflicts(project_id, conflicts)

        return conflicts

    # -- Decision aggregation ------------------------------------------------

    def aggregate_decision(self, project_id: str, decision_id: str) -> GovernanceDecision:
        cached = self._decisions.get(project_id, {}).get(decision_id)
        if cached is not None:
            return cached

        votes = self.get_votes(project_id, decision_id)
        weighted_votes = self._get_weighted_votes(votes)
        conflicts = self.detect_conflicts(project_id, decision_id)

        go_count = sum(1 for v in votes if v.type == VoteType.GO)
        no_count = sum(1 for v in votes if v.type == VoteType.NO_GO)
        cond_count = sum(1 for v in votes if v.type == VoteType.CONDITIONAL_GO)
        abstain_count = sum(1 for v in votes if v.type == VoteType.ABSTAIN)

        result = self._aggregate_by_strategy(votes, weighted_votes)

        decision = GovernanceDecision(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            decision_id=decision_id,
            type=result["type"],
            confidence=result["confidence"],
            go_votes=go_count,
            no_go_votes=no_count,
            conditional_votes=cond_count,
            abstain_votes=abstain_count,
            reasoning=result["reasoning"],
            timestamp=time.time(),
            conflicts=conflicts,
        )

        self._decisions.setdefault(project_id, {})[decision_id] = decision
        return decision

    def resolve_conflict(self, project_id: str, decision_id: str) -> ConflictResolution:
        conflicts = self.detect_conflicts(project_id, decision_id)
        if not conflicts:
            decision = self.aggregate_decision(project_id, decision_id)
            return ConflictResolution(resolved=True, decision=decision, message="No conflicts")

        high_severity = any(c.severity in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL) for c in conflicts)
        if high_severity:
            return ConflictResolution(resolved=False, requires_human=True, message="High severity conflicts require human intervention")

        decision = self.aggregate_decision(project_id, decision_id)
        return ConflictResolution(resolved=True, decision=decision, message=f"Auto-resolved {len(conflicts)} conflict(s)")

    def get_conflict_history(self, project_id: str | None = None) -> list[GovernanceConflict]:
        if project_id:
            return list(self._conflicts.get(project_id, []))
        return list(self._conflict_history)

    # -- Stats ---------------------------------------------------------------

    def get_stats(self) -> CoordinatorStats:
        total_decisions = 0
        total_votes = 0
        for proj_votes in self._votes.values():
            for dec_votes in proj_votes.values():
                total_votes += len(dec_votes)
                total_decisions += 1
        total_conflicts = len(self._conflict_history)
        human_count = sum(1 for c in self._conflict_history if c.severity in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL))
        return CoordinatorStats(total_decisions=total_decisions, total_votes=total_votes, total_conflicts=total_conflicts, human_intervention_count=human_count)

    def should_alert_guardian(self) -> bool:
        stats = self.get_stats()
        if stats.total_decisions == 0:
            return False
        conflict_rate = stats.total_conflicts / stats.total_decisions
        return conflict_rate > 0.3 or stats.human_intervention_count > 0

    # -- Data management -----------------------------------------------------

    def clear_votes(self, project_id: str, decision_id: str) -> None:
        self._votes.get(project_id, {}).pop(decision_id, None)
        self._decisions.get(project_id, {}).pop(decision_id, None)

    def clear_project(self, project_id: str) -> None:
        self._votes.pop(project_id, None)
        self._decisions.pop(project_id, None)
        self._conflicts.pop(project_id, None)

    # -- Strategy implementations --------------------------------------------

    def _aggregate_by_strategy(self, votes: list[GovernanceVote], weighted: list[tuple[GovernanceVote, float]]) -> dict[str, Any]:
        go = sum(1 for v in votes if v.type == VoteType.GO)
        no = sum(1 for v in votes if v.type == VoteType.NO_GO)
        cond = sum(1 for v in votes if v.type == VoteType.CONDITIONAL_GO)

        if self._strategy == AggregationStrategy.UNANIMITY:
            total = len(votes)
            if total > 0 and go == total:
                return {"type": VoteType.GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.GO]), "reasoning": "Unanimity: all GO"}
            if total > 0 and no == total:
                return {"type": VoteType.NO_GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.NO_GO]), "reasoning": "Unanimity: all NO_GO"}
            if total > 0:
                return {"type": VoteType.CONDITIONAL_GO, "confidence": 0.5, "reasoning": "Unanimity: disagreement, requires review"}
            return {"type": VoteType.NO_GO, "confidence": 0, "reasoning": "No votes"}

        if self._strategy == AggregationStrategy.CONFIDENCE:
            conf_sums: dict[VoteType, float] = {}
            for v in votes:
                conf_sums[v.type] = conf_sums.get(v.type, 0) + v.confidence
            best = max(conf_sums, key=lambda k: conf_sums[k]) if conf_sums else VoteType.NO_GO
            count = sum(1 for v in votes if v.type == best)
            return {"type": best, "confidence": conf_sums.get(best, 0) / count if count > 0 else 0, "reasoning": f"Confidence-weighted: {best.value}"}

        if self._strategy == AggregationStrategy.SUPER_MAJORITY:
            threshold = self._config.super_majority_threshold
            total = len(votes)
            if total > 0 and go / total >= threshold:
                return {"type": VoteType.GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.GO]), "reasoning": f"Super-majority GO ({go}/{total})"}
            if total > 0 and no / total >= threshold:
                return {"type": VoteType.NO_GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.NO_GO]), "reasoning": f"Super-majority NO_GO ({no}/{total})"}
            # Fall through to simple majority

        # Simple majority (also fallback for super-majority)
        max_count = max(go, no, cond)
        if go == max_count:
            return {"type": VoteType.GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.GO]), "reasoning": f"Simple majority: {go} GO"}
        if cond == max_count:
            return {"type": VoteType.CONDITIONAL_GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.CONDITIONAL_GO]), "reasoning": f"Simple majority: {cond} conditional"}
        return {"type": VoteType.NO_GO, "confidence": self._avg_conf([v for v in votes if v.type == VoteType.NO_GO]), "reasoning": f"Simple majority: {no} NO_GO"}

    # -- Helper methods ------------------------------------------------------

    def _get_weighted_votes(self, votes: list[GovernanceVote]) -> list[tuple[GovernanceVote, float]]:
        result: list[tuple[GovernanceVote, float]] = []
        for v in votes:
            agent = self._agents.get(v.agent_id)
            weight = agent.weight if agent else 1.0
            result.append((v, weight))
        return result

    @staticmethod
    def _avg_conf(votes: list[GovernanceVote]) -> float:
        if not votes:
            return 0.0
        return sum(v.confidence for v in votes) / len(votes)

    def _record_conflicts(self, project_id: str, conflicts: list[GovernanceConflict]) -> None:
        self._conflicts.setdefault(project_id, [])
        for c in conflicts:
            if c.id not in {x.id for x in self._conflicts[project_id]}:
                self._conflicts[project_id].append(c)
                self._conflict_history.append(c)
                while len(self._conflict_history) > self._config.max_conflict_history:
                    self._conflict_history.pop(0)

    @staticmethod
    def create_default() -> GovernanceCoordinator:
        config = CoordinatorConfig(
            agents=[
                GovernanceAgent(id="gov-01", name="Quality Gate", weight=1.5),
                GovernanceAgent(id="gov-02", name="Security Reviewer", weight=1.3),
                GovernanceAgent(id="gov-03", name="Architecture Reviewer", weight=1.0),
            ],
        )
        return GovernanceCoordinator(config)
