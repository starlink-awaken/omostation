from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L2
Summary: "Hybrid Intent Classifier — L1 rules + L2 LLM with three-tier quality assessment"
Tags:
  - intent
  - classifier
  - hybrid
  - llm
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Hybrid Classifier ≡ Module
# 内涵 ≝ {Hybrid, Classifier}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, HybridClassifier)}
# 功能 ⊢ {Hybrid_Classifier, Init_Hybrid, Validate_Classifier}
# =============================================================================


import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

_log = logging.getLogger(__name__)


class _ClassificationLevel(Protocol):
    value: str


class _L1ClassificationResult(Protocol):
    confidence: float
    rationale: str
    level: _ClassificationLevel


# =============================================================================
# Enums & Data Classes
# =============================================================================


class ClassificationPath(Enum):
    """Which classification path was taken."""

    L1_RULES = "l1_rules"
    L2_LLM = "l2_llm"
    L3_HYBRID = "l3_hybrid"  # Combined result


@dataclass
class HybridClassificationResult:
    """Enhanced result with path and quality metrics."""

    level: str  # SIMPLE, MODERATE, COMPLEX
    confidence: float
    reasoning: str
    path: ClassificationPath
    l1_confidence: float = 0.0
    l2_confidence: float = 0.0
    l1_level: str | None = None
    l2_level: str | None = None
    latency_ms: float = 0.0
    llm_used: bool = False
    cache_hit: bool = False


# =============================================================================
# Hybrid Intent Classifier
# =============================================================================


