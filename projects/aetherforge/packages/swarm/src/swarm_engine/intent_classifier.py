from __future__ import annotations

# ruff: noqa: RUF002, RUF003

# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---
"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-ST01-01_architecture_standard.md
Layer: L2
Constraint: "[!!] INTENT_CLASSIFIER_HEURISTIC"
Summary: 'IntentClassifier: 意图复杂度分类器 — 判断任务是否需要 Swarm 模式执行。'
Tags:
  - intent
  - classifier
  - swarm
  - execution
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# IntentClassifier ≡ Module
# 内涵 ≝ {IntentClassifier}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, IntentClassifier)}
# 功能 ⊢ {Classify_Intent, Detect_Complexity, Suggest_Swarm_Size}
# =============================================================================
import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

try:
    from nucleus.Z_Microkernel.infrastructure.oracle.inference_oracle import (  # type: ignore[import-not-found]
        InferenceOracle,
    )
except (ImportError, ModuleNotFoundError):

    class InferenceOracle:  # type: ignore[no-redef]
        @classmethod
        def get_instance(cls) -> InferenceOracle:
            raise ImportError("nucleus.Z_Microkernel.infrastructure.oracle.inference_oracle is unavailable")


_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------


class ComplexityLevel(Enum):
    """Intent complexity tier used to drive execution routing."""

    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


@dataclass
class ClassificationResult:
    """Full classification output returned by IntentClassifier.classify()."""

    level: ComplexityLevel
    confidence: float  # 0.0 – 1.0
    rationale: str  # Human-readable explanation
    suggested_swarm_size: int  # 1 – 8 parallel workers
    suggested_roles: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.level.value} (confidence: {self.confidence:.2f}) — {self.rationale}"


# ---------------------------------------------------------------------------
# Heuristic Rule Sets (Enhanced v1.1)
# ---------------------------------------------------------------------------

# Keywords that strongly indicate COMPLEX work
_COMPLEX_KEYWORDS: frozenset[str] = frozenset(
    {
        "analyze",
        "analyse",
        "research",
        "comprehensive",
        "all",
        "entire",
        "multiple",
        "parallel",
        "coordinate",
        "across",
        "compare",
        "investigate",
        "evaluate",
        "audit",
        "refactor",
        "redesign",
        "architect",
        "plan",
        "strategy",
        "deploy",
        "migrate",
        "integrate",
        "orchestrate",
        "benchmark",
        "review all",
        "full",
        "complete",
        "end-to-end",
        "end to end",
        # === ENHANCED: More domain-specific complex indicators ===
        "thorough",
        "systematic",
        "cross-functional",
        "multi-stage",
        "production",
        "scalable",
        "enterprise",
        "microservice",
        "distributed",
        "concurrent",
        "optimization",
        "performance",
        "security",
        "vulnerability",
        "threat",
        "authentication",
        "authorization",
        "encryption",
        "CI/CD",
        "pipeline",
        "automation",
    }
)

# Keywords that push toward MODERATE (step-sequencing language)
_STEP_KEYWORDS: frozenset[str] = frozenset(
    {
        "then",
        "after",
        "and then",
        "followed by",
        "step",
        "next",
        "first",
        "second",
        "third",
        "finally",
        "lastly",
        "subsequently",
        "once",
        "before",
        "when done",
        # === ENHANCED: Additional sequential indicators ===
        "sequence",
        "consequently",
        "afterwards",
        "prior to",
        "subsequent",
        "step by step",
        "in order",
        "gradually",
        "proceed",
        "continue",
    }
)

# Keywords that pull toward SIMPLE (single-action verbs)
_SIMPLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "list",
        "show",
        "check",
        "get",
        "find",
        "print",
        "display",
        "read",
        "cat",
        "view",
        "ping",
        "status",
        "version",
        "help",
        "count",
        "echo",
        "whoami",
        "pwd",
        "ls",
        "ps",
        # === ENHANCED: More single-action indicators ===
        "inspect",
        "query",
        "fetch",
        "retrieve",
        "lookup",
        "search",
        "validate",
        "verify",
        "test",
        "run",
        "execute",
        "start",
        "stop",
        "restart",
        "reload",
        "refresh",
        "update",
    }
)

# Conjunctions that break the "single-step" assumption
_CONJUNCTIONS: frozenset[str] = frozenset({"and", "or", "then", "while", "but", "also"})

