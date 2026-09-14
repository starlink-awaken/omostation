"""
OntoDerive 共享常量
====================
消除各模块中硬编码的ID前缀模式和魔法数字。
"""

import re

# ── ID前缀 ──
ENTITY_PREFIXES = ("ORG-", "ROL-", "PRJ-", "POL-", "DAT-", "DOC-", "STD-")
FACT_PREFIXES = ("D-F", "P-F")
INFERENCE_PREFIX = "INF-"

# ── 编译正则 ──
RE_FACT_ID = re.compile(r"(D-F\d+|P-F\d+)")
RE_ENTITY_ID = re.compile(r"\*\*(ORG-[\w-]+|ROL-[\w-]+|PRJ-[\w-]+|DOC-[\w-]+|STD-[\w-]+)\*\*")
RE_IS_FACT_ID = re.compile(r"^(D-F|P-F)\d+")
RE_IS_ENTITY_PREFIX = re.compile(r"^(ORG|ROL|PRJ)-")

# ── V2扩展ID前缀 ──
V2_ID_PATTERNS = [
    "ORG-",
    "ROL-",
    "PRJ-",
    "POL-",
    "DAT-",
    "INF-",
    "INF-V2-",
    "ADR-",
    "DCH-",
    "DOC-",
    "STD-",
    "CON-",
    "IP",
    "T[0-7]",
    "F[1-8]",
    "H[1-6]",
    "META-",
    "LAYER-",
    "TH-",
    "LANG-",
    "ENG-",
    "FRM-",
    "BAY-",
    "PRIOR-",
    "POST-",
    "KQI-",
    "MEAS-",
]

# ── 置信度映射 ──
CONFIDENCE_MAP = {
    "fact": 0.95,
    "high": 0.92,
    "inference": 0.85,
    "medium": 0.70,
    "hypothesis": 0.50,
    "low": 0.30,
    "estimated": 0.25,
    "assumption": 0.10,
}

# ── 传播参数 ──
DIRECT_FACTOR = 0.90
INDIRECT_FACTOR = 0.80
MAX_ITERATIONS = 20
CONVERGENCE_EPSILON = 0.001

# ── KQI权重 ──
KQI_WEIGHTS = {
    "entropy": 0.25,
    "coverage": 0.25,
    "density": 0.20,
    "entities": 0.15,
    "schemes": 0.15,
}

# ── PID默认增益 ──
PID_DEFAULTS = {"kp": 1.0, "ki": 0.5, "kd": 0.5, "window": 5, "epsilon": 0.1}

# ── 分析引擎阈值 (v3.4) ──
CAPACITY_TIGHT = 90  # 产能利用率紧张阈值(%)
CAPACITY_EXCESS = 60  # 产能利用率过剩阈值(%)
DELIVERY_WARNING = 80  # 交付及时率告警阈值(%)
SEMANTIC_THRESHOLD = 0.15  # 语义匹配默认阈值
INCENTIVE_DISSIMILARITY = 0.30  # 激励冲突最小差异度
REMEDIATION_URGENT = 1.5  # 整改可行性紧急阈值(问题/人/月)
REMEDIATION_TIGHT = 1.0  # 整改可行性紧张阈值
DEFAULT_TEAM_SIZE = 4  # 默认合规团队人数
DEFAULT_MONTHS = 6  # 默认整改时间窗口(月)
