from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OntologyNode:
    id: str
    name: str
    node_type: str
    parent: str = ""
    properties: dict = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> OntologyNode:
        return cls(**d)

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.name:
            errs.append("name is required")
        if not self.node_type:
            errs.append("node_type is required")
        return errs
