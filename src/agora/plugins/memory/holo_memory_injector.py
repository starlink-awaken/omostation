from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Summary: "HoloMemoryInjector — selects relevant memories for a worker at spawn time."
Tags:
  - memory
  - worker
  - swarm
  - injection
---

HoloMemoryInjector — selects relevant memories for a worker at spawn time.
Works with both the local HoloMemory store and the session-level memory system.
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# HoloMemoryInjector ≡ Module
# 内涵 ≝ {MemorySlice, HoloMemoryInjector}
# 外延 ≝ {e | e ∈ D-Gateway ∧ injects(e, Memory)}
# 功能 ⊢ {Store, Retrieve, Inject, Serialize}
# =============================================================================
import json  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

logger = logging.getLogger(__name__)

_MAX_ENV_BYTES = 4096


@dataclass
class MemorySlice:
    """A single retrieved memory unit for worker context injection.

    Attributes:
        source:          Origin of the memory (e.g. "holo_memory", "session", "role_default").
        key:             Memory key / identifier.
        value:           Memory content / text.
        relevance_score: Float in [0, 1] — higher means more relevant to the current task.
        created_at:      Unix timestamp of when this memory was stored.
    """

    source: str
    key: str
    value: str
    relevance_score: float = 0.0
    created_at: float = field(default_factory=time.time)


