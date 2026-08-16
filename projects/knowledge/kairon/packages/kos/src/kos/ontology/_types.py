"""KOS entity/relation type definitions (from SPEC-v0.1 §3).

These types establish a shared protocol across KOS, ontoderive,
and DigitalBrainOS.  Migrated from SPEC into code.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EntityType(StrEnum):
    """统一实体类型枚举 — 所有项目共用"""

    PERSON = "person"
    ORGANIZATION = "organization"
    PROJECT = "project"
    RESOURCE = "resource"
    EVENT = "event"
    STANDARD = "standard"
    CONCEPT = "concept"
    ROLE = "role"
    AXIOM = "axiom"
    PRINCIPLE = "principle"
    THEORY = "theory"
    FRAMEWORK = "framework"
    SKILL = "skill"
    CONSENSUS = "consensus"
    TASK = "task"


ENTITY_ID_PREFIXES = {
    "ROL-": EntityType.PERSON,
    "ORG-": EntityType.ORGANIZATION,
    "PRJ-": EntityType.PROJECT,
    "RES-": EntityType.RESOURCE,
    "EVT-": EntityType.EVENT,
    "STD-": EntityType.STANDARD,
    "CON-": EntityType.CONCEPT,
    "RLE-": EntityType.ROLE,
    "AXM-": EntityType.AXIOM,
    "PRN-": EntityType.PRINCIPLE,
    "THY-": EntityType.THEORY,
    "FRW-": EntityType.FRAMEWORK,
    "SKL-": EntityType.SKILL,
    "CNS-": EntityType.CONSENSUS,
    "TSK-": EntityType.TASK,
    "RCH-": EntityType.CONCEPT,  # Minerva research results
}


@dataclass
class Entity:
    """核心实体定义。"""

    entity_id: str
    entity_type: EntityType = EntityType.CONCEPT
    label: str = ""
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    zone: str = ""
    source: str = ""
    confidence: float = 1.0
    status: str = "active"
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Value Stack fields (X3)
    value_tier: int = 0
    half_life_days: int = 365
    freshness_status: str = "fresh"
    last_validated: str = ""
    next_review: str = ""
    references: list[str] = field(default_factory=list)


class RelationType(StrEnum):
    """统一关系类型枚举"""

    REPORTS_TO = "reports_to"
    MANAGES = "manages"
    MEMBER_OF = "member_of"
    WORKS_ON = "works_on"
    COORDINATES = "coordinates"
    OWNS = "owns"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    PRECEDES = "precedes"
    DERIVES_FROM = "derives_from"


@dataclass
class Relation:
    source_id: str
    relation_type: RelationType
    target_id: str
    confidence: float = 1.0
    source: str = ""
    updated_at: str = ""


# ── ID utilities ──


def validate_entity_id(entity_id: str) -> bool:
    """校验 ID 格式是否符合前缀规范"""
    return any(entity_id.startswith(prefix) and len(entity_id) > len(prefix) for prefix in ENTITY_ID_PREFIXES)


def infer_entity_type(entity_id: str) -> EntityType | None:
    """从 ID 前缀推断实体类型"""
    for prefix, etype in ENTITY_ID_PREFIXES.items():
        if entity_id.startswith(prefix):
            return etype
    return None


def migrate_id(old_id: str) -> str:
    """将旧 ID 格式迁移到新标准"""
    migration_map = {
        "P:": "ROL-",
        "O:": "ORG-",
        "J:": "PRJ-",
        "person-": "ROL-",
        "org-": "ORG-",
        "proj_": "PRJ-",
        "mem_": "RES-",
    }
    for old_prefix, new_prefix in migration_map.items():
        if old_id.startswith(old_prefix):
            return new_prefix + old_id[len(old_prefix) :]
    return old_id
