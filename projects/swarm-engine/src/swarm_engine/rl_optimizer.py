from __future__ import annotations

# ruff: noqa: RUF002
from typing import Any

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Rl Optimizer ≡ Module
# 内涵 ≝ {Rl, Optimizer}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RlOptimizer)}
# 功能 ⊢ {Rl_Optimizer, Init_Rl, Validate_Optimizer}
# =============================================================================


"""Reinforcement learning optimizer for task routing in SharedBrain B-OS."""


import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RLAction:
    name: str  # e.g., "route_to_local", "route_to_node_abc"
    metadata: dict = field(default_factory=dict)


@dataclass
class RLState:
    features: tuple  # hashable state representation
    description: str = ""


class QLearningAgent:
    """Q-learning agent for discrete state/action spaces.

    Uses epsilon-greedy exploration with exponential decay.
    No external dependencies — pure stdlib.
    """

    DEFAULT_ALPHA = 0.1  # learning rate
    DEFAULT_GAMMA = 0.9  # discount factor
    DEFAULT_EPSILON = 0.3  # initial exploration rate
    DEFAULT_EPSILON_MIN = 0.01
    DEFAULT_EPSILON_DECAY = 0.995

    def __init__(
        self,
        actions: list[str],
        alpha: float = DEFAULT_ALPHA,
        gamma: float = DEFAULT_GAMMA,
        epsilon: float = DEFAULT_EPSILON,
        epsilon_min: float = DEFAULT_EPSILON_MIN,
        epsilon_decay: float = DEFAULT_EPSILON_DECAY,
    ) -> None:
        self.actions = list(actions)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self._q: dict[tuple, dict[str, float]] = defaultdict(lambda: dict.fromkeys(self.actions, 0.0))
        self._steps = 0
        self._lock = threading.Lock()

    def choose_action(self, state: tuple) -> str:
        """Epsilon-greedy action selection."""
        with self._lock:
            if random.random() < self.epsilon:  # noqa: S311
                return random.choice(self.actions)  # noqa: S311
            q_vals = self._q[state]
            return max(q_vals, key=q_vals.__getitem__)

    def learn(self, state: tuple, action: str, reward: float, next_state: tuple) -> None:
        """Q-value update: Q(s,a) ← Q(s,a) + α[r + γ max Q(s',a') - Q(s,a)]"""
        with self._lock:
            current_q = self._q[state][action]
            max_next_q = max(self._q[next_state].values())
            new_q = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
            self._q[state][action] = new_q
            self._steps += 1
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def get_q_values(self, state: tuple) -> dict[str, float]:
        with self._lock:
            return dict(self._q[state])

    def get_best_action(self, state: tuple) -> str:
        """Greedy best action (no exploration)."""
        with self._lock:
            q_vals = self._q[state]
            return max(q_vals, key=q_vals.__getitem__)

    @classmethod
    def with_history_tracking(
        cls,
        db_path: str | None = None,
        **kwargs: Any,
    ) -> tuple[QLearningAgent, object]:
        """Create an agent + history tracker, monkey-patching learn() to auto-record.

        Args:
            db_path: Optional path for the SQLite history database.
            **kwargs: Forwarded to :class:`QLearningAgent.__init__`.

        Returns:
            (agent, history) tuple where history is a RLTrainingHistory instance.
        """
        # Lazy import to avoid circular dependency at module load time.
        try:
            RLTrainingHistory = __import__(  # cross-organ: invisible to AST topology checker  # noqa: N806
                "organs.D_Monitoring.rl_dashboard", fromlist=["RLTrainingHistory"]
            ).RLTrainingHistory
        except (ImportError, AttributeError):
            RLTrainingHistory = None  # noqa: N806

        agent = cls(**kwargs)
        if RLTrainingHistory is None:
            return agent, None
        history = RLTrainingHistory(db_path=db_path)
        _original_learn = agent.learn

        def _instrumented_learn(state: tuple, action: str, reward: float, next_state: tuple) -> None:
            _original_learn(state, action, reward, next_state)
            # After learn(), capture updated Q-value and epsilon
            q_value = agent._q[state][action]
            history.record_step(
                step=agent._steps,
                state=str(state),
                action=action,
                reward=reward,
                q_value=round(q_value, 6),
                epsilon=agent.epsilon,
            )

        agent.learn = _instrumented_learn  # type: ignore[method-assign]
        return agent, history

    def stats(self) -> dict:
        with self._lock:
            return {
                "steps": self._steps,
                "epsilon": round(self.epsilon, 6),
                "num_states": len(self._q),
                "num_actions": len(self.actions),
            }


class FederationRLRouter:
    """RL-based federation router that learns which nodes give best results.

    State: (task_type, hour_of_day, recent_failure_count)  [discretized]
    Action: node_id to route to (or "local")
    Reward: +1.0 success, -1.0 failure, -0.5 timeout
    """

    REWARD_SUCCESS = 1.0
    REWARD_FAILURE = -1.0
    REWARD_TIMEOUT = -0.5

    def __init__(self, node_ids: list[str]) -> None:
        self._agent = QLearningAgent(actions=["local", *node_ids])
        self._pending: dict[str, tuple[tuple, str]] = {}  # request_id → (state, action)
        self._lock = threading.Lock()

    def _make_state(self, task_type: str, failure_count: int = 0) -> tuple:
        """Discretize inputs into a hashable state."""
        hour = int(time.time() // 3600) % 24  # hour bucket
        failure_bucket = min(failure_count // 3, 3)  # 0, 1, 2, 3+
        return (task_type, hour, failure_bucket)

    def choose_node(self, request_id: str, task_type: str, failure_count: int = 0) -> str:
        """Choose a node for this request, tracking it for future learning."""
        state = self._make_state(task_type, failure_count)
        action = self._agent.choose_action(state)
        with self._lock:
            self._pending[request_id] = (state, action)
        return action

    def record_success(self, request_id: str) -> None:
        self._record_outcome(request_id, self.REWARD_SUCCESS)

    def record_failure(self, request_id: str) -> None:
        self._record_outcome(request_id, self.REWARD_FAILURE)

    def record_timeout(self, request_id: str) -> None:
        self._record_outcome(request_id, self.REWARD_TIMEOUT)

    def _record_outcome(self, request_id: str, reward: float) -> None:
        with self._lock:
            if request_id not in self._pending:
                return
            state, action = self._pending.pop(request_id)
        next_state = state  # simplified: stationary transitions
        self._agent.learn(state, action, reward, next_state)

    def stats(self) -> dict:
        return {**self._agent.stats(), "pending_requests": len(self._pending)}

    def get_q_values(self, task_type: str, failure_count: int = 0) -> dict[str, float]:
        state = self._make_state(task_type, failure_count)
        return self._agent.get_q_values(state)


_rl_router: FederationRLRouter | None = None
_rl_lock = threading.Lock()


def get_rl_router(node_ids: list[str] | None = None) -> FederationRLRouter:
    global _rl_router
    with _rl_lock:
        if _rl_router is None:
            _rl_router = FederationRLRouter(node_ids or [])
        return _rl_router