class HybridIntentClassifier:
    """
    Hybrid intent classifier combining rule-based (L1) and LLM-based (L2) approaches.

    Architecture:
    - L1: Fast heuristic rules (existing IntentClassifier logic)
    - L2: LLM semantic analysis (Ollama-based)
    - L3: Three-tier quality assessment and result fusion

    Performance targets:
    - L1 path: <50ms (rules only)
    - L2 path: <500ms P50 (LLM inference)
    - Cache hit: <10ms

    Accuracy targets:
    - Overall: >92% on natural language queries
    - L1 alone: ~72% (baseline)
    - L2 alone: >90% (target)
    """

    def __init__(self, enable_llm: bool = True) -> None:
        """
        Initialize the hybrid classifier.

        Args:
            enable_llm: Whether to enable L2 LLM path (default: True).
                      Can be disabled via BOS_HYBRID_CLASSIFIER=false env var.
        """
        super().__init__()
        self.organ_name = "hybrid_classifier"
        # Check environment variable override
        env_hybrid = os.environ.get("BOS_HYBRID_CLASSIFIER", "true").lower()
        self._enable_llm = enable_llm and env_hybrid in ("true", "1", "yes")

        # Import L1 classifier (existing rule-based implementation)
        from .organs.intent_classifier import (  # type: ignore[import-not-found]
            IntentClassifier as L1Classifier,
        )

        self._l1_classifier = L1Classifier(llm_enhance=False)

        # LLM client (lazy load)
        self._llm_client: Any | None = None
        self._llm_model: str = "llama3.2"

        # Prompt templates
        self._prompts: dict[str, Any] = {}
        self._load_prompts()

        # Result cache (LRU)
        self._cache: dict[str, tuple[float, HybridClassificationResult]] = {}
        self._cache_max_size = 1000
        self._cache_ttl = 3600  # 1 hour

        _log.info(f"HybridIntentClassifier initialized (LLM enabled: {self._enable_llm})")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, intent_text: str) -> HybridClassificationResult:
        """
        Classify intent using hybrid approach.

        Args:
            intent_text: User's natural language input

        Returns:
            HybridClassificationResult with path information
        """
        start_time = time.time()

        # Check cache
        cached_result = self._check_cache(intent_text)
        if cached_result is not None:
            cached_result.cache_hit = True
            cached_result.latency_ms = (time.time() - start_time) * 1000
            return cached_result

        # L1: Rule-based classification
        l1_result = self._l1_classifier.classify(intent_text)

        # Extract confidence from L1 result (normalize to 0-1)
        l1_confidence = l1_result.confidence

        # Quality assessment: should we use L2?
        if self._should_trigger_llm(l1_confidence, intent_text):
            # L2: LLM-based classification
            l2_result = self._classify_with_llm(intent_text)

            # L3: Quality assessment and fusion
            final_result = self._fuse_results(intent_text, l1_result, l2_result)
        else:
            # L1 high confidence, skip L2
            final_result = HybridClassificationResult(
                level=l1_result.level.value,
                confidence=l1_confidence,
                reasoning=l1_result.rationale,
                path=ClassificationPath.L1_RULES,
                l1_confidence=l1_confidence,
                l1_level=l1_result.level.value,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Cache result
        self._add_to_cache(intent_text, final_result)

        return final_result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _should_trigger_llm(self, l1_confidence: float, intent_text: str) -> bool:
        """
        Decide whether to trigger L2 LLM path.

        Triggers L2 if:
        - LLM is enabled
        - L1 confidence is below threshold
        - Intent length suggests complexity (>60 chars)
        """
        if not self._enable_llm:
            return False

        # Configuration from prompts YAML
        llm_activation_threshold = self._prompts.get("thresholds", {}).get("llm_activation", 0.75)

        # Trigger if L1 confidence is low
        if l1_confidence < llm_activation_threshold:
            _log.debug(f"L2 triggered: L1 confidence {l1_confidence:.2f} < {llm_activation_threshold}")
            return True

        # Trigger for longer intents (heuristic)
        if len(intent_text) > 60:
            _log.debug("L2 triggered: intent length > 60 chars")
            return True

        return False

    def _classify_with_llm(self, intent_text: str) -> tuple[str, float, str]:
        """
        Classify using LLM (L2 path).

        Returns:
            Tuple of (level, confidence, reasoning)
        """
        try:
            # Lazy load LLM client
            if self._llm_client is None:
                self._init_llm_client()

            # Build prompt from template
            prompt = self._prompts.get("classification_prompt", "").format(user_intent=intent_text)

            # Call LLM
            response = self._call_llm(prompt)

            # Parse JSON response
            try:
                data = json.loads(response)
                level = data.get("level", "MODERATE").upper()
                confidence = float(data.get("confidence", 0.7))
                reasoning = data.get("reasoning", "LLM classification")

                # Validate level
                valid_levels = {"SIMPLE", "MODERATE", "COMPLEX"}
                if level not in valid_levels:
                    _log.warning(f"LLM returned invalid level: {level}, defaulting to MODERATE")
                    level = "MODERATE"

                return level, confidence, reasoning
            except json.JSONDecodeError:
                _log.error(f"Failed to parse LLM response as JSON: {response}")
                return "MODERATE", 0.5, "LLM parsing failed"

        except Exception as exc:
            _log.warning(f"LLM classification failed: {exc}, falling back to MODERATE")
            return "MODERATE", 0.5, f"LLM error: {str(exc)[:50]}"

    def _fuse_results(
        self,
        intent_text: str,
        l1_result: _L1ClassificationResult,
        l2_result: tuple[str, float, str],
    ) -> HybridClassificationResult:
        """
        Fuse L1 and L2 results using quality assessment.

        Returns:
            HybridClassificationResult with final classification
        """
        l2_level, l2_confidence, l2_reasoning = l2_result
        l1_confidence = l1_result.confidence

        # Quality check: L3 semantic validation
        l1_level = l1_result.level.value
        semantic_drift = self._calculate_semantic_drift(l1_level, l2_level)

        # Get thresholds
        drift_threshold = self._prompts.get("quality_assessment", {}).get("semantic_drift_threshold", 0.3)

        if semantic_drift > drift_threshold:
            # Significant disagreement - use L2 (more intelligent)
            _log.info(f"L3: Semantic drift {semantic_drift:.2f} > {drift_threshold}, using L2 result")
            final_level = l2_level
            final_reasoning = f"{l2_reasoning} (L1: {l1_level})"
            final_confidence = l2_confidence
            path = ClassificationPath.L2_LLM
        else:
            # Agreement - blend results (weighted average)
            # Weight L2 slightly higher (0.6) because it's more intelligent
            final_confidence = round(l1_confidence * 0.4 + l2_confidence * 0.6, 2)

            # Choose level based on higher confidence
            if l2_confidence > l1_confidence:
                final_level = l2_level
                final_reasoning = f"{l2_reasoning} (L1 agreed: {l1_level})"
                path = ClassificationPath.L2_LLM
            else:
                final_level = l1_level
                final_reasoning = f"{l1_result.rationale} (L2 confirmed: {l2_level})"
                path = ClassificationPath.L1_RULES

        return HybridClassificationResult(
            level=final_level,
            confidence=final_confidence,
            reasoning=final_reasoning,
            path=path,
            l1_confidence=l1_confidence,
            l2_confidence=l2_confidence,
            l1_level=l1_level,
            l2_level=l2_level,
            llm_used=True,
        )

    def _calculate_semantic_drift(self, l1_level: str, l2_level: str) -> float:
        """
        Calculate semantic drift between L1 and L2 classifications.

        Returns:
            Drift score (0.0 = agreement, 1.0 = maximum disagreement)
        """
        level_order = {"SIMPLE": 0, "MODERATE": 1, "COMPLEX": 2}

        l1_value = level_order.get(l1_level, 1)
        l2_value = level_order.get(l2_level, 1)

        return abs(l1_value - l2_value) / 2.0  # Normalize to 0-1

    def _init_llm_client(self) -> None:
        """Initialize LLM client (lazy load)."""
        try:
            from .organs.synapse_ollama import OllamaSynapse  # type: ignore[import-not-found]

            self._llm_client = OllamaSynapse()
            _log.info("LLM client initialized (OllamaSynapse)")
        except ImportError:
            _log.error("Failed to import OllamaSynapse, LLM path disabled")
            self._enable_llm = False
            self._llm_client = None

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM and return response.

        Args:
            prompt: Classification prompt

        Returns:
            LLM response text
        """
        if self._llm_client is None:
            raise RuntimeError("LLM client not initialized")

        system_prompt = self._prompts.get("system_prompt", "")
        llm_config = self._prompts.get("llm_config", {})
        model = llm_config.get("model", "llama3.2")

        # Call Ollama
        response = self._llm_client.generate(
            model=model, prompt=prompt, system=system_prompt, options={"num_predict": 128}
        )

        # Check for errors
        if response.get("status") == "error":
            raise RuntimeError(f"LLM error: {response.get('message')}")

        # Extract response text
        return response.get("response", "")

    def _load_prompts(self) -> None:
        """Load prompt templates from YAML configuration."""
        import yaml

        config_path = "config/intents_classifier_prompts.yaml"

        try:
            with open(config_path) as f:
                prompts = yaml.safe_load(f)
            _log.info(f"Loaded prompts from {config_path}")
        except FileNotFoundError:
            _log.warning(f"Prompt config not found at {config_path}, using defaults")
            self._prompts = self._get_default_prompts()
            return
        except (OSError, yaml.YAMLError) as exc:
            _log.warning(f"Failed to load prompts: {exc}, using defaults")
            self._prompts = self._get_default_prompts()
            return

        if isinstance(prompts, dict) and prompts:
            self._prompts = prompts
            return

        _log.warning(f"Prompt config at {config_path} was empty or invalid, using defaults")
        self._prompts = self._get_default_prompts()

    def _get_default_prompts(self) -> dict[str, Any]:
        """Return default prompt configuration."""
        return {
            "system_prompt": "You are an intent complexity classifier for B-OS.",
            "classification_prompt": 'Classify: "{user_intent}"\nRespond with JSON: {{"level": "SIMPLE|MODERATE|COMPLEX", "confidence": 0.0}}',
            "llm_config": {"model": "llama3.2", "timeout_ms": 300},
            "thresholds": {"llm_activation": 0.75},
            "quality_assessment": {"semantic_drift_threshold": 0.3},
        }

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _check_cache(self, intent_text: str) -> HybridClassificationResult | None:
        """Check cache for existing result."""
        if intent_text in self._cache:
            timestamp, result = self._cache[intent_text]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                # Expired, remove
                del self._cache[intent_text]

        return None

    def _add_to_cache(self, intent_text: str, result: HybridClassificationResult) -> None:
        """Add result to cache."""
        # Implement LRU eviction
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (FIFO for simplicity)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[intent_text] = (time.time(), result)

    def health_check(self) -> dict[str, Any]:
        """Check hybrid classifier health."""
        return {
            "status": "healthy",
            "llm_enabled": self._enable_llm,
            "llm_available": self._llm_client is not None,
            "cache_size": len(self._cache),
            "prompts_loaded": len(self._prompts) > 0,
        }
