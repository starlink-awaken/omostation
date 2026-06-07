from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Swarm Emergence ≡ Module
# 内涵 ≝ {Swarm, Emergence}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SwarmEmergence)}
# 功能 ⊢ {Swarm_Emergence, Init_Swarm, Validate_Emergence}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import threading
import time
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class EmergentPattern:
    pattern_id: str
    pattern_type: str  # "clustering", "specialization", "oscillation", "cascade"
    agents_involved: list[str] = field(default_factory=list)
    confidence: float = 0.0
    first_detected: float = field(default_factory=time.time)
    observations: int = 1
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentEvent:
    agent_id: str
    event_type: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


class SwarmEmergenceMonitor:
    """Detects emergent behavioral patterns in multi-agent swarms."""

    PATTERN_THRESHOLD = 3  # Min observations to confirm a pattern

    def __init__(self) -> None:
        self._events: list[AgentEvent] = []
        self._patterns: dict[str, EmergentPattern] = {}
        self._agent_roles: dict[str, list[str]] = {}  # agent_id -> [role history]
        self._lock = threading.Lock()
        self._pattern_counter = 0

    def record_event(self, event: AgentEvent) -> None:
        with self._lock:
            self._events.append(event)
            self._agent_roles.setdefault(event.agent_id, []).append(event.event_type)

    def detect_clustering(self, min_cluster_size: int = 2) -> list[EmergentPattern]:
        """Detect agents converging on the same event types."""
        with self._lock:
            type_agents: dict[str, set[str]] = {}
            for e in self._events:
                type_agents.setdefault(e.event_type, set()).add(e.agent_id)
            patterns = []
            for etype, agents in type_agents.items():
                if len(agents) >= min_cluster_size:
                    self._pattern_counter += 1
                    pid = f"cluster-{self._pattern_counter}"
                    p = EmergentPattern(
                        pattern_id=pid,
                        pattern_type="clustering",
                        agents_involved=sorted(agents),
                        confidence=min(1.0, len(agents) / 5.0),
                        metadata={"event_type": etype},
                    )
                    self._patterns[pid] = p
                    patterns.append(p)
            return patterns

    def detect_specialization(self) -> list[EmergentPattern]:
        """Detect agents specializing in specific event types."""
        with self._lock:
            patterns = []
            for agent_id, roles in self._agent_roles.items():
                if len(roles) < 3:
                    continue
                counter = Counter(roles)
                most_common, count = counter.most_common(1)[0]
                ratio = count / len(roles)
                if ratio >= 0.7:
                    self._pattern_counter += 1
                    pid = f"spec-{self._pattern_counter}"
                    p = EmergentPattern(
                        pattern_id=pid,
                        pattern_type="specialization",
                        agents_involved=[agent_id],
                        confidence=ratio,
                        metadata={"specialized_in": most_common, "ratio": ratio},
                    )
                    self._patterns[pid] = p
                    patterns.append(p)
            return patterns

    def detect_cascade(self, time_window: float = 1.0) -> list[EmergentPattern]:
        """Detect rapid sequential events across different agents (cascade effect)."""
        with self._lock:
            if len(self._events) < 3:
                return []
            sorted_events = sorted(self._events, key=lambda e: e.timestamp)
            cascades = []
            i = 0
            while i < len(sorted_events) - 2:
                chain = [sorted_events[i]]
                agents_seen = {sorted_events[i].agent_id}
                j = i + 1
                while j < len(sorted_events):
                    if sorted_events[j].timestamp - chain[-1].timestamp > time_window:
                        break
                    if sorted_events[j].agent_id not in agents_seen:
                        chain.append(sorted_events[j])
                        agents_seen.add(sorted_events[j].agent_id)
                    j += 1
                if len(chain) >= 3:
                    self._pattern_counter += 1
                    pid = f"cascade-{self._pattern_counter}"
                    p = EmergentPattern(
                        pattern_id=pid,
                        pattern_type="cascade",
                        agents_involved=[e.agent_id for e in chain],
                        confidence=min(1.0, len(chain) / 5.0),
                        observations=len(chain),
                    )
                    self._patterns[pid] = p
                    cascades.append(p)
                i = j if j > i + 1 else i + 1
            return cascades

    def get_patterns(self) -> list[EmergentPattern]:
        with self._lock:
            return list(self._patterns.values())

    def get_pattern(self, pattern_id: str) -> EmergentPattern | None:
        with self._lock:
            return self._patterns.get(pattern_id)

    def get_agent_profile(self, agent_id: str) -> dict:
        with self._lock:
            roles = self._agent_roles.get(agent_id, [])
            counter = Counter(roles)
            return {
                "agent_id": agent_id,
                "total_events": len(roles),
                "event_distribution": dict(counter),
                "dominant_role": counter.most_common(1)[0][0] if counter else None,
            }

    def summary(self) -> dict:
        with self._lock:
            return {
                "total_events": len(self._events),
                "unique_agents": len(self._agent_roles),
                "detected_patterns": len(self._patterns),
                "by_type": Counter(p.pattern_type for p in self._patterns.values()),
            }
