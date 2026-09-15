"""Dual-track writer: raw audit + theta searchable (non-simulation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mos.backends import RawBackend, ThetaBackend
from mos.envelope import MemoryEnvelope


@dataclass
class DualTrackResult:
    ok: bool
    raw_id: str | None
    raw_ok: bool
    theta_ok: bool
    theta_id: str | None = None
    theta_error: str | None = None
    degraded: bool = False
    skipped_theta: bool = False
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DualTrackWriter:
    """
    Write raw first; then theta.
    Theta failure must not erase raw success (degraded=True).
    """

    def __init__(
        self,
        raw: RawBackend,
        theta: ThetaBackend,
        *,
        confidence_threshold: float = 0.6,
    ) -> None:
        self.raw = raw
        self.theta = theta
        self.confidence_threshold = confidence_threshold

    def write(self, envelope: MemoryEnvelope) -> DualTrackResult:
        payload = envelope.to_dict()
        # Strip high-PII body from raw audit payload when content_ref present
        raw_payload = dict(payload)
        if envelope.pii_class == "high" or (envelope.content_ref and envelope.pii_class != "none"):
            raw_payload["content"] = None
            raw_payload["content_redacted"] = True

        raw_res = self.raw.emit("memory.write_raw", raw_payload)
        raw_id = str(raw_res.get("id") or "")
        raw_ok = bool(raw_res.get("ok", True))

        if envelope.confidence < self.confidence_threshold:
            return DualTrackResult(
                ok=raw_ok,
                raw_id=raw_id or None,
                raw_ok=raw_ok,
                theta_ok=False,
                skipped_theta=True,
                reason=f"confidence {envelope.confidence} < {self.confidence_threshold}",
            )

        try:
            theta_res = self.theta.upsert(payload)
            return DualTrackResult(
                ok=raw_ok and bool(theta_res.get("ok", True)),
                raw_id=raw_id or None,
                raw_ok=raw_ok,
                theta_ok=bool(theta_res.get("ok", True)),
                theta_id=str(theta_res.get("id") or envelope.id or ""),
            )
        except Exception as exc:
            return DualTrackResult(
                ok=raw_ok,  # raw survived
                raw_id=raw_id or None,
                raw_ok=raw_ok,
                theta_ok=False,
                theta_error=str(exc),
                degraded=True,
                reason="theta_failed",
            )

    def forget(self, memory_id: str, *, reason: str | None = None) -> DualTrackResult:
        """Propagate forget: raw audit always; theta best-effort."""
        payload = {"memory_id": memory_id, "reason": reason or "user_forget"}
        raw_res = self.raw.emit("memory.forget", payload)
        raw_id = str(raw_res.get("id") or "")
        raw_ok = bool(raw_res.get("ok", True))
        try:
            theta_res = self.theta.forget(memory_id)
            return DualTrackResult(
                ok=raw_ok,
                raw_id=raw_id or None,
                raw_ok=raw_ok,
                theta_ok=bool(theta_res.get("ok", True)),
                theta_id=str(theta_res.get("id") or memory_id),
                metadata={"theta_found": theta_res.get("found")},
            )
        except Exception as exc:
            return DualTrackResult(
                ok=raw_ok,
                raw_id=raw_id or None,
                raw_ok=raw_ok,
                theta_ok=False,
                theta_error=str(exc),
                degraded=True,
                reason="theta_forget_failed",
            )
