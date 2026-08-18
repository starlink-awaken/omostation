"""Domain Governance Cartridge Capsule Specification (ADR-0203).

Defines the metadata, intent rules, policy boundaries, and tool signatures
for distributable, sovereign .cartridge packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CartridgeManifest:
    """领域治理卡带清单元数据."""

    cartridge_id: str
    name: str
    version: str
    domain: str
    author: str = "Antigravity"
    description: str = ""
    intent_patterns: list[str] = field(default_factory=list)
    policy_rules: list[str] = field(default_factory=list)
    required_models: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    manifest_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cartridge_id": self.cartridge_id,
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "author": self.author,
            "description": self.description,
            "intent_patterns": self.intent_patterns,
            "policy_rules": self.policy_rules,
            "required_models": self.required_models,
            "created_at": self.created_at,
            "manifest_hash": self.manifest_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CartridgeManifest:
        return cls(
            cartridge_id=data["cartridge_id"],
            name=data["name"],
            version=data.get("version", "1.0.0"),
            domain=data.get("domain", "common"),
            author=data.get("author", "Unknown"),
            description=data.get("description", ""),
            intent_patterns=data.get("intent_patterns", []),
            policy_rules=data.get("policy_rules", []),
            required_models=data.get("required_models", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            manifest_hash=data.get("manifest_hash", ""),
        )
