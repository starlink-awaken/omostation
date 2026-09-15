"""InferenceRule — MET-INFERENCE type for OntoDerive reasoning rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferenceRule:
    """A reasoning rule — defines premises, conclusion, and derivation method."""

    id: str
    name: str
    rule_type: str  # forward | backward | abductive
    premises: list[str]
    conclusion: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "rule_type": self.rule_type,
            "premises": self.premises,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InferenceRule:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.name:
            errs.append("name is required")
        if self.rule_type not in ("forward", "backward", "abductive"):
            errs.append(f"invalid rule_type: {self.rule_type}")
        if not self.premises:
            errs.append("at least one premise required")
        if not self.conclusion:
            errs.append("conclusion is required")
        return errs
