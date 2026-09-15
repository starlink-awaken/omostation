"""Eidos — 认知记忆系统 (kairon 枢纽, 39K LOC, 被最多外部包 import).

主体模块:
- memory: 情感/联邦/蒸馏/遗忘曲线/生命周期/版本控制 (memory_manager, knowledge_distiller,
  forgetting_curve_engine, federated_memory, emotional_memory ...)
- nks 神经知识系统: 语义搜索/graphusion/agent 文件系统/增量索引/查询缓存
  (nks_semantic_search, nks_graphusion_engine, nks_agent_file_system ...)
- continuity: CRDT 会话/交接/冲突解决 (continuity_*, crdt_*)
- learning: dream/habit/pattern/preference/priority (认知学习)
- schema: 类型/注册/迁移 (Schema, registry — 数据建模子集)

被 kos/minerva/iris/codeanalyze 依赖 (kairon 内 9 个外部文件 import, 枢纽第一).
注意: 旧描述 "Schema validation layer" 严重失真, schema 只是数据建模子集.
"""

__version__ = "0.5.0"

from .core.validator import (
    ValidationError,
    ValidationResult,
    Validator,
)
from .meta import MetaRelationType, MetaType
from .registry import create_registry, registry
from .schema import (
    FieldType,
    Schema,
    SchemaField,
    SchemaMigration,
    SchemaRegistry,
    get_migrations,
    migrate_schema_instance,
    register_migration,
)
from .types import Fact, InferenceRule, KnowledgeCard, OntologyNode, Relation, StateMachine, StateTransition

__all__ = (
    "Fact",
    "FieldType",
    "InferenceRule",
    "KnowledgeCard",
    "MetaRelationType",
    "MetaType",
    "OntologyNode",
    "Relation",
    "Schema",
    "SchemaField",
    "SchemaMigration",
    "SchemaRegistry",
    "StateMachine",
    "StateTransition",
    "ValidationError",
    "ValidationResult",
    "Validator",
    "create_registry",
    "get_migrations",
    "migrate_schema_instance",
    "register_migration",
    "registry",
)