# Role suggestions keyed by complexity tier
_DEFAULT_ROLES: dict[ComplexityLevel, list[str]] = {
    ComplexityLevel.SIMPLE: ["executor"],
    ComplexityLevel.MODERATE: ["planner", "executor"],
    ComplexityLevel.COMPLEX: ["coordinator", "researcher", "analyst", "executor", "reviewer"],
}

# ---------------------------------------------------------------------------
# IntentClassifier
# ---------------------------------------------------------------------------


class IntentClassifier:
    """
    Pure heuristic intent complexity classifier.

    Classifies free-text intent strings into SIMPLE / MODERATE / COMPLEX
    levels and produces swarm-sizing recommendations.  No external API is
    required; an optional LLM enhancement hook is provided via the
    ``llm_enhance`` parameter.
    """

    def __init__(self, llm_enhance: bool = False) -> None:
        """
        super().__init__()
        Args:
            llm_enhance: When True the classifier will attempt to call an
                         LLM backend (if configured) to refine confidence
                         scores.  Falls back to heuristic silently.
        """
        self._llm_enhance = llm_enhance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, intent_text: str) -> ClassificationResult:
        """
        Classify *intent_text* and return a :class:`ClassificationResult`.

        The heuristic pipeline:
        1. Normalise & tokenise the input.
        2. Apply rule-based scoring (COMPLEX / STEP / SIMPLE indicators).
        3. Consider word count and sentence count.
        4. Resolve final tier and build rationale.
        5. (Optional) LLM-enhance confidence.
        """
        if not intent_text or not intent_text.strip():
            return ClassificationResult(
                level=ComplexityLevel.SIMPLE,
                confidence=1.0,
                rationale="Empty intent defaults to SIMPLE.",
                suggested_swarm_size=1,
                suggested_roles=["executor"],
            )

        text = intent_text.strip()
        normalised = text.lower()
        tokens = re.findall(r"\b\w+\b", normalised)
        word_count = len(tokens)
        sentence_count = len(re.split(r"[.!?]+", text.strip()))

        # --- score accumulators ---
        complex_hits: list[str] = []
        step_hits: list[str] = []
        simple_hits: list[str] = []
        conjunction_hits: list[str] = []

        for kw in _COMPLEX_KEYWORDS:
            if kw in normalised:
                complex_hits.append(kw)

        for kw in _STEP_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", normalised):
                step_hits.append(kw)

        for kw in _SIMPLE_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", normalised):
                simple_hits.append(kw)

        for conj in _CONJUNCTIONS:
            if re.search(r"\b" + re.escape(conj) + r"\b", normalised):
                conjunction_hits.append(conj)

        # --- rule evaluation ---
        level, rationale_parts, base_confidence = self._apply_rules(
            word_count=word_count,
            sentence_count=sentence_count,
            complex_hits=complex_hits,
            step_hits=step_hits,
            simple_hits=simple_hits,
            conjunction_hits=conjunction_hits,
            normalised=normalised,
        )

        confidence = self._compute_confidence(
            level=level,
            word_count=word_count,
            complex_hits=complex_hits,
            step_hits=step_hits,
            simple_hits=simple_hits,
            base=base_confidence,
        )

        swarm_size = self._swarm_size(level, word_count, complex_hits, step_hits)
        roles = self._suggest_roles(level, complex_hits)
        rationale = "; ".join(rationale_parts)

        result = ClassificationResult(
            level=level,
            confidence=round(confidence, 2),
            rationale=rationale,
            suggested_swarm_size=swarm_size,
            suggested_roles=roles,
        )

        _log.debug("IntentClassifier: %s", result)

        if self._llm_enhance:
            result = self._try_llm_enhance(intent_text, result)

        return result

    def should_use_swarm(self, intent_text: str) -> bool:
        """Return True if the intent warrants swarm (MODERATE or COMPLEX)."""
        result = self.classify(intent_text)
        return result.level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)

    def suggest_spore_count(self, intent_text: str) -> int:
        """Return the suggested number of parallel spore workers (1–8)."""
        result = self.classify(intent_text)
        return result.suggested_swarm_size

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_rules(
        self,
        *,
        word_count: int,
        sentence_count: int,
        complex_hits: list[str],
        step_hits: list[str],
        simple_hits: list[str],
        conjunction_hits: list[str],
        normalised: str,
    ) -> tuple[ComplexityLevel, list[str], float]:
        """Core rule engine.  Returns (level, rationale_parts, base_confidence)."""
        rationale: list[str] = []

        # --- COMPLEX fast-paths ---
        if sentence_count > 2:
            rationale.append(f"sentence count {sentence_count} > 2 → COMPLEX")
            return ComplexityLevel.COMPLEX, rationale, 0.80

        if len(complex_hits) >= 2:
            rationale.append(f"multiple COMPLEX indicators: {', '.join(complex_hits[:3])}")
            return ComplexityLevel.COMPLEX, rationale, 0.85

        if len(complex_hits) == 1 and len(step_hits) >= 1:
            rationale.append(f"COMPLEX keyword '{complex_hits[0]}' + step word '{step_hits[0]}'")
            return ComplexityLevel.COMPLEX, rationale, 0.78

        if word_count > 20 and complex_hits:
            rationale.append(f"long intent ({word_count} words) with COMPLEX keyword '{complex_hits[0]}'")
            return ComplexityLevel.COMPLEX, rationale, 0.75

        # === ENHANCED: Security/Audit fast-path ===
        security_keywords = {
            "security",
            "vulnerability",
            "threat",
            "authentication",
            "authorization",
            "permission",
            "access control",
            "audit",
        }
        if any(kw in normalised for kw in security_keywords):
            rationale.append("security/audit context detected → COMPLEX")
            return ComplexityLevel.COMPLEX, rationale, 0.88

        # === ENHANCED: Multi-file/multi-module indicators ===
        multi_indicators = {
            "all files",
            "every",
            "entire",
            "whole",
            "all modules",
            "across",
            "throughout",
            "全部",
            "所有文件",
        }
        if any(ind in normalised for ind in multi_indicators):
            rationale.append("multi-target scope detected → COMPLEX")
            return ComplexityLevel.COMPLEX, rationale, 0.85

        # === ENHANCED: Code generation with specifications ===
        gen_indicators = {
            "generate",
            "create",
            "implement",
            "write code",
            "build",
            "develop",
            "create new",
        }
        spec_indicators = {
            "specification",
            "spec",
            "requirement",
            "design",
            "architecture",
            "blueprint",
        }
        if any(ind in normalised for ind in gen_indicators):
            if any(ind in normalised for ind in spec_indicators) or word_count > 15:
                rationale.append("code generation with specification → COMPLEX")
                return ComplexityLevel.COMPLEX, rationale, 0.82

        # --- SIMPLE fast-path ---
        if word_count < 8 and not conjunction_hits and not complex_hits and not step_hits:
            rationale.append(f"short intent ({word_count} words) with no conjunctions or complex indicators")
            return ComplexityLevel.SIMPLE, rationale, 0.90

        # Pure simple verbs with no mixing signals
        if simple_hits and not complex_hits and not step_hits and word_count <= 12:
            rationale.append(f"simple action verb(s): {', '.join(simple_hits[:2])}; no complex or step indicators")
            return ComplexityLevel.SIMPLE, rationale, 0.88

        # --- MODERATE middle ground ---
        if step_hits and not complex_hits:
            rationale.append(f"step/sequence words: {', '.join(step_hits[:2])}; no COMPLEX keywords → MODERATE")
            return ComplexityLevel.MODERATE, rationale, 0.75

        if complex_hits and word_count <= 12:
            rationale.append(f"single COMPLEX keyword '{complex_hits[0]}' in short intent → MODERATE")
            return ComplexityLevel.MODERATE, rationale, 0.70

        if conjunction_hits and word_count >= 8:
            rationale.append(f"conjunctions {conjunction_hits[:2]} suggest multi-step → MODERATE")
            return ComplexityLevel.MODERATE, rationale, 0.65

        # --- Default: MODERATE for anything ambiguous ---
        rationale.append("no clear pattern — defaulting to MODERATE")
        return ComplexityLevel.MODERATE, rationale, 0.55

    def _compute_confidence(
        self,
        *,
        level: ComplexityLevel,
        word_count: int,
        complex_hits: list[str],
        step_hits: list[str],
        simple_hits: list[str],
        base: float,
    ) -> float:
        """
        Enhanced confidence computation with multi-factor analysis.
        Considers: keyword density, word count patterns, keyword diversity.
        """
        bonus = 0.0

        if level == ComplexityLevel.COMPLEX:
            # More keywords = higher confidence
            bonus += min(len(complex_hits) * 0.03, 0.12)
            # Long intents with complex keywords are more certain
            if word_count > 20:
                bonus += 0.05
            # Multiple distinct categories = higher confidence
            if len(complex_hits) >= 3:
                bonus += 0.05
        elif level == ComplexityLevel.SIMPLE:
            bonus += min(len(simple_hits) * 0.02, 0.08)
            # Very short intents are very confident
            if word_count < 5:
                bonus += 0.05
            # Single clear verb is confident
            if len(simple_hits) == 1:
                bonus += 0.03
        elif level == ComplexityLevel.MODERATE:
            bonus += min(len(step_hits) * 0.02, 0.06)
            # Step words suggest clear process
            if len(step_hits) >= 2:
                bonus += 0.03

        # === ENHANCED: Pattern coherence bonus ===
        # High keyword density (many matches relative to word count) = more confident
        total_hits = len(complex_hits) + len(simple_hits) + len(step_hits)
        if word_count > 0:
            density = total_hits / word_count
            if density > 0.2:  # High signal density
                bonus += 0.05

        return min(base + bonus, 1.0)

    def _swarm_size(
        self,
        level: ComplexityLevel,
        word_count: int,
        complex_hits: list[str],
        step_hits: list[str],
    ) -> int:
        """Derive swarm worker count (1–8) from complexity signals."""
        if level == ComplexityLevel.SIMPLE:
            return 1
        if level == ComplexityLevel.MODERATE:
            base = 2
            base += min(len(step_hits), 2)
            return min(base, 4)
        # COMPLEX
        base = 3
        base += min(len(complex_hits), 3)
        if word_count > 25:
            base += 1
        return min(base, 8)

    def _suggest_roles(
        self,
        level: ComplexityLevel,
        complex_hits: list[str],
    ) -> list[str]:
        """Produce a role list tuned to detected keywords."""
        base = list(_DEFAULT_ROLES[level])

        if level == ComplexityLevel.COMPLEX:
            if any(kw in complex_hits for kw in ("research", "analyze", "analyse", "investigate")):
                if "researcher" not in base:
                    base.insert(1, "researcher")
            if any(kw in complex_hits for kw in ("compare", "benchmark", "evaluate")):
                if "analyst" not in base:
                    base.append("analyst")
            if any(kw in complex_hits for kw in ("coordinate", "orchestrate")):
                if "coordinator" not in base:
                    base.insert(0, "coordinator")

        return base[:8]  # cap at 8

    def _try_llm_enhance(
        self,
        intent_text: str,
        result: ClassificationResult,
    ) -> ClassificationResult:
        """
        Optional LLM enhancement path.

        Attempts to import an LLM client from the execution engine.  On any
        failure, silently returns the original heuristic result unchanged.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            _log.debug("LLM enhance skipped because an event loop is already running.")
            return result

        prompt = (
            f"Rate the complexity of this intent as SIMPLE, MODERATE, or COMPLEX. "
            f'Intent: "{intent_text}". '
            f'Respond with JSON: {{"level": "...", "confidence": 0.0}}'
        )

        try:
            response = asyncio.run(InferenceOracle.get_instance().infer(prompt=prompt, max_tokens=64))
            if response.get("status") != "success":
                return result

            import json as _json

            data = _json.loads(response.get("content", ""))
            level_str = data.get("level", result.level.value).upper()
            llm_level = ComplexityLevel(level_str)
            llm_confidence = float(data.get("confidence", result.confidence))
            # Blend heuristic + LLM: weight heuristic 40%, LLM 60%
            blended_confidence = round(result.confidence * 0.4 + llm_confidence * 0.6, 2)
            return ClassificationResult(
                level=llm_level,
                confidence=blended_confidence,
                rationale=result.rationale + f"; LLM override: {llm_level.value}",
                suggested_swarm_size=result.suggested_swarm_size,
                suggested_roles=result.suggested_roles,
            )
        except (AttributeError, OSError, RuntimeError, TimeoutError, TypeError, ValueError) as exc:
            _log.debug("LLM enhance failed (harmless): %s", exc)
            return result
