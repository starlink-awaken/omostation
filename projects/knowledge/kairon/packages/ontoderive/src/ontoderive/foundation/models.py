"""
OntoDerive 数据模型
===================
dataclass 定义所有核心类型，消除各模块中 ad-hoc dict。
所有引擎模块从 models 导入，保证类型一致性。
"""

from dataclasses import dataclass, field

# ---- Type normalization (no external deps) ----
VALID_TYPES = [
    "domain",
    "data",
    "policy",
    "fact",
    "inference",
    "relation",
    "state",
    "document",
    "constraint",
    "processor",
]
VALID_TYPES_SET = set(VALID_TYPES)


def _normalize_type(t: str) -> str:
    """Normalize a type string. Unknown types default to 'domain'."""
    normalized = t.lower()
    return normalized if normalized in VALID_TYPES_SET else "domain"


def list_valid_types() -> list[str]:
    return list(VALID_TYPES)


@dataclass
class Fact:
    fid: str  # D-F1, P-F9 等
    description: str  # 事实描述
    value: str = ""  # 数值/内容
    source: str = ""  # 来源
    confidence: float = 0.95  # 置信度 [0,1]
    type: str = "data"  # data / policy

    def __post_init__(self) -> None:
        if hasattr(self, "type") and self.type:
            self.type = _normalize_type(str(self.type))


@dataclass
class Entity:
    eid: str  # ORG-xxx, ROL-xxx, PRJ-xxx
    name: str  # 实体名称
    entity_type: str  # Organization / Role / Project
    role: str = ""  # 角色描述
    count: str = ""  # 数量
    facts_ref: list[str] = field(default_factory=list)  # 引用的事实ID

    def __post_init__(self) -> None:
        self.entity_type = _normalize_type(self.entity_type)


@dataclass
class Inference:
    iid: str  # INF-L1, INF-V2-xxx
    title: str  # 推论标题
    derives_from: list[str] = field(default_factory=list)  # 前提事实/推论ID
    confidence: float = 0.85  # 置信度 [0,1]
    raw_confidence_label: str = "inference"  # 原始置信度标签
    meta_type: str = "inference"
    text: str = ""  # 推论全文
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.meta_type = _normalize_type(self.meta_type)


@dataclass
class Scheme:
    sid: str  # 方案ID
    title: str  # 方案标题
    assertions: list[str] = field(default_factory=list)  # 断言列表
    facts_refs: list[str] = field(default_factory=list)
    inferences_refs: list[str] = field(default_factory=list)
    meta_type: str = "document"
    file_path: str = ""  # 源文件路径

    def __post_init__(self) -> None:
        self.meta_type = _normalize_type(self.meta_type)


@dataclass
class CheckResult:
    pid: str  # C-01 ~ C-13
    name: str  # 检查项名称
    passed: bool  # 是否通过
    severity: str  # BLOCKER / ERROR / WARN / PASS
    detail: str  # 详细说明
    fixes: list[str] = field(default_factory=list)  # 修复建议
    file: str = ""  # 关联文件路径
    line: int = 0  # 关联行号


@dataclass
class DeriveSnapshot:
    timestamp: str  # ISO时间戳
    facts: int = 0  # 事实数
    entities: int = 0  # 实体数
    inferences: int = 0  # 推偶数
    scheme_files: int = 0  # 方案文件数
    metrics: dict | None = None  # KQI等指标(可选)