class HoloMemoryInjector:
    """Selects and injects relevant memories into worker spawn contexts.

    Supports two storage backends:
    - **File-backed** — persists slices as JSON files under *memory_path*.
    - **In-memory dict** — used when *memory_path* is ``None`` or the directory
      cannot be created (e.g. tests, read-only environments).

    Usage::

        injector = HoloMemoryInjector()
        injector.store("api_pattern", "Always use retry with backoff", tags=["coder"])
        ctx = injector.inject_into_context({}, role_id="coder", task_intent="write API client")
    """

    _DEFAULT_PATH = "data/holo_memory"

    def __init__(self, memory_path: str | None = None) -> None:
        """Initialise the injector.

        Args:
            memory_path: Directory path for persisted memory slices.  Defaults
                         to ``data/holo_memory/`` relative to the project root.
                         Pass an explicit ``None`` to force in-memory mode.
        """
        self.status = "active"
        self._in_memory: dict[str, dict[str, Any]] = {}
        self._file_backed = False

        resolved = memory_path if memory_path is not None else self._DEFAULT_PATH

        try:
            p = Path(resolved)
            p.mkdir(parents=True, exist_ok=True)
            self._store_path = p
            self._file_backed = True
            logger.debug("[HoloMemoryInjector] File-backed store at '%s'.", p)
        except OSError as exc:
            logger.warning(
                "[HoloMemoryInjector] Cannot use file store '%s' (%s). Falling back to in-memory.",
                resolved,
                exc,
            )
            self._store_path = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, key: str, value: str, tags: list[str] | None = None) -> MemorySlice:
        """Persist a memory slice.

        Args:
            key:   Identifier / short label for the memory.
            value: Content of the memory.
            tags:  Optional list of role/domain tags for filtering.

        Returns:
            The created :class:`MemorySlice`.
        """
        slice_data: dict[str, Any] = {
            "source": "holo_memory",
            "key": key,
            "value": value,
            "relevance_score": 0.0,
            "created_at": time.time(),
            "tags": tags or [],
        }

        if self._file_backed and self._store_path:
            safe_key = key.replace("/", "_").replace(" ", "_")
            dest = self._store_path / f"{safe_key}.json"
            try:
                dest.write_text(
                    json.dumps(slice_data, ensure_ascii=False), encoding="utf-8"
                )
            except OSError as exc:
                logger.warning(
                    "[HoloMemoryInjector] Failed to write '%s': %s", dest, exc
                )
                self._in_memory[key] = slice_data
        else:
            self._in_memory[key] = slice_data

        return MemorySlice(
            source=slice_data["source"],
            key=key,
            value=value,
            relevance_score=0.0,
            created_at=slice_data["created_at"],
        )

    def retrieve_for_role(
        self,
        role_id: str,
        task_intent: str,
        max_slices: int = 10,
    ) -> list[MemorySlice]:
        """Retrieve relevant memories for *role_id* given *task_intent*.

        Scoring strategy:
        - Tokenises both *task_intent* and each slice's ``key`` + ``value``.
        - ``relevance_score = matching_tokens / total_intent_tokens``   (clamped to [0, 1]).
        - Slices tagged with *role_id* receive a +0.2 bonus.

        Args:
            role_id:     Role identifier used to filter / boost tagged slices.
            task_intent: Natural-language description of the task (used for scoring).
            max_slices:  Maximum number of slices to return.

        Returns:
            Up to *max_slices* :class:`MemorySlice` objects sorted by
            ``relevance_score`` descending.
        """
        raw_slices = self._load_all()
        if not raw_slices:
            return []

        intent_tokens = set(_tokenize(task_intent))
        scored: list[MemorySlice] = []

        for data in raw_slices:
            tags: list[str] = data.get("tags", [])
            # Skip slices that have role tags but none match this role
            if tags and role_id not in tags:
                continue

            candidate_text = f"{data.get('key', '')} {data.get('value', '')}"
            candidate_tokens = set(_tokenize(candidate_text))

            if intent_tokens:
                overlap = len(intent_tokens & candidate_tokens)
                score = min(1.0, overlap / len(intent_tokens))
            else:
                score = 0.0

            # Role-tag bonus
            if role_id in tags:
                score = min(1.0, score + 0.2)

            scored.append(
                MemorySlice(
                    source=data.get("source", "holo_memory"),
                    key=data.get("key", ""),
                    value=data.get("value", ""),
                    relevance_score=round(score, 4),
                    created_at=data.get("created_at", 0.0),
                )
            )

        scored.sort(key=lambda s: s.relevance_score, reverse=True)
        return scored[:max_slices]

    def inject_into_context(
        self,
        worker_context: dict,
        role_id: str,
        task_intent: str,
    ) -> dict:
        """Augment *worker_context* with a ``memory_slices`` list.

        Retrieves relevant memories and attaches them under the
        ``"memory_slices"`` key.  Called during worker spawn.

        Args:
            worker_context: Existing context dict (mutated in place and returned).
            role_id:        Role of the worker being spawned.
            task_intent:    Task description used for relevance scoring.

        Returns:
            The augmented *worker_context* dict.
        """
        slices = self.retrieve_for_role(role_id=role_id, task_intent=task_intent)
        worker_context["memory_slices"] = [asdict(s) for s in slices]
        return worker_context

    def serialize_for_env(self, slices: list[MemorySlice]) -> str:
        """Serialise *slices* to a JSON string suitable for ``BOS_MEMORY_CONTEXT``.

        Truncates to ``_MAX_ENV_BYTES`` characters to fit inside process
        environment variable limits.

        Args:
            slices: List of :class:`MemorySlice` objects.

        Returns:
            JSON string, truncated at ``_MAX_ENV_BYTES`` bytes.
        """
        payload = json.dumps([asdict(s) for s in slices], ensure_ascii=False)
        if len(payload) > _MAX_ENV_BYTES:
            # Trim: drop trailing slices until it fits
            for n in range(len(slices), 0, -1):
                candidate = json.dumps(
                    [asdict(s) for s in slices[:n]], ensure_ascii=False
                )
                if len(candidate) <= _MAX_ENV_BYTES:
                    return candidate
            return "[]"
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> list[dict[str, Any]]:
        """Return all stored slice dicts from the active backend."""
        results: list[dict[str, Any]] = []

        if self._file_backed and self._store_path:
            for fp in self._store_path.glob("*.json"):
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    results.append(data)
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "[HoloMemoryInjector] Skipping corrupt file '%s': %s", fp, exc
                    )

        # In-memory always included (may overlap file keys — that's fine for retrieval)
        results.extend(self._in_memory.values())
        return results


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Return lowercased alpha-numeric tokens from *text*."""
    import re

    return re.findall(r"[a-z0-9]+", text.lower())
