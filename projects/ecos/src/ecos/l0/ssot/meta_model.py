"""
SSOT Kernel — meta_model.py
============================
元模型内核：8 类元实体（MET-Type）、4 类元关系（MET-Relation）、元约束。

这是整个 SSOT 唯一不依赖任何输入数据的模块——它定义的是"建模本身的规则"。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# ── 一、8 类元实体类型 ──────────────────────────────────────


class MetaType(enum.Enum):
    """8 类元实体类型（META-EntityType），定义自 06-元本体.md"""

    DOMAIN = "MET-DOMAIN"  # 领域实体：现实世界的"东西"
    FACT = "MET-FACT"  # 事实：可验证的客观陈述
    INFERENCE = "MET-INFERENCE"  # 推论：基于事实的推导
    STATE = "MET-STATE"  # 状态：系统行为节点
    DOCUMENT = "MET-DOCUMENT"  # 文档：知识呈现载体
    CONSTRAINT = "MET-CONSTRAINT"  # 约束：质量门禁
    PROCESSOR = "MET-PROCESSOR"  # 处理器：操作模型的模型
    RELATION = "MET-RELATION"  # 关系：连接实体的边

    @classmethod
    def from_str(cls, s: str) -> MetaType:
        mapping = {
            "MET-DOMAIN": cls.DOMAIN,
            "MET-FACT": cls.FACT,
            "MET-INFERENCE": cls.INFERENCE,
            "MET-STATE": cls.STATE,
            "MET-DOCUMENT": cls.DOCUMENT,
            "MET-CONSTRAINT": cls.CONSTRAINT,
            "MET-PROCESSOR": cls.PROCESSOR,
            "MET-RELATION": cls.RELATION,
        }
        return mapping[s.upper()]


# ── 二、4 类元关系类型 ──────────────────────────────────────


class MetaRelationType(enum.Enum):
    """4 类元关系类型（MET-RelationType）"""

    STRUCT = "MET-REL-STRUCT"  # 结构关系："由什么组成"（树形、有向、不可成环）
    DERIVE = "MET-REL-DERIVE"  # 推导关系："从什么产出"（有向、可追溯）
    BEHAVIOR = "MET-REL-BEHAVIOR"  # 行为关系："什么触发什么"（有向、可循环）
    JUSTIFY = "MET-REL-JUSTIFY"  # 验证关系："什么支撑什么"（有向、约束性）


# ── 三、元关系矩阵 ──────────────────────────────────────────

# MET-Type 之间的允许关系矩阵（rows=源, cols=目标）
# 原始定义见 06-元本体.md 3.3 节
_RELATION_MATRIX: dict[tuple[str, str], list[MetaRelationType]] = {
    # 源             目标              允许的元关系
    ("MET-DOMAIN", "MET-DOMAIN"): [MetaRelationType.STRUCT],
    ("MET-DOMAIN", "MET-FACT"): [MetaRelationType.DERIVE],
    ("MET-DOMAIN", "MET-INFERENCE"): [MetaRelationType.DERIVE],
    ("MET-DOMAIN", "MET-DOCUMENT"): [MetaRelationType.STRUCT, MetaRelationType.JUSTIFY],
    ("MET-FACT", "MET-DOCUMENT"): [MetaRelationType.JUSTIFY],
    ("MET-INFERENCE", "MET-DOCUMENT"): [MetaRelationType.DERIVE],
    ("MET-INFERENCE", "MET-FACT"): [MetaRelationType.DERIVE],  # derives_from
    ("MET-STATE", "MET-STATE"): [MetaRelationType.BEHAVIOR],
    ("MET-DOCUMENT", "MET-DOCUMENT"): [MetaRelationType.STRUCT],
    ("MET-DOCUMENT", "MET-FACT"): [MetaRelationType.JUSTIFY],
    ("MET-DOCUMENT", "MET-INFERENCE"): [MetaRelationType.DERIVE],
    ("MET-DOCUMENT", "MET-CONSTRAINT"): [MetaRelationType.JUSTIFY],
    ("MET-PROCESSOR", "MET-INFERENCE"): [MetaRelationType.DERIVE],
    ("MET-PROCESSOR", "MET-DOCUMENT"): [MetaRelationType.DERIVE],
    ("MET-PROCESSOR", "MET-CONSTRAINT"): [MetaRelationType.JUSTIFY],
}


def check_relation_allowed(source_type: MetaType, target_type: MetaType, relation_type: MetaRelationType) -> bool:
    """检查给定的元关系是否被元矩阵允许"""
    key = (source_type.value, target_type.value)
    allowed = _RELATION_MATRIX.get(key, [])
    return relation_type in allowed


# ── 四、四类元约束 ──────────────────────────────────────────


class MetaConstraint(enum.Enum):
    """4 条元约束（META-CON），定义自 06-元本体.md 5.1 节"""

    TYPE_PURITY = "META-CON-01"  # 每个实体属于且只属于一个 MET-Type
    REL_DIRECTION = "META-CON-02"  # 关系必须遵守 MET-Relation 矩阵
    PROC_INPUT = "META-CON-03"  # 处理器的输入必须是已实例化的实体
    SELF_REF_BOUND = "META-CON-04"  # 处理器不可处理自身实现代码


# ── 五、置信度级别 ──────────────────────────────────────────


class Confidence(enum.Enum):
    FACT = "fact"  # ✅ 事实：可独立验证
    INFERENCE = "inference"  # 📋 推论：从事实推导
    HYPOTHESIS = "hypothesis"  # 🤔 假设：有待验证
    ESTIMATED = "estimated"  # ⚠️ 估计：有不确定性


# ── 六、核心数据类 ──────────────────────────────────────────


@dataclass
class Entity:
    """一个 SSOT 实体。这是所有领域实体的基类。"""

    id: str  # 唯一标识符（如 ORG-国转中心）
    name: str  # 可读名称
    meta_type: MetaType  # 所属元类型
    entity_type: str  # 具体实体类型（Organization/Role/...）
    status: str = "active"  # active/draft/deprecated
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: Confidence = Confidence.FACT
    source: str = ""
    relations: list[Relation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    value_tier: int = 0  # 0=unknown, 1-7 matching X3 tiers
    half_life_days: int = 365  # default 1 year
    freshness_status: str = "fresh"  # fresh | aging | stale | expired

    @property
    def id_prefix(self) -> str:
        """取 ID 的前缀部分（如 ORG-/ROL-/INF-）"""
        parts = self.id.split("-", 1)
        return f"{parts[0]}-" if len(parts) > 1 else self.id


@dataclass
class Relation:
    """实体之间的关系"""

    source_id: str  # 源实体 ID
    target_id: str  # 目标实体 ID
    relation_type: str  # 具体关系名（part_of / derives_from / ...）
    meta_relation: MetaRelationType | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: Confidence = Confidence.FACT


@dataclass
class Fact:
    """事实实体——可验证的客观陈述"""

    id: str
    title: str
    meta_type: MetaType = MetaType.FACT
    value: Any = None
    unit: str = ""
    source: str = ""
    date: str = ""
    tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Inference:
    """推论实体——基于事实的逻辑推导"""

    id: str
    title: str
    derives_from: list[str]  # 依赖的事实 ID 列表
    logic: str  # 推导逻辑描述
    conclusion: str  # 推论结论
    meta_type: MetaType = MetaType.INFERENCE
    confidence: Confidence = Confidence.INFERENCE
    theory: str = ""  # 理论支撑
    status: str = "active"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateMachine:
    """状态机——系统行为节点的集合"""

    id: str
    name: str
    description: str = ""
    states: list[StateNode] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)


@dataclass
class StateNode:
    id: str
    name: str
    chain: str = ""  # 所属链（innovation/funding/talent）
    description: str = ""


@dataclass
class Transition:
    from_state: str
    to_state: str
    condition: str = ""
    interlocks: list[str] = field(default_factory=list)  # 咬合的目标状态


@dataclass
class Rule:
    """推理规则——从配置加载的规则定义"""

    id: str
    pattern: str  # 对应 5 条内置模式之一
    name: str = ""
    premises: list[dict] = field(default_factory=list)
    logic: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class Constraint:
    """约束规则——质量门禁"""

    id: str
    name: str
    severity: str = "WARN"  # BLOCKER / ERROR / WARN
    category: str = ""
    check_type: str = ""
    expectation: str = ""
    target_paths: list[str] = field(default_factory=list)
    meta_constraint: MetaConstraint | None = None


@dataclass
class DomainConfig:
    """完整的领域配置——所有领域的"输入数据"容器"""

    domain: dict[str, Any] = field(default_factory=dict)
    entities: list[Entity] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    inferences: list[Inference] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    state_machines: list[StateMachine] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)

    def find_entity(self, entity_id: str) -> Entity | None:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def find_fact(self, fact_id: str) -> Fact | None:
        for f in self.facts:
            if f.id == fact_id:
                return f
        return None

    def find_inference(self, inf_id: str) -> Inference | None:
        for i in self.inferences:
            if i.id == inf_id:
                return i
        return None


# ── 八层架构信息 ──────────────────────────────────────────

LAYER_NAMES = {
    0: "元元层 (Meta-Meta)",
    1: "元层 (Meta)",
    2: "处理器层 (Processor)",
    3: "知识组织层 (Document)",
    4: "行为层 (Behavior)",
    5: "约束层 (Constraint)",
    6: "知识层 (Knowledge)",
    7: "领域层 (Domain Instance)",
}


def describe_meta_type(meta_type: MetaType) -> dict:
    """返回元类型的本质描述（nature / can_do / cannot_do）"""
    descriptions = {
        MetaType.DOMAIN: {
            "nature": "可指认的现实实体",
            "can_do": ["被part_of", "被participates_in"],
            "cannot_do": "不能derives_from（非事实来源）",
        },
        MetaType.FACT: {
            "nature": "可验证的陈述",
            "can_do": ["被cites", "被derives_from"],
            "cannot_do": "不能主动推理（事实不产生推论）",
        },
        MetaType.INFERENCE: {
            "nature": "逻辑推导产物",
            "can_do": ["derives_from", "maps_to"],
            "cannot_do": "不能直接cites事实（应通过derives_from）",
        },
        MetaType.STATE: {
            "nature": "系统行为节点",
            "can_do": ["transitions_to", "interlocks_with"],
            "cannot_do": "不能contains文档（非组织形态）",
        },
        MetaType.DOCUMENT: {
            "nature": "知识呈现载体",
            "can_do": ["contains", "maps_to", "has_derivation_chain"],
            "cannot_do": "不能transitions_to（非系统行为）",
        },
        MetaType.CONSTRAINT: {
            "nature": "质量门禁",
            "can_do": ["satisfies(被满足)"],
            "cannot_do": "不能part_of（非组织实体）",
        },
        MetaType.PROCESSOR: {
            "nature": "计算过程",
            "can_do": ["processes", "generates", "validates"],
            "cannot_do": "不能有状态（无状态处理器）",
        },
        MetaType.RELATION: {
            "nature": "连接实体的边",
            "can_do": ["连接实体"],
            "cannot_do": "不能独立存在",
        },
    }
    return descriptions.get(meta_type, {})


# ── YAML Schema 校验 ──────────────────────────────────

# JSON Schema 模板：每个 YAML 文件的结构定义
YAML_SCHEMAS: dict[str, dict] = {
    "domain": {
        "title": "Domain Config",
        "type": "object",
        "required": ["domain"],
        "properties": {
            "domain": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string"},
                    "meta_model_version": {"type": "string"},
                },
            },
        },
    },
    "entities": {
        "title": "Entities",
        "type": "object",
        "required": ["entities"],
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "type"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "type": {"type": "string"},
                        "meta_type": {"type": "string"},
                        "name": {"type": "string"},
                        "status": {"type": "string", "enum": ["active", "draft", "deprecated"]},
                    },
                },
            },
        },
    },
    "facts": {
        "title": "Facts",
        "type": "object",
        "properties": {
            "policy": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "title"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "title": {"type": "string"},
                        "value": {},
                        "source": {"type": "string"},
                    },
                },
            },
            "data": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "title"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "title": {"type": "string"},
                        "value": {},
                        "unit": {"type": "string"},
                        "source": {"type": "string"},
                    },
                },
            },
        },
    },
    "inferences": {
        "title": "Inferences",
        "type": "object",
        "properties": {
            "inferences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "title", "conclusion"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "title": {"type": "string"},
                        "conclusion": {"type": "string"},
                        "logic": {"type": "string"},
                    },
                },
            },
        },
    },
    "rules": {
        "title": "Rules",
        "type": "object",
        "required": ["rules"],
        "properties": {
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "pattern"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "pattern": {"type": "string"},
                        "name": {"type": "string"},
                        "premises": {"type": "array"},
                    },
                },
            },
        },
    },
    "relations": {
        "title": "Relations",
        "type": "object",
        "properties": {
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["source_id", "target_id", "relation_type"],
                    "properties": {
                        "source_id": {"type": "string", "minLength": 1},
                        "target_id": {"type": "string", "minLength": 1},
                        "relation_type": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    },
    "machines": {
        "title": "State Machines",
        "type": "object",
        "properties": {
            "machines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "name": {"type": "string"},
                        "states": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["id", "name"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "constraints": {
        "title": "Constraints",
        "type": "object",
        "properties": {
            "constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "name", "expectation"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "name": {"type": "string"},
                        "severity": {"type": "string"},
                        "check_type": {"type": "string"},
                        "expectation": {"type": "string"},
                    },
                },
            },
        },
    },
}


def validate_yaml_schema(yaml_name: str, data: dict) -> list[str]:
    """用预定义的 JSON Schema 校验 YAML 数据结构。

    Returns:
        校验错误列表，空列表表示通过。
    """
    schema = YAML_SCHEMAS.get(yaml_name)
    if not schema:
        return []  # 无对应 schema 则跳过

    errors: list[str] = []

    def _check(obj: Any, schema: dict, path: str) -> None:
        if not isinstance(obj, dict):
            return

        # required fields
        for req in schema.get("required", []):
            if req not in obj:
                errors.append(f"{path}: 缺少必填字段 '{req}'")

        # properties
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name not in obj:
                continue
            value = obj[prop_name]
            prop_type = prop_schema.get("type", "")

            if prop_type == "string":
                if not isinstance(value, str):
                    errors.append(f"{path}.{prop_name}: 应为字符串，实际为 {type(value).__name__}")
                elif prop_schema.get("minLength", 0) > 0 and len(value) == 0:
                    errors.append(f"{path}.{prop_name}: 字符串不能为空")
                elif "enum" in prop_schema and value not in prop_schema["enum"]:
                    errors.append(f"{path}.{prop_name}: 值 '{value}' 不在允许范围内 {prop_schema['enum']}")

            elif prop_type == "array":
                if not isinstance(value, list):
                    errors.append(f"{path}.{prop_name}: 应为数组，实际为 {type(value).__name__}")
                elif "items" in prop_schema:
                    for idx, item in enumerate(value):
                        if isinstance(item, dict):
                            _check(item, prop_schema["items"], f"{path}.{prop_name}[{idx}]")

    _check(data, schema, yaml_name)
    return errors


# ── 跨文件引用校验 ────────────────────────────────────

import re as _re


def validate_cross_references(config: DomainConfig) -> list[str]:
    """校验跨文件引用完整性（实体/事实/关系/状态间的引用）。

    在 compile 阶段运行，确保所有引用目标存在，避免推导时才发现问题。

    检查项:
        1. 关系的 source/target → 实体/事实/推论/状态
        2. 推论的 derives_from → 事实/实体
        3. 规则条件中的 entity_attr/fact_ratio → 实体/事实
        4. 状态机的转换 → 状态节点
        5. 实体的 metadata.facts → 事实
    """
    errors: list[str] = []

    # 构建所有已知 ID 的索引
    known_ids: dict[str, str] = {}  # id → type_label
    for e in config.entities:
        known_ids[e.id] = f"实体({e.entity_type})"
    for f in config.facts:
        known_ids[f.id] = "事实"
    for i in config.inferences:
        known_ids[i.id] = "推论"
    for sm in config.state_machines:
        for s in sm.states:
            known_ids[s.id] = f"状态({sm.name})"

    # 1. 关系引用
    for r in config.relations:
        if r.source_id not in known_ids:
            errors.append(f"关系源 '{r.source_id}' 未定义（引用了不存在的实体/事实/状态）")
        if r.target_id not in known_ids:
            errors.append(f"关系目标 '{r.target_id}' 未定义（引用了不存在的实体/事实/状态）")

    # 2. 推论依赖
    for inf in config.inferences:
        for dep in inf.derives_from:
            if dep not in known_ids:
                errors.append(f"推论 {inf.id} 依赖 '{dep}' 不存在")

    # 3. 规则条件引用
    for rule in config.rules:
        for premise in rule.premises:
            cond = premise.get("condition", "")
            # entity_attr("ID", ...)
            for m in _re.finditer(r'entity_attr\("([^"]+)"', cond):
                ref = m.group(1)
                if ref not in known_ids:
                    errors.append(f"规则 {rule.id} 条件引用实体 '{ref}' 不存在")
            # fact_ratio("ID_A", "ID_B")
            for m in _re.finditer(r'fact_ratio\("([^"]+)",\s*"([^"]+)"\)', cond):
                for ref in (m.group(1), m.group(2)):
                    if ref not in known_ids:
                        errors.append(f"规则 {rule.id} 条件引用事实 '{ref}' 不存在")

    # 4. 状态机转换引用
    for sm in config.state_machines:
        state_ids = {s.id for s in sm.states}
        for t in sm.transitions:
            if t.from_state not in state_ids:
                errors.append(f"状态机 {sm.id} 转换 from_state='{t.from_state}' 不在状态列表中")
            if t.to_state not in state_ids:
                errors.append(f"状态机 {sm.id} 转换 to_state='{t.to_state}' 不在状态列表中")

    # 5. 实体引用的 facts
    for e in config.entities:
        for fid in e.metadata.get("facts", []):
            if fid not in known_ids:
                errors.append(f"实体 {e.id} metadata.facts 引用 '{fid}' 不存在")
        for pid in e.metadata.get("policies", []):
            if pid not in known_ids:
                errors.append(f"实体 {e.id} metadata.policies 引用 '{pid}' 不存在")

    return errors


# ── 正交性验证 ──────────────────────────────────────────


def verify_orthogonality() -> list[str]:
    """验证 8 个 MET-Type 两两正交（交集为空）"""
    violations = []
    types = list(MetaType)
    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            ti, tj = types[i], types[j]
            di = describe_meta_type(ti)
            dj = describe_meta_type(tj)
            if di == dj:
                violations.append(f"{ti.value} ∩ {tj.value} ≠ ∅")
    return violations
