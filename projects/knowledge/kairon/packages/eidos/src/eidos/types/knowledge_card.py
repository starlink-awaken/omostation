from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Relation:
    target_id: str
    relation_type: str
    label: str = ""


@dataclass
class KnowledgeCard:
    id: str
    title: str
    content: str
    source: str
    source_type: str
    schema_type: str
    tags: list[str] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "source_type": self.source_type,
            "schema_type": self.schema_type,
            "tags": self.tags,
            "relations": [r.__dict__ for r in self.relations],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> KnowledgeCard:
        rels = [Relation(**r) if isinstance(r, dict) else r for r in d.get("relations", [])]
        return cls(**{k: v for k, v in d.items() if k != "relations"}, relations=rels)

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.title:
            errs.append("title is required")
        if not self.content:
            errs.append("content is required")
        if not self.source:
            errs.append("source is required")
        if not self.source_type:
            errs.append("source_type is required")
        if not self.schema_type:
            errs.append("schema_type is required")
        return errs
