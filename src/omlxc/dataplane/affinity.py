"""
Session Sticky and Prefix Cache Affinity Registry for omlxc.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omlxc.domain.protocols import ChatMessage


@dataclass(frozen=True, slots=True)
class AffinityConfig:
    session_ttl_seconds: float = 900.0  # 15 minutes
    prefix_ttl_seconds: float = 1800.0  # 30 minutes
    max_sessions: int = 1000
    max_prefixes: int = 500
    session_bonus: float = 1.35
    prefix_bonus: float = 1.15


class SessionAffinityRegistry:
    """
    In-memory dual-mode affinity registry tracking session-to-placement
    and prefix-to-placement mappings to maximize KV Cache hits.
    """

    def __init__(self, config: AffinityConfig | None = None) -> None:
        self._config = config or AffinityConfig()
        self._sessions: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._prefixes: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def get_session_placement(self, session_id: str, now: float | None = None) -> str | None:
        """Get bound placement for session if TTL has not expired."""
        ts = now if now is not None else time.monotonic()
        if session_id not in self._sessions:
            return None
        placement_id, last_seen = self._sessions[session_id]
        if ts - last_seen > self._config.session_ttl_seconds:
            # Expired
            self._sessions.pop(session_id, None)
            return None
        # Move to end (LRU touch)
        self._sessions.move_to_end(session_id)
        return placement_id

    def record_session_placement(
        self, session_id: str, placement_id: str, now: float | None = None
    ) -> None:
        """Record or refresh session affinity."""
        ts = now if now is not None else time.monotonic()
        if session_id in self._sessions:
            self._sessions.pop(session_id)
        elif len(self._sessions) >= self._config.max_sessions:
            # Evict oldest
            self._sessions.popitem(last=False)
        self._sessions[session_id] = (placement_id, ts)

    def get_prefix_placement(self, prefix_hash: str, now: float | None = None) -> str | None:
        """Get bound placement for prompt prefix hash if TTL has not expired."""
        ts = now if now is not None else time.monotonic()
        if prefix_hash not in self._prefixes:
            return None
        placement_id, last_seen = self._prefixes[prefix_hash]
        if ts - last_seen > self._config.prefix_ttl_seconds:
            self._prefixes.pop(prefix_hash, None)
            return None
        self._prefixes.move_to_end(prefix_hash)
        return placement_id

    def record_prefix_placement(
        self, prefix_hash: str, placement_id: str, now: float | None = None
    ) -> None:
        """Record or refresh prefix affinity."""
        ts = now if now is not None else time.monotonic()
        if prefix_hash in self._prefixes:
            self._prefixes.pop(prefix_hash)
        elif len(self._prefixes) >= self._config.max_prefixes:
            self._prefixes.popitem(last=False)
        self._prefixes[prefix_hash] = (placement_id, ts)

    def clear(self) -> None:
        """Clear all active affinities."""
        self._sessions.clear()
        self._prefixes.clear()


def _extract_text(msg: ChatMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, tuple):
        chunks: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return " ".join(chunks)
    return ""


def calculate_prefix_hash(messages: tuple[ChatMessage, ...]) -> str | None:
    """
    Calculate fingerprint of system prompt and initial instructions
    for KV Cache affinity routing.
    """
    if not messages:
        return None
    parts: list[str] = []
    for msg in messages:
        if msg.role == "system":
            text = _extract_text(msg)
            if text:
                parts.append(text)
        elif not parts and msg.role == "user":
            text = _extract_text(msg)
            if text:
                parts.append(text[:512])
            break

    if not parts:
        return None

    digest = hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]
