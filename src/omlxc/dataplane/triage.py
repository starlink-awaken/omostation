"""
Fast Triage Gate and intent complexity tiering for omlxc.

Classifies incoming route requests into FAST, STANDARD, or REASONING tiers
using zero-latency heuristic structural feature analysis and lightweight rules.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final

from omlxc.domain.protocols import ChatMessage


class ComplexityTier(enum.StrEnum):
    """Complexity tiers for model selection and scheduling."""

    FAST = "fast"  # 2B~4B micro-latency (e.g. single-turn lookup, syntax check)
    STANDARD = "standard"  # 8B~14B balanced daily tasks
    REASONING = "reasoning"  # 27B~70B deep thinking, architectural AST refactoring


@dataclass(frozen=True, slots=True)
class TriageResult:
    """Outcome of intent complexity triage."""

    tier: ComplexityTier
    reason: str
    confidence: float
    heuristic_matched: bool = True


REASONING_KEYWORDS: Final[tuple[str, ...]] = (
    "refactor architecture",
    "design system",
    "ast rewrite",
    "formal verification",
    "deep thinking",
    "step-by-step reasoning",
    "proof",
    "deadlock analysis",
    "distributed consensus",
    "aba problem",
    "lock-free",
    "p vs np",
    "np-hard",
    "race condition",
    "memory leak analysis",
    "type inference engine",
    "compiler pass",
    "byzantine fault",
    "raft consensus",
)

FAST_KEYWORDS: Final[tuple[str, ...]] = (
    "fix typo",
    "grammar check",
    "format json",
    "translate word",
    "explain regex",
    "synonym",
    "quick fix",
)


def _extract_text(content: str | tuple[object, ...] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        text_attr = getattr(block, "text", None)
        if isinstance(text_attr, str):
            parts.append(text_attr)
        elif isinstance(block, str):
            parts.append(block)
    return " ".join(parts)


class TriageClassifier:
    """Zero-latency intent complexity triage classifier."""

    def __init__(
        self,
        fast_token_threshold: int = 150,
        reasoning_token_threshold: int = 2500,
    ) -> None:
        self._fast_token_threshold = fast_token_threshold
        self._reasoning_token_threshold = reasoning_token_threshold

    def classify(
        self,
        messages: tuple[ChatMessage, ...] | None = None,
        context_tokens: int = 0,
        thinking_requested: bool = False,
        model_hint: str | None = None,
    ) -> TriageResult:
        """Classify request complexity based on structural features and tokens."""
        # 1. Explicit thinking or deep model hint
        if thinking_requested:
            return TriageResult(
                tier=ComplexityTier.REASONING,
                reason="explicit thinking_requested=true",
                confidence=1.0,
            )

        if model_hint and any(
            hint in model_hint.lower() for hint in ("deepseek-r1", "reasoner", "o1", "o3", "thought")
        ):
            return TriageResult(
                tier=ComplexityTier.REASONING,
                reason=f"model hint '{model_hint}' indicates reasoning",
                confidence=0.95,
            )

        # 2. Heavy context size
        if context_tokens >= self._reasoning_token_threshold:
            return TriageResult(
                tier=ComplexityTier.REASONING,
                reason=(f"large context tokens ({context_tokens} >= {self._reasoning_token_threshold})"),
                confidence=0.9,
            )

        # 3. Analyze prompt text structure if messages provided
        if messages:
            last_user_msg = ""
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user_msg = _extract_text(msg.content)
                    break

            last_lower = last_user_msg.lower()

            # Check reasoning keywords or complex multi-code blocks
            if any(kw in last_lower for kw in REASONING_KEYWORDS):
                return TriageResult(
                    tier=ComplexityTier.REASONING,
                    reason="detected architectural/reasoning keywords in user prompt",
                    confidence=0.85,
                )

            code_blocks = len(re.findall(r"```", last_user_msg)) // 2
            if code_blocks >= 3:
                return TriageResult(
                    tier=ComplexityTier.REASONING,
                    reason=f"multiple code blocks ({code_blocks}) requires deep AST synthesis",
                    confidence=0.8,
                )

            # Check fast keywords & small token count
            if (
                context_tokens <= self._fast_token_threshold
                and len(messages) <= 2
                and (any(kw in last_lower for kw in FAST_KEYWORDS) or (len(last_user_msg) <= 80 and code_blocks == 0))
            ):
                return TriageResult(
                    tier=ComplexityTier.FAST,
                    reason="short single-turn query without complex code structure",
                    confidence=0.85,
                )

        # 4. Fallback to standard
        return TriageResult(
            tier=ComplexityTier.STANDARD,
            reason="standard daily dialogue / balanced completion task",
            confidence=0.75,
        )
