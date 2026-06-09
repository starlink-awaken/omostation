"""
model_driven.mof — MOF 扩展模块

提供全生命周期模型驱动的元模型扩展：
- M3 扩展: 生命周期元素 + 价值元素
- M2 扩展: ~22 个新类型覆盖 7 阶段
- 本体论映射扩展
"""

from .m3_extended import (
    BenefitModel,
    CostModel,
    Gate,
    Goal,
    KeyResult,
    LifecycleStage,
    M3ElementType,
    M3RelationType,
    STANDARD_GATES,
    STANDARD_STAGES,
    Stage,
    Transition,
)
from .m2_lifecycle import (
    ALL_M2_SCHEMAS,
    M2Schema,
    M2Type,
    get_schema,
    list_all_schema_names,
    list_schemas_by_stage,
)
from .ontology_extended import (
    CROSS_STAGE_CONSISTENCY_RULES,
    DERIVATION_RULES_EXTENDED,
    M2_TYPE_STAGE_MAPPING,
    STAGE_DEPENDENCIES,
    STAGE_EQUIVALENCES,
    TRIGGER_DEPENDENCIES,
    TRIGGER_DERIVATION_RULES,
    TRIGGER_EQUIVALENCES,
    TRIGGER_GENERALIZATIONS,
)

__all__ = [
    # M3
    "LifecycleStage",
    "M3ElementType",
    "M3RelationType",
    "Stage",
    "Gate",
    "Transition",
    "Goal",
    "KeyResult",
    "CostModel",
    "BenefitModel",
    "STANDARD_STAGES",
    "STANDARD_GATES",
    # M2
    "M2Type",
    "M2Schema",
    "ALL_M2_SCHEMAS",
    "get_schema",
    "list_schemas_by_stage",
    "list_all_schema_names",
    # Ontology
    "STAGE_EQUIVALENCES",
    "STAGE_DEPENDENCIES",
    "M2_TYPE_STAGE_MAPPING",
    "DERIVATION_RULES_EXTENDED",
    "CROSS_STAGE_CONSISTENCY_RULES",
    "TRIGGER_EQUIVALENCES",
    "TRIGGER_DEPENDENCIES",
    "TRIGGER_GENERALIZATIONS",
    "TRIGGER_DERIVATION_RULES",
]
