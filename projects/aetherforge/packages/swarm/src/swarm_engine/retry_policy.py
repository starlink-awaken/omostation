from __future__ import annotations

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---
"""
---
Type: Engine Component
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: 'RetryPolicy — exponential backoff with jitter for Hatcher worker retries.'
Tags:
- retry
- backoff
- hatcher
- resilience
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Retry Policy ≡ Module
# 内涵 ≝ {Retry, Policy}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RetryPolicy)}
# 功能 ⊢ {Retry_Policy, Init_Retry, Validate_Policy}
# =============================================================================

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    """Configurable retry policy with exponential backoff and optional jitter.

    Parameters
    ----------
    max_attempts:
        Maximum number of retry attempts (excludes the initial attempt).
    backoff_base:
        Base for exponential delay calculation: ``backoff_base ** attempt``.
    max_delay:
        Hard upper bound on computed delay (seconds).
    jitter:
        When ``True``, multiply computed delay by ``uniform(0.5, 1.5)``
        to decorrelate concurrent retries.
    """

    max_attempts: int = 3
    backoff_base: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the backoff delay in seconds for the given attempt number.

        *attempt* is 1-based: attempt 1 is the first retry after the
        initial failure.
        """
        delay = min(self.backoff_base**attempt, self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)  # noqa: S311
        return delay


@dataclass
class RetryState:
    """Mutable per-worker retry tracking state."""

    attempt_count: int = 0
    last_error: str = ""
    next_retry_at: float = 0.0
    spore_config: dict = field(default_factory=dict)
    task_prompt: str = ""
    eu_budget: float = 0.0
    soul_context: dict | None = None

    @property
    def exhausted(self) -> bool:
        """Check exhaustion against a policy externally — convenience helper."""
        return False  # always checked via policy.max_attempts externally


class RetryExhaustedError(RuntimeError):
    """Raised when all retry attempts for a worker have been exhausted."""

    def __init__(self, worker_id: str, attempts: int, last_error: str) -> None:
        self.worker_id = worker_id
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Worker '{worker_id}' exhausted {attempts} retry attempts. Last error: {last_error}")


DEFAULT_RETRY_POLICY = RetryPolicy()
