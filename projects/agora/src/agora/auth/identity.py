"""Typed identity helpers for Agora routing, accounting, and audit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Identity:
    """Canonical caller identity used at Agora boundaries."""

    subject_id: str
    subject_type: str = "legacy"
    issuer: str = "legacy"
    tenant: str = ""

    @property
    def actor(self) -> str:
        if self.subject_type == "legacy":
            return self.subject_id
        return f"{self.subject_type}:{self.subject_id}"

    @property
    def billing_subject(self) -> str:
        if self.tenant:
            return f"tenant:{self.tenant}"
        return self.actor

    def to_payload(self) -> dict[str, str]:
        return {
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "issuer": self.issuer,
            "tenant": self.tenant,
        }


def normalize_identity(value: Identity | Mapping[str, Any] | str | None) -> Identity:
    """Normalize supported caller representations into a typed Identity."""
    if isinstance(value, Identity):
        return value

    if isinstance(value, str) or value is None:
        subject_id = (value or "unknown").strip() or "unknown"
        return Identity(subject_id=subject_id, subject_type="legacy", issuer="legacy", tenant="")

    if isinstance(value, Mapping):
        subject_id = str(value.get("subject_id") or "unknown").strip() or "unknown"
        subject_type = str(value.get("subject_type") or "user").strip() or "user"
        issuer = str(value.get("issuer") or "unknown").strip() or "unknown"
        tenant = str(value.get("tenant") or "").strip()
        return Identity(
            subject_id=subject_id,
            subject_type=subject_type,
            issuer=issuer,
            tenant=tenant,
        )

    if all(hasattr(value, attr) for attr in ("subject_id", "subject_type", "issuer", "tenant")):
        subject_id = str(value.subject_id or "unknown").strip() or "unknown"
        subject_type = str(value.subject_type or "user").strip() or "user"
        issuer = str(value.issuer or "unknown").strip() or "unknown"
        tenant = str(value.tenant or "").strip()
        return Identity(
            subject_id=subject_id,
            subject_type=subject_type,
            issuer=issuer,
            tenant=tenant,
        )

    return Identity(subject_id="unknown", subject_type="legacy", issuer="legacy", tenant="")
