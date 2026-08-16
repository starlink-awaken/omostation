from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fact:
    id: str
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source_card_id: str = ""
    derived_from: str = ""

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> Fact:
        return cls(**d)

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.subject:
            errs.append("subject is required")
        if not self.predicate:
            errs.append("predicate is required")
        if not self.object:
            errs.append("object is required")
        return errs
