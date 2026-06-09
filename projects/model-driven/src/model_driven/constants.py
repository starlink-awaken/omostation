"""model-driven 全局常量定义

集中管理所有魔法数字和业务阈值，避免散落在各处硬编码。
"""

# ── 健康分 ──────────────────────────────────────

MAX_HEALTH_SCORE: float = 100.0
HEALTH_RECOVERY_INCREMENT: float = 5.0
HEALTH_PENALTY_DECREMENT: float = 20.0
HEALTH_ISSUE_PENALTY: int = 10

# ── Trigger 阈值 ────────────────────────────────

HEALTHY_CONSECUTIVE_SUCCESSES: int = 3
DEGRADED_CONSECUTIVE_FAILURES: int = 3
STOPPED_CONSECUTIVE_FAILURES: int = 5
EVENT_BUS_QUEUE_THRESHOLD: int = 1000
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_DAEMON_INTERVAL: int = 21600  # 6h
DAEMON_STUCK_MULTIPLIER: int = 2

# ── 推导引擎 ────────────────────────────────────

DEFAULT_EXPECTED_PROGRESS: float = 0.5
DEFAULT_COVERAGE_THRESHOLD: float = 80.0

# ── OKR ─────────────────────────────────────────

PRIORITY_P0_THRESHOLD: float = 2.0
PRIORITY_P1_THRESHOLD: float = 1.0
PRIORITY_P2_THRESHOLD: float = 0.5
TASK_SPLIT_DIVISOR: int = 10

# ── 萃取信心 ────────────────────────────────────

LESSON_CONFIDENCE_DIVISOR: float = 5.0
DECISION_CONFIDENCE_DIVISOR: float = 3.0
SPEC_CONFIDENCE_DIVISOR: float = 2.0

# ── 时间 ────────────────────────────────────────

SECONDS_PER_DAY: float = 86400.0

# ── 百分比 ──────────────────────────────────────

PERCENT_MULTIPLIER: float = 100.0
