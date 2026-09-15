"""OntoLang AST节点定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(Enum):
    ENTITY = "entity"
    FACT = "fact"
    INFERENCE = "inference"
    PROTOCOL = "protocol"
    RELATION = "relation"


@dataclass
class SourcePos:
    line: int
    col: int
    file: str = ""

    def __str__(self) -> Any:
        return f"{self.file}:{self.line}:{self.col}" if self.file else f"L{self.line}:C{self.col}"


@dataclass
class EntityDef:
    id: str
    entity_type: str
    properties: dict = field(default_factory=dict)
    pos: SourcePos | None = None


@dataclass
class FactDef:
    id: str
    fact_type: str
    properties: dict = field(default_factory=dict)
    pos: SourcePos | None = None


@dataclass
class InferenceDef:
    id: str
    inference_type: str
    derives_from: list[str] = field(default_factory=list)
    conclusion: str = ""
    properties: dict = field(default_factory=dict)
    pos: SourcePos | None = None


@dataclass
class ProtocolDef:
    id: str
    constraint_type: str
    constraint: str = ""
    properties: dict = field(default_factory=dict)
    pos: SourcePos | None = None


@dataclass
class RelationDef:
    subject: str
    relation_type: str
    object: str
    pos: SourcePos | None = None


@dataclass
class AST:
    entities: list[EntityDef] = field(default_factory=list)
    facts: list[FactDef] = field(default_factory=list)
    inferences: list[InferenceDef] = field(default_factory=list)
    protocols: list[ProtocolDef] = field(default_factory=list)
    relations: list[RelationDef] = field(default_factory=list)


@dataclass
class ParseError:
    msg: str
    pos: SourcePos
    hint: str = ""


@dataclass
class SemanticError:
    msg: str
    node_id: str = ""
    pos: SourcePos | None = None
    hint: str = ""
